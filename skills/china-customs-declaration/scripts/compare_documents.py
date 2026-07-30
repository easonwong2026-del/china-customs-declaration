#!/usr/bin/env python3
"""
单据一致性比较系统（按商品匹配）

比较发票、箱单、合同等单据，通过商品匹配键（SKU → 品牌+型号+HS编码 → 型号+HS编码 → 品名+型号 → 模糊匹配）
进行逐项比对，支持多行聚合与 Decimal 精确计算。

用法:
    python compare_documents.py invoice.csv packing_list.csv contract.json
    python compare_documents.py --dir ./documents/
    python compare_documents.py --output result.json invoice.csv packing_list.csv
    python compare_documents.py --test        # 运行自测
"""

import argparse
import csv
import json
import os
import sys
from collections import OrderedDict
from decimal import Decimal

# ── 确保能找到 common 模块 ──────────────────────────────────────────────
_script_dir = os.path.dirname(os.path.abspath(__file__))
if _script_dir not in sys.path:
    sys.path.insert(0, _script_dir)

from common.decimal_utils import (
    check_amount_match,
    to_decimal_safe,
)
from common.field_normalizer import (
    FIELD_ALIASES,
    normalize_hs_code,
    normalize_model,
    normalize_text,
)

# ── 匹配置信度级别 ─────────────────────────────────────────────────────
CONF_SKU = Decimal("1.0")
CONF_BRAND_MODEL_HS = Decimal("0.9")
CONF_MODEL_HS = Decimal("0.8")
CONF_NAME_MODEL = Decimal("0.7")
CONF_FUZZY = Decimal("0.3")


# =====================================================================
#  文档加载
# =====================================================================


def load_document(filepath: str) -> list[dict]:
    """
    加载单据文件（CSV / JSON）。

    JSON 支持两种结构：
      - 纯数组: [{"品名": "..."}, ...]
      - 字典（从某个键下取数组）: {"items": [...], "data": [...]}
    """
    if not os.path.exists(filepath):
        print(f"警告: 文件不存在: {filepath}")
        return []
    with open(filepath, "r", encoding="utf-8-sig") as f:
        ext = os.path.splitext(filepath)[1].lower()
        if ext == ".json":
            data = json.load(f)
            if isinstance(data, dict):
                # 查找常见的数据容器键
                for key in (
                    "items",
                    "data",
                    "records",
                    "rows",
                    "商品",
                    "明细",
                    "declaration",
                    "invoice",
                    "packing",
                ):
                    if key in data and isinstance(data[key], list):
                        return data[key]
                # 找不到则取第一个列表值
                for v in data.values():
                    if isinstance(v, list):
                        return v
                return []
            return list(data) if isinstance(data, list) else []
        elif ext == ".csv":
            reader = csv.DictReader(f)
            return list(reader)
        else:
            raise ValueError(f"不支持的文件格式: {filepath}")


# =====================================================================
#  行标准化
# =====================================================================


def normalize_row(row: dict) -> dict:
    """
    将行的字段别名标准化为统一键名。

    例: 若行中有 "品名" 而非 "中文品名"，标准化后会保留原键并增加 "中文品名" 键。
    """
    normalized = dict(row)
    for standard_field, aliases in FIELD_ALIASES.items():
        for alias in aliases:
            if alias in row:
                # 只在没有该标准字段时写入
                if (
                    standard_field not in normalized
                    or not str(normalized.get(standard_field, "")).strip()
                ):
                    normalized[standard_field] = row[alias]
                break
    return normalized


# =====================================================================
#  匹配键计算
# =====================================================================


def compute_item_key(row: dict, keys_available: list[str]) -> tuple[str, float]:
    """
    为单据行计算匹配键，按优先级返回最高可用的键。

    Priority:
      1. 货号/SKU  →  exact match, confidence=1.0
      2. brand + model + hs_code  →  confidence=0.9
      3. model + hs_code  →  confidence=0.8
      4. name + model  →  confidence=0.7
      5. fuzzy (name only)  →  confidence=0.3

    Args:
        row: 标准化后的行数据
        keys_available: 当前上下文中可用字段名列表（用于判断哪些策略可用）

    Returns:
        (key_string, confidence)
    """
    # 从行中提取各字段值
    name = normalize_text(row.get("中文品名", ""))
    model = normalize_model(row.get("型号", ""))
    hs = normalize_hs_code(row.get("HS编码", ""))
    brand = normalize_text(row.get("品牌", ""))
    sku = normalize_text(row.get("货号", ""))

    # 1. SKU
    if sku:
        return (sku, 1.0)

    # 2. brand + model + HS
    if brand and model and hs:
        return (f"{brand}|{model}|{hs}", 0.9)

    # 3. model + HS
    if model and hs:
        return (f"{model}|{hs}", 0.8)

    # 4. name + model
    if name and model:
        return (f"{name}|{model}", 0.7)

    # 5. fuzzy on name
    if name:
        return (name, 0.3)

    # 无可辨识内容
    return ("", 0.0)


def compute_all_keys(row: dict) -> list[tuple[str, Decimal]]:
    """
    为一行计算**所有**可能的匹配键，按置信度从高到低排列。

    返回:
        [(key_string, confidence), ...]
    """
    keys: list[tuple[str, Decimal]] = []
    name = normalize_text(row.get("中文品名", ""))
    model = normalize_model(row.get("型号", ""))
    hs = normalize_hs_code(row.get("HS编码", ""))
    brand = normalize_text(row.get("品牌", ""))
    sku = normalize_text(row.get("货号", ""))

    if sku:
        keys.append((sku, CONF_SKU))
    if brand and model and hs:
        keys.append((f"{brand}|{model}|{hs}", CONF_BRAND_MODEL_HS))
    if model and hs:
        keys.append((f"{model}|{hs}", CONF_MODEL_HS))
    if name and model:
        keys.append((f"{name}|{model}", CONF_NAME_MODEL))
    if name:
        keys.append((name, CONF_FUZZY))

    return keys


# =====================================================================
#  聚合
# =====================================================================


def aggregate_items(rows: list[dict], doc_name: str) -> dict:
    """
    将多行按匹配键聚合。同一商品分拆在箱单的多行中，数量/金额会被求和。

    Returns:
        {primary_key: {
            "primary_key": str,
            "all_keys": {key_string: conf_float, ...},
            "confidence": float,
            "doc_name": str,
            "source_rows": [dict, ...],
            "aggregated_qty": Decimal,
            "aggregated_amount": Decimal,
            "aggregated_gross": Decimal,
            "aggregated_net": Decimal,
            "unit_price": Decimal or None,
        }, ...}
    """
    aggregates: dict[str, dict] = OrderedDict()

    for row in rows:
        all_keys = compute_all_keys(row)
        if not all_keys:
            continue

        # 以最高置信度的键作为主键
        primary_key, _ = all_keys[0]

        if primary_key not in aggregates:
            aggregates[primary_key] = {
                "primary_key": primary_key,
                "all_keys": {k: float(c) for k, c in all_keys},
                "confidence": float(all_keys[0][1]),
                "doc_name": doc_name,
                "source_rows": [],
                "aggregated_qty": Decimal("0"),
                "aggregated_amount": Decimal("0"),
                "aggregated_gross": Decimal("0"),
                "aggregated_net": Decimal("0"),
            }

        agg = aggregates[primary_key]
        agg["source_rows"].append(row)
        agg["aggregated_qty"] += to_decimal_safe(row.get("数量"))
        agg["aggregated_amount"] += to_decimal_safe(row.get("总价"))
        agg["aggregated_gross"] += to_decimal_safe(row.get("毛重"))
        agg["aggregated_net"] += to_decimal_safe(row.get("净重"))

        # 更新 all_keys（合并新 key 映射）
        for k, c in all_keys:
            if k not in agg["all_keys"]:
                agg["all_keys"][k] = float(c)

    return aggregates


# =====================================================================
#  文档间匹配
# =====================================================================


def _match_aggregates(agg1: dict, name1: str, agg2: dict, name2: str) -> dict:
    """
    在两个聚合字典之间按置信度从高到低执行匹配。

    Returns:
        {
            "matched_items": [...],
            "unmatched_in_doc1": [...],
            "unmatched_in_doc2": [...],
        }
    """
    matched_items: list[dict] = []
    keys1_remaining = set(agg1.keys())
    keys2_remaining = set(agg2.keys())

    # 按置信度级别从高到低匹配
    conf_levels = [
        (CONF_SKU, "SKU"),
        (CONF_BRAND_MODEL_HS, "brand+model+HS"),
        (CONF_MODEL_HS, "model+HS"),
        (CONF_NAME_MODEL, "name+model"),
        (CONF_FUZZY, "fuzzy"),
    ]

    for conf_threshold, level_name in conf_levels:
        if not keys1_remaining or not keys2_remaining:
            break

        matched_keys_1: set[str] = set()
        matched_keys_2: set[str] = set()

        for pk1 in list(keys1_remaining):
            entry1 = agg1[pk1]
            # 当前条目的最高置信度必须 >= 当前级别
            if entry1["confidence"] < float(conf_threshold):
                continue

            # 在 doc2 剩余条目中查找匹配
            best_match = None
            for pk2 in list(keys2_remaining):
                entry2 = agg2[pk2]
                if entry2["confidence"] < float(conf_threshold):
                    continue

                # 检查是否有共同键
                if (
                    pk1 == pk2
                    or any(k1 in entry2["all_keys"] for k1 in entry1["all_keys"])
                    or any(k2 in entry1["all_keys"] for k2 in entry2["all_keys"])
                ):
                    best_match = pk2
                    break

            if best_match is not None:
                entry1 = agg1[pk1]
                entry2 = agg2[best_match]
                differences = []
                has_significant_diff = False

                # 比较数量
                qty1, qty2 = entry1["aggregated_qty"], entry2["aggregated_qty"]
                qty_match, _, _ = check_amount_match(
                    qty1, qty2, tolerance=Decimal("0.001")
                )
                if not qty_match:
                    diff_amt = abs(to_decimal_safe(qty1) - to_decimal_safe(qty2))
                    differences.append(
                        {
                            "field": "数量",
                            "doc1_value": str(qty1),
                            "doc2_value": str(qty2),
                            "diff_amount": str(diff_amt),
                        }
                    )
                    has_significant_diff = True

                # 比较总价
                amt1, amt2 = entry1["aggregated_amount"], entry2["aggregated_amount"]
                amt_match, _, _ = check_amount_match(amt1, amt2)
                if not amt_match:
                    diff_amt = abs(to_decimal_safe(amt1) - to_decimal_safe(amt2))
                    differences.append(
                        {
                            "field": "总价",
                            "doc1_value": str(amt1),
                            "doc2_value": str(amt2),
                            "diff_amount": str(diff_amt),
                        }
                    )
                    has_significant_diff = True

                # 比较毛重（至少一方 > 0 时才检查）
                gw1, gw2 = entry1["aggregated_gross"], entry2["aggregated_gross"]
                if gw1 > 0 or gw2 > 0:
                    gw_match, _, _ = check_amount_match(
                        gw1, gw2, tolerance=Decimal("0.01")
                    )
                    if not gw_match:
                        diff_amt = abs(gw1 - gw2)
                        differences.append(
                            {
                                "field": "毛重",
                                "doc1_value": str(gw1),
                                "doc2_value": str(gw2),
                                "diff_amount": str(diff_amt),
                            }
                        )
                        has_significant_diff = True

                # 比较净重
                nw1, nw2 = entry1["aggregated_net"], entry2["aggregated_net"]
                if nw1 > 0 or nw2 > 0:
                    nw_match, _, _ = check_amount_match(
                        nw1, nw2, tolerance=Decimal("0.01")
                    )
                    if not nw_match:
                        diff_amt = abs(nw1 - nw2)
                        differences.append(
                            {
                                "field": "净重",
                                "doc1_value": str(nw1),
                                "doc2_value": str(nw2),
                                "diff_amount": str(diff_amt),
                            }
                        )
                        has_significant_diff = True

                matched_items.append(
                    {
                        "match_key": pk1,
                        "level": level_name,
                        "confidence": float(conf_threshold),
                        "doc1": {
                            "source_rows": entry1["source_rows"],
                            "aggregated_qty": str(entry1["aggregated_qty"]),
                            "aggregated_amount": str(entry1["aggregated_amount"]),
                            "aggregated_gross": str(entry1["aggregated_gross"]),
                            "aggregated_net": str(entry1["aggregated_net"]),
                            "row_count": len(entry1["source_rows"]),
                        },
                        "doc2": {
                            "source_rows": entry2["source_rows"],
                            "aggregated_qty": str(entry2["aggregated_qty"]),
                            "aggregated_amount": str(entry2["aggregated_amount"]),
                            "aggregated_gross": str(entry2["aggregated_gross"]),
                            "aggregated_net": str(entry2["aggregated_net"]),
                            "row_count": len(entry2["source_rows"]),
                        },
                        "differences": differences,
                        "has_significant_diff": has_significant_diff,
                    }
                )

                matched_keys_1.add(pk1)
                matched_keys_2.add(best_match)

        keys1_remaining -= matched_keys_1
        keys2_remaining -= matched_keys_2

    # 构建未匹配条目列表
    def _build_unmatched(keys, agg) -> list[dict]:
        return [
            {
                "key": agg[k]["primary_key"],
                "confidence": agg[k]["confidence"],
                "source_rows": agg[k]["source_rows"],
                "aggregated_qty": str(agg[k]["aggregated_qty"]),
                "aggregated_amount": str(agg[k]["aggregated_amount"]),
                "aggregated_gross": str(agg[k]["aggregated_gross"]),
                "aggregated_net": str(agg[k]["aggregated_net"]),
                "row_count": len(agg[k]["source_rows"]),
            }
            for k in keys
        ]

    return {
        "matched_items": matched_items,
        "unmatched_in_doc1": _build_unmatched(keys1_remaining, agg1),
        "unmatched_in_doc2": _build_unmatched(keys2_remaining, agg2),
    }


# =====================================================================
#  主比较函数
# =====================================================================


def compare_documents(files: dict[str, str]) -> dict:
    """
    主比较函数。对文档两两配对，按商品匹配键逐项比对。

    Args:
        files: {文档名称: 文件路径} 的映射
               例: {"发票": "invoice.csv", "箱单": "packing_list.csv"}

    Returns:
        {
            "document_pairs": [{
                "doc1_name": str,
                "doc2_name": str,
                "matched_items": [...],
                "unmatched_in_doc1": [...],
                "unmatched_in_doc2": [...],
            }, ...],
            "summary": {
                "total_items": int,
                "matched": int,
                "unmatched": int,
                "differences_found": int,
                "compared_documents": [str, ...],
            },
        }
    """
    # 加载并标准化
    loaded: dict[str, list[dict]] = {}
    for name, path in files.items():
        raw = load_document(path)
        loaded[name] = [normalize_row(r) for r in raw] if raw else []
        if not loaded[name]:
            print(f"警告: '{name}' 文件为空或不包含有效数据 ({path})")

    doc_names = list(loaded.keys())
    document_pairs = []
    total_matched = 0
    total_unmatched = 0
    total_differences = 0

    for i in range(len(doc_names)):
        for j in range(i + 1, len(doc_names)):
            name1, name2 = doc_names[i], doc_names[j]
            rows1 = loaded[name1]
            rows2 = loaded[name2]

            if not rows1 or not rows2:
                continue

            agg1 = aggregate_items(rows1, name1)
            agg2 = aggregate_items(rows2, name2)

            pair_result = _match_aggregates(agg1, name1, agg2, name2)

            total_matched += len(pair_result["matched_items"])
            total_unmatched += len(pair_result["unmatched_in_doc1"])
            total_unmatched += len(pair_result["unmatched_in_doc2"])
            total_differences += sum(
                1 for m in pair_result["matched_items"] if m["has_significant_diff"]
            )

            document_pairs.append(
                {
                    "doc1_name": name1,
                    "doc2_name": name2,
                    "matched_items": pair_result["matched_items"],
                    "unmatched_in_doc1": pair_result["unmatched_in_doc1"],
                    "unmatched_in_doc2": pair_result["unmatched_in_doc2"],
                }
            )

    return {
        "document_pairs": document_pairs,
        "summary": {
            "total_items": total_matched + total_unmatched,
            "matched": total_matched,
            "unmatched": total_unmatched,
            "differences_found": total_differences,
            "compared_documents": doc_names,
        },
    }


# =====================================================================
#  报告输出
# =====================================================================


def print_report(result: dict) -> None:
    """打印可读的 HTML 风格比较报告。"""
    summary = result["summary"]

    print("╔" + "═" * 68 + "╗")
    print("║  单据一致性比较报告（按商品匹配）                              ║")
    print("╚" + "═" * 68 + "╝")

    print(f"\n比较文档: {', '.join(summary['compared_documents'])}")
    print(f"总商品数: {summary['total_items']}")
    print(f"已匹配:   {summary['matched']}")
    print(f"未匹配:   {summary['unmatched']}")
    print(f"差异数:   {summary['differences_found']}")

    for pair in result["document_pairs"]:
        print(f"\n{'─' * 68}")
        print(f"  [{pair['doc1_name']}]  ↔  [{pair['doc2_name']}]")
        print(f"{'─' * 68}")

        # ── 已匹配项 ──
        matched = pair["matched_items"]
        if matched:
            print(f"\n  已匹配 ({len(matched)} 项):\n")
            for item in matched:
                status_mark = "⚠" if item["has_significant_diff"] else "✓"
                print(f"    {status_mark} [{item['level']}] {item['match_key']}")
                print(f"      置信度: {item['confidence']:.1f}")
                d1 = item["doc1"]
                d2 = item["doc2"]
                print(
                    f"      {pair['doc1_name']}:"
                    f" 数量={d1['aggregated_qty']}"
                    f", 总价={d1['aggregated_amount']}"
                    f", 毛重={d1['aggregated_gross']}"
                    f", 净重={d1['aggregated_net']}"
                    f" ({d1['row_count']}行)"
                )
                print(
                    f"      {pair['doc2_name']}:"
                    f" 数量={d2['aggregated_qty']}"
                    f", 总价={d2['aggregated_amount']}"
                    f", 毛重={d2['aggregated_gross']}"
                    f", 净重={d2['aggregated_net']}"
                    f" ({d2['row_count']}行)"
                )
                if item["differences"]:
                    print("      差异:")
                    for diff in item["differences"]:
                        print(
                            f"        {diff['field']}:"
                            f" [{pair['doc1_name']}] {diff['doc1_value']}"
                            f" vs [{pair['doc2_name']}] {diff['doc2_value']}"
                            f" (差值: {diff['diff_amount']})"
                        )
                print()
        else:
            print("  无匹配项")

        # ── 仅 doc1 有的项 ──
        unmatched1 = pair["unmatched_in_doc1"]
        if unmatched1:
            print(f"  [仅 {pair['doc1_name']} 有] ({len(unmatched1)} 项):")
            for item in unmatched1:
                print(
                    f"    ✗ {item['key']}"
                    f" (置信度: {item['confidence']:.1f}"
                    f", 数量={item['aggregated_qty']}"
                    f", 总价={item['aggregated_amount']})"
                )
            print()

        # ── 仅 doc2 有的项 ──
        unmatched2 = pair["unmatched_in_doc2"]
        if unmatched2:
            print(f"  [仅 {pair['doc2_name']} 有] ({len(unmatched2)} 项):")
            for item in unmatched2:
                print(
                    f"    ✗ {item['key']}"
                    f" (置信度: {item['confidence']:.1f}"
                    f", 数量={item['aggregated_qty']}"
                    f", 总价={item['aggregated_amount']})"
                )
            print()

    print(f"\n{'═' * 68}")
    if summary["differences_found"] > 0 or summary["unmatched"] > 0:
        print(
            f"  结论: 存在 {summary['differences_found']} 处差异,"
            f" {summary['unmatched']} 项未匹配"
        )
    else:
        print("  结论: 所有内容一致 ✓")
    print(f"{'═' * 68}")


# =====================================================================
#  自测代码
# =====================================================================


def _run_tests():
    """快速验证核心逻辑。"""
    passed = 0
    failed = 0

    def check(condition: bool, msg: str):
        nonlocal passed, failed
        if condition:
            passed += 1
            print(f"  ✓ {msg}")
        else:
            failed += 1
            print(f"  ✗ {msg}")

    # ── Test 1: 相同内容不同顺序 → 应匹配 ──
    print("\n--- Test 1: 相同内容不同顺序的发票 ---")
    doc1 = [
        {
            "中文品名": "蓝牙耳机",
            "型号": "BT-100",
            "数量": "50",
            "总价": "2500.00",
            "毛重": "5.0",
            "净重": "4.5",
            "HS编码": "85183000",
        },
        {
            "中文品名": "充电线",
            "型号": "CBL-USB-C",
            "数量": "100",
            "总价": "500.00",
            "毛重": "2.0",
            "净重": "1.8",
            "HS编码": "85444211",
        },
    ]
    doc2 = [
        {
            "中文品名": "充电线",
            "型号": "CBL-USB-C",
            "数量": "100",
            "总价": "500.00",
            "毛重": "2.0",
            "净重": "1.8",
            "HS编码": "85444211",
        },
        {
            "中文品名": "蓝牙耳机",
            "型号": "BT-100",
            "数量": "50",
            "总价": "2500.00",
            "毛重": "5.0",
            "净重": "4.5",
            "HS编码": "85183000",
        },
    ]
    n1 = [normalize_row(r) for r in doc1]
    n2 = [normalize_row(r) for r in doc2]
    a1 = aggregate_items(n1, "doc1")
    a2 = aggregate_items(n2, "doc2")
    check(len(a1) == 2, f"doc1 聚合后有 2 个条目 (实际: {len(a1)})")
    check(len(a2) == 2, f"doc2 聚合后有 2 个条目 (实际: {len(a2)})")
    match_result = _match_aggregates(a1, "doc1", a2, "doc2")
    check(
        len(match_result["matched_items"]) == 2,
        f"2 项全部匹配 (实际: {len(match_result['matched_items'])})",
    )
    check(len(match_result["unmatched_in_doc1"]) == 0, "doc1 无未匹配项")
    check(len(match_result["unmatched_in_doc2"]) == 0, "doc2 无未匹配项")

    # ── Test 2: 一行发票 vs 三行箱单（分拆）→ 聚合匹配 ──
    print("\n--- Test 2: 一行发票 vs 三行箱单（分拆聚合）---")
    invoice = [
        {
            "中文品名": "蓝牙耳机",
            "型号": "BT-100",
            "数量": "150",
            "总价": "7500.00",
            "HS编码": "85183000",
        },
    ]
    packing = [
        {
            "中文品名": "蓝牙耳机",
            "型号": "BT-100",
            "数量": "50",
            "总价": "2500.00",
            "HS编码": "85183000",
        },
        {
            "中文品名": "蓝牙耳机",
            "型号": "BT-100",
            "数量": "60",
            "总价": "3000.00",
            "HS编码": "85183000",
        },
        {
            "中文品名": "蓝牙耳机",
            "型号": "BT-100",
            "数量": "40",
            "总价": "2000.00",
            "HS编码": "85183000",
        },
    ]
    inv_norm = [normalize_row(r) for r in invoice]
    pkg_norm = [normalize_row(r) for r in packing]
    agg_inv = aggregate_items(inv_norm, "发票")
    agg_pkg = aggregate_items(pkg_norm, "箱单")
    match_result = _match_aggregates(agg_inv, "发票", agg_pkg, "箱单")
    check(len(match_result["matched_items"]) == 1, "聚合后 1 项匹配")
    check(len(match_result["unmatched_in_doc1"]) == 0, "发票无未匹配")
    check(len(match_result["unmatched_in_doc2"]) == 0, "箱单无未匹配")
    if match_result["matched_items"]:
        m = match_result["matched_items"][0]
        check(m["doc1"]["aggregated_qty"] == "150", "发票数量聚合 = 150")
        check(
            m["doc2"]["aggregated_qty"] == "150",
            f"箱单数量聚合 = 150 (实际: {m['doc2']['aggregated_qty']})",
        )
        check(m["doc1"]["aggregated_amount"] == "7500.00", "发票总价聚合 = 7500.00")
        check(
            m["doc2"]["aggregated_amount"] == "7500.00",
            f"箱单总价聚合 = 7500.00 (实际: {m['doc2']['aggregated_amount']})",
        )
        check(m["doc2"]["row_count"] == 3, "箱单聚合了 3 行")

    # ── Test 3: 型号大小写/空格/连字符差异 → 应匹配 ──
    print("\n--- Test 3: 型号大小写/空格/连字符差异 ---")
    d1 = [{"中文品名": "蓝牙耳机", "型号": "BT 100", "数量": "10", "总价": "500"}]
    d2 = [{"中文品名": "蓝牙耳机", "型号": "bt-100", "数量": "10", "总价": "500"}]
    n1 = [normalize_row(r) for r in d1]
    n2 = [normalize_row(r) for r in d2]
    a1 = aggregate_items(n1, "d1")
    a2 = aggregate_items(n2, "d2")
    check(len(a1) == 1, "d1 聚合 1 项")
    check(len(a2) == 1, "d2 聚合 1 项")
    # 主键可能因空格/连字符不同，但 all_keys 交叉匹配确保匹配成功
    pk1 = list(a1.keys())[0]
    pk2 = list(a2.keys())[0]
    if pk1 != pk2:
        print(f"    (主键不同但 all_keys 交叉匹配: {pk1} vs {pk2})")
    # 验证 all_keys 中有重叠
    all_keys_share = set(a1[pk1]["all_keys"]) & set(a2[pk2]["all_keys"])
    check(len(all_keys_share) > 0, f"all_keys 有共同键 ({len(all_keys_share)} 个)")
    match_result = _match_aggregates(a1, "d1", a2, "d2")
    check(len(match_result["matched_items"]) == 1, "型号差异项匹配成功")
    check(not match_result["matched_items"][0]["has_significant_diff"], "无显著差异")

    # ── Test 4: 仅一个文档存在的项 → 标记为未匹配 ──
    print("\n--- Test 4: 未匹配项检测 ---")
    d1 = [{"中文品名": "蓝牙耳机", "型号": "BT-100", "数量": "10", "总价": "500"}]
    d2 = [{"中文品名": "充电线", "型号": "CBL-USB-C", "数量": "20", "总价": "100"}]
    n1 = [normalize_row(r) for r in d1]
    n2 = [normalize_row(r) for r in d2]
    a1 = aggregate_items(n1, "d1")
    a2 = aggregate_items(n2, "d2")
    match_result = _match_aggregates(a1, "d1", a2, "d2")
    check(len(match_result["matched_items"]) == 0, "0 项匹配")
    check(len(match_result["unmatched_in_doc1"]) == 1, "d1 有 1 未匹配")
    check(len(match_result["unmatched_in_doc2"]) == 1, "d2 有 1 未匹配")
    check(
        match_result["unmatched_in_doc1"][0]["key"].startswith("蓝牙耳机"),
        "d1 未匹配项为蓝牙耳机",
    )
    check(
        match_result["unmatched_in_doc2"][0]["key"].startswith("充电线"),
        "d2 未匹配项为充电线",
    )

    # ── Test 5: 带 SKU 的匹配 → 全量匹配 ──
    print("\n--- Test 5: SKU 精确匹配 ---")
    d1 = [{"货号": "SKU001", "中文品名": "A", "数量": "5", "总价": "100"}]
    d2 = [{"货号": "SKU001", "中文品名": "A", "数量": "5", "总价": "100"}]
    a1 = aggregate_items([normalize_row(r) for r in d1], "d1")
    a2 = aggregate_items([normalize_row(r) for r in d2], "d2")
    match_result = _match_aggregates(a1, "d1", a2, "d2")
    check(len(match_result["matched_items"]) == 1, "SKU 匹配 1 项")
    if match_result["matched_items"]:
        check(match_result["matched_items"][0]["confidence"] == 1.0, "置信度 = 1.0")

    # ── Test 6: 字段别名（品名 vs 中文品名）→ 兼容 ──
    print("\n--- Test 6: 字段别名兼容 ---")
    d1 = [{"品名": "蓝牙耳机", "规格型号": "BT-100", "数量": "10", "金额": "500"}]
    d2 = [{"中文品名": "蓝牙耳机", "型号": "BT-100", "数量": "10", "总价": "500"}]
    n1 = [normalize_row(r) for r in d1]
    n2 = [normalize_row(r) for r in d2]
    check(n1[0].get("中文品名") == "蓝牙耳机", "d1 品名 → 中文品名")
    check(n1[0].get("型号") == "BT-100", "d1 规格型号 → 型号")
    check(n1[0].get("总价") == "500", "d1 金额 → 总价")
    a1 = aggregate_items(n1, "d1")
    a2 = aggregate_items(n2, "d2")
    match_result = _match_aggregates(a1, "d1", a2, "d2")
    check(len(match_result["matched_items"]) == 1, "别名兼容匹配成功")

    # ── Test 7: HS 编码带点号 vs 无点号 ──
    print("\n--- Test 7: HS 编码点号归一 ---")
    d1 = [
        {
            "中文品名": "A",
            "型号": "X1",
            "HS编码": "8518.3000",
            "数量": "1",
            "总价": "10",
        }
    ]
    d2 = [
        {"中文品名": "A", "型号": "X1", "HS编码": "85183000", "数量": "1", "总价": "10"}
    ]
    a1 = aggregate_items([normalize_row(r) for r in d1], "d1")
    a2 = aggregate_items([normalize_row(r) for r in d2], "d2")
    check(len(a1) == 1 and len(a2) == 1, "双方各 1 项")
    pk1 = list(a1.keys())[0]
    pk2 = list(a2.keys())[0]
    check(pk1 == pk2, "HS 编码归一后键一致")

    # ── Test 8: Decimal 精确性 ──
    print("\n--- Test 8: Decimal 精度 ---")
    d1 = [{"中文品名": "X", "型号": "M1", "数量": "0.1", "总价": "0.03"}]
    d2 = [{"中文品名": "X", "型号": "M1", "数量": "0.1", "总价": "0.03"}]
    a1 = aggregate_items([normalize_row(r) for r in d1], "d1")
    a2 = aggregate_items([normalize_row(r) for r in d2], "d2")
    match_result = _match_aggregates(a1, "d1", a2, "d2")
    check(len(match_result["matched_items"]) == 1, "Decimal 精度匹配")
    check(
        not match_result["matched_items"][0]["has_significant_diff"],
        "Decimal 无浮点误差差异",
    )

    # ── Test 9: 实际数量差异 → 应标记 ──
    print("\n--- Test 9: 数量差异检测 ---")
    d1 = [{"中文品名": "A", "型号": "X1", "数量": "10", "总价": "100"}]
    d2 = [{"中文品名": "A", "型号": "X1", "数量": "12", "总价": "100"}]
    a1 = aggregate_items([normalize_row(r) for r in d1], "d1")
    a2 = aggregate_items([normalize_row(r) for r in d2], "d2")
    match_result = _match_aggregates(a1, "d1", a2, "d2")
    check(len(match_result["matched_items"]) == 1, "数量差异项仍匹配")
    check(match_result["matched_items"][0]["has_significant_diff"], "数量差异被标记")

    print(f"\n{'=' * 40}")
    print(f"  自测结果: {passed} 通过, {failed} 失败")
    print(f"{'=' * 40}")
    return failed == 0


# =====================================================================
#  CLI
# =====================================================================


def main():
    parser = argparse.ArgumentParser(
        description="单据一致性比较系统（按商品匹配）",
        formatter_class=argparse.RawTextHelpFormatter,
        epilog=(
            "示例:\n"
            "  python compare_documents.py invoice.csv packing_list.csv\n"
            "  python compare_documents.py --dir ./documents/\n"
            "  python compare_documents.py -o result.json inv.csv pkg.csv\n"
            "  python compare_documents.py --test\n"
        ),
    )
    parser.add_argument(
        "files",
        nargs="*",
        help="单据文件路径（支持 .csv / .json）",
    )
    parser.add_argument(
        "--output",
        "-o",
        default="comparison_report.json",
        help="输出 JSON 报告路径 (默认: comparison_report.json)",
    )
    parser.add_argument(
        "--dir",
        "-d",
        help="从指定目录加载所有 CSV/JSON 文件",
    )
    parser.add_argument(
        "--test",
        action="store_true",
        help="运行自测并退出",
    )
    args = parser.parse_args()

    # 自测模式
    if args.test:
        success = _run_tests()
        sys.exit(0 if success else 1)

    # 收集文件
    files: dict[str, str] = {}
    if args.dir:
        directory = args.dir
        if not os.path.isdir(directory):
            print(f"错误: '{directory}' 不是目录")
            sys.exit(1)
        for f in sorted(os.listdir(directory)):
            if f.lower().endswith((".csv", ".json")):
                name = os.path.splitext(f)[0]
                files[name] = os.path.join(directory, f)
        if not files:
            print(f"错误: 目录 '{directory}' 中未找到 .csv 或 .json 文件")
            sys.exit(1)
    elif args.files:
        for filepath in args.files:
            if not os.path.exists(filepath):
                print(f"错误: 文件 '{filepath}' 不存在")
                sys.exit(1)
            name = os.path.splitext(os.path.basename(filepath))[0]
            files[name] = filepath
    else:
        parser.print_help()
        sys.exit(1)

    # 至少需要两文件
    if len(files) < 2:
        print("错误: 至少需要 2 个文件进行比较")
        print(f"       当前提供了 {len(files)} 个: {list(files.keys())}")
        sys.exit(1)

    # 执行比较
    result = compare_documents(files)
    print_report(result)

    # 保存 JSON 输出
    output_path = args.output
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    print(f"\n报告已保存到: {output_path}")

    # 退出码：有差异/未匹配时返回 1
    if result["summary"]["differences_found"] > 0 or result["summary"]["unmatched"] > 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
