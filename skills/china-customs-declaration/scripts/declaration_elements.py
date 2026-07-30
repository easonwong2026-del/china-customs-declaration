#!/usr/bin/env python3
"""
规范申报要素整理系统

根据申报要素 Schema 生成规范申报要素，
支持 HS编码逐级匹配、Schema 状态区分、多版本输出。
"""

import csv
import json
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

SCHEMA_DIR = Path(__file__).parent.parent / "data" / "declaration-elements"
SCHEMA_REGISTRY = SCHEMA_DIR / "schema.json"
QUERY_DATE = datetime.now().strftime("%Y-%m-%d")

# ──────────────────────────────────────────────
# Schema Registry
# ──────────────────────────────────────────────


def load_schema_registry() -> dict:
    """加载 schema.json 注册表"""
    try:
        with open(SCHEMA_REGISTRY, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"错误：找不到注册表文件 {SCHEMA_REGISTRY}", file=sys.stderr)
        return {
            "registry_version": "0.0.0",
            "last_updated": "",
            "source_note": "",
            "schemas": {},
        }


# ──────────────────────────────────────────────
# HS Code Matching
# ──────────────────────────────────────────────


def find_schema(hs_code: str, registry: dict) -> tuple[Optional[dict], str, str]:
    """
    按优先级匹配 HS 编码对应的 Schema：
    1. 精确10位
    2. 8位前缀
    3. 6位前缀
    4. 4位前缀
    5. 未找到

    返回 (schema_data, schema_type, matched_prefix)
    """
    clean_code = hs_code.replace(".", "").replace(" ", "").strip()
    schemas = registry.get("schemas", {})

    # 按长度降序遍历前缀尝试匹配
    prefixes_to_try = _generate_prefixes(clean_code)
    for prefix in prefixes_to_try:
        if prefix in schemas:
            schema_info = schemas[prefix]
            schema_type = schema_info.get("type", "not_found")
            schema_data = load_schema_by_prefix(prefix)
            return schema_data, schema_type, prefix

    return None, "not_found", ""


def _generate_prefixes(hs_code: str) -> list[str]:
    """生成用于匹配的前缀列表（从长到短）"""
    code = hs_code.replace(".", "").replace(" ", "").strip()
    prefixes = set()
    # 尝试 10 位
    if len(code) >= 10:
        prefixes.add(code[:10])
    # 尝试 8 位
    if len(code) >= 8:
        prefixes.add(code[:8])
    # 尝试 6 位
    if len(code) >= 6:
        prefixes.add(code[:6])
    # 尝试 4 位
    if len(code) >= 4:
        prefixes.add(code[:4])
    return sorted(prefixes, key=len, reverse=True)


def load_schema_by_prefix(prefix: str) -> Optional[dict]:
    """根据 HS 前缀加载对应的 Schema JSON 文件"""
    schema_file = SCHEMA_DIR / f"{prefix}.json"
    try:
        with open(schema_file, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return None


def match_hs_prefix(hs_code: str, prefix: str) -> bool:
    """检查清洗后的 HS 编码是否以给定前缀开头"""
    clean_code = hs_code.replace(".", "").replace(" ", "").strip()
    clean_prefix = prefix.replace(".", "").replace(" ", "").strip()
    return clean_code.startswith(clean_prefix)


# ──────────────────────────────────────────────
# Status Helpers
# ──────────────────────────────────────────────


def _resolve_verification_status(schema_type: str) -> str:
    """根据 Schema 类型返回验证状态"""
    mapping = {
        "official_confirmed": "已确认",
        "internal_historical": "推断",
        "example_only": "待确认",
        "not_found": "待官方核实",
    }
    return mapping.get(schema_type, "待官方核实")


def _resolve_field_status(schema_type: str) -> str:
    """根据 Schema 类型返回字段状态"""
    mapping = {
        "official_confirmed": "已确认",
        "internal_historical": "推断",
        "example_only": "示例参考，需官方核实",
        "not_found": "未找到",
    }
    return mapping.get(schema_type, "未找到")


def _resolve_source(schema_type: str, schema_source: str, registry_entry: dict) -> str:
    """生成来源描述"""
    if schema_type == "not_found":
        return "未匹配到任何已加载的 Schema"
    if schema_type == "example_only":
        return f"示例参考数据：{schema_source}"
    if schema_type == "official_confirmed":
        return f"官方核定数据：{schema_source}"
    if schema_type == "internal_historical":
        return f"历史推断数据：{schema_source}"
    return schema_source


# ──────────────────────────────────────────────
# Element Generation
# ──────────────────────────────────────────────


def _extract_field_value(field_def: dict, product_data: dict) -> str:
    """从 product_data 中提取字段值"""
    source_keys = field_def.get("source_keys", [])
    # 尝试按 source_keys 从 product_data 中取值
    for key in source_keys:
        value = product_data.get(key)
        if value is not None and str(value).strip():
            return str(value).strip()
    # 尝试按别名匹配
    name = field_def.get("name", "")
    if name in product_data:
        val = product_data[name]
        if val is not None and str(val).strip():
            return str(val).strip()
    return ""


def generate_elements(
    hs_code: str,
    product_data: dict,
    schema_registry: Optional[dict] = None,
) -> dict:
    """为产品生成规范申报要素"""
    if schema_registry is None:
        schema_registry = load_schema_registry()

    source_note = schema_registry.get("source_note", "")

    schema_data, schema_type, matched_prefix = find_schema(hs_code, schema_registry)

    # ── 未找到 Schema ──
    if schema_type == "not_found":
        return {
            "hs_code": hs_code,
            "matched_prefix": "",
            "schema_type": "not_found",
            "schema_version": "",
            "verification_status": "待官方核实",
            "source": "未匹配到任何已加载的 Schema",
            "fields": [],
            "paste_version": "",
            "detail_version": [],
            "pending_questions": ["请查询该 HS 编码的法定申报要素"],
            "schema_source_note": source_note,
            "error": "当前未加载该 HS 编码的有效申报要素定义",
            "recommendation": "请通过单一窗口或当年《规范申报目录》查询该编码的法定申报要素",
        }

    # ── 找到 Schema ──
    registry_schema = schema_registry.get("schemas", {}).get(matched_prefix, {})
    schema_source = schema_data.get("source", "") if schema_data else ""
    schema_version = schema_data.get("version", "") if schema_data else ""
    description = registry_schema.get("description", "")

    verification_status = _resolve_verification_status(schema_type)
    field_status = _resolve_field_status(schema_type)
    source = _resolve_source(schema_type, schema_source, registry_schema)

    fields = []
    field_defs = schema_data.get("fields", []) if schema_data else []

    for field_def in field_defs:
        name = field_def.get("name", "")
        order = field_def.get("order", 0)
        required = field_def.get("required", False)

        raw_value = _extract_field_value(field_def, product_data)
        content = raw_value or ("待确认：______" if required else "")

        field_entry = {
            "name": name,
            "order": order,
            "required": required,
            "content": content,
            "source": field_def.get("source_keys", name),
            "status": field_status,
        }
        fields.append(field_entry)

    # 构建 paste 版本
    paste_parts = []
    for f in fields:
        val = f["content"]
        if val:
            paste_parts.append(val)
    paste_version = ";".join(paste_parts)

    # 构建 detail 版本
    detail_version = []
    for f in fields:
        detail_version.append(
            {
                "申报要素": f["name"],
                "填报内容": f["content"],
                "是否必填": "是" if f["required"] else "否",
                "状态": f["status"],
            }
        )

    # 收集未填写的必填项
    pending_questions = []
    for f in fields:
        if f["required"] and (not f["content"] or f["content"].startswith("待确认：")):
            pending_questions.append(f"缺少必填要素「{f['name']}」")

    # 针对 example_only 的提示
    if schema_type == "example_only":
        pending_questions.insert(
            0,
            f"当前使用的为示例参考 Schema（HS{matched_prefix} - {description}），"
            f"请核实后替换为官方《规范申报目录》版本",
        )

    return {
        "hs_code": hs_code,
        "matched_prefix": matched_prefix,
        "schema_type": schema_type,
        "schema_version": schema_version,
        "verification_status": verification_status,
        "source": source,
        "fields": fields,
        "paste_version": paste_version,
        "detail_version": detail_version,
        "pending_questions": pending_questions,
        "schema_source_note": source_note,
    }


def generate_batch_elements(
    products: list[dict],
    registry: Optional[dict] = None,
) -> list[dict]:
    """批量处理产品列表"""
    results = []
    for product in products:
        hs_code = product.get("hs_code", product.get("hsCode", ""))
        if not hs_code:
            continue
        result = generate_elements(hs_code, product, registry)
        result["product_name"] = product.get("name", product.get("product_name", ""))
        results.append(result)
    return results


# ──────────────────────────────────────────────
# Output / Reporting
# ──────────────────────────────────────────────


def print_detail_report(results: list[dict]) -> None:
    """打印详细报告"""
    separator = "=" * 78
    sub_separator = "-" * 78

    for result in results:
        print(separator)
        name = result.get("product_name", "")
        hs = result["hs_code"]
        print(f"  产品：{name}" if name else f"  HS编码：{hs}")
        print(f"  HS编码：{hs}  |  匹配前缀：{result['matched_prefix']}")
        print(
            f"  Schema类型：{result['schema_type']}  |  验证状态：{result['verification_status']}"
        )
        print(f"  来源：{result['source']}")
        print(sub_separator)

        if result["schema_type"] == "not_found":
            print(f"  ⚠  {result.get('error', '')}")
            print(f"  建议：{result.get('recommendation', '')}")
            continue

        fields = result.get("fields", [])
        if fields:
            print(f"  {'要素名称':<30} {'填报内容':<30} {'状态':<16}")
            print(f"  {'-' * 28} {'-' * 28} {'-' * 14}")
            for f in fields:
                name = f["name"]
                content = f["content"]
                status = f["status"]
                print(f"  {name:<28} {content:<28} {status:<14}")

        print(f"\n  粘贴版（分号分隔）：{result['paste_version']}")

        pending = result.get("pending_questions", [])
        if pending:
            print("\n  待确认事项：")
            for q in pending:
                print(f"    - {q}")

    if results:
        print(separator)
        source_note = results[0].get("schema_source_note", "")
        if source_note:
            print(f"数据来源说明：{source_note}")

    # 汇总
    print(separator)
    print(f"  共处理 {len(results)} 个产品")
    not_found = [r for r in results if r["schema_type"] == "not_found"]
    example = [r for r in results if r["schema_type"] == "example_only"]
    if not_found:
        print(f"  未找到 Schema：{len(not_found)} 个")
    if example:
        print(f"  使用示例 Schema：{len(example)} 个（需官方核实）")
    print(separator)


def _save_json_output(results: list[dict], output_path: str) -> None:
    """保存 JSON 格式输出"""
    data = {
        "query_date": QUERY_DATE,
        "generated_by": "规范申报要素整理系统",
        "results": results,
    }
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"输出已保存至：{output_path}")


def _save_csv_output(results: list[dict], output_path: str) -> None:
    """保存 CSV 格式输出"""
    with open(output_path, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(
            ["产品名称", "HS编码", "匹配前缀", "Schema类型", "验证状态", "粘贴版"]
        )
        for r in results:
            writer.writerow(
                [
                    r.get("product_name", ""),
                    r["hs_code"],
                    r["matched_prefix"],
                    r["schema_type"],
                    r["verification_status"],
                    r["paste_version"],
                ]
            )
    print(f"输出已保存至：{output_path}")


# ──────────────────────────────────────────────
# Data Loading
# ──────────────────────────────────────────────


def _load_input_file(file_path: str) -> list[dict]:
    """从 JSON 或 CSV 文件加载产品数据"""
    ext = Path(file_path).suffix.lower()
    if ext == ".json":
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, list):
            return data
        if isinstance(data, dict):
            return data.get("products", data.get("items", [data]))
        return []
    elif ext == ".csv":
        products = []
        with open(file_path, "r", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            for row in reader:
                products.append(row)
        return products
    else:
        print(f"错误：不支持的文件格式 '{ext}'（仅支持 JSON/CSV）", file=sys.stderr)
        sys.exit(1)


# ──────────────────────────────────────────────
# CLI
# ──────────────────────────────────────────────


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="规范申报要素整理系统")
    parser.add_argument("input_file", nargs="?", help="输入文件（JSON/CSV）")
    parser.add_argument("-o", "--output", help="输出文件路径")
    parser.add_argument("-f", "--format", choices=["json", "csv"], default="json")
    args = parser.parse_args()

    registry = load_schema_registry()

    if args.input_file:
        if not os.path.isfile(args.input_file):
            print(f"错误：找不到输入文件 '{args.input_file}'", file=sys.stderr)
            sys.exit(1)
        products = _load_input_file(args.input_file)
        if not products:
            print("警告：输入文件中无有效产品数据", file=sys.stderr)
            sys.exit(1)
        results = generate_batch_elements(products, registry)

        if args.output:
            if args.format == "json":
                _save_json_output(results, args.output)
            else:
                _save_csv_output(results, args.output)
        else:
            print_detail_report(results)

        # 检查是否有错误
        has_error = any(r["schema_type"] == "not_found" for r in results)
        sys.exit(1 if has_error else 0)

    # ── 无输入文件：使用示例数据 ──
    sample_data = [
        {
            "name": "激光投影仪",
            "hs_code": "8528690000",
            "brand_type": "3-境外品牌（其他）",
            "export_preference": "2-出口货物在最终目的国不享受优惠关税",
            "usage": "用于家庭影音播放",
            "display_principle": "激光",
            "brand": "海信",
            "model": "Vidda C1",
        },
        {
            "name": "蓝牙音箱",
            "hs_code": "8518220000",
            "brand_type": "3-境外品牌（其他）",
            "export_preference": "1-出口货物在最终目的国可享受优惠关税",
            "usage": "用于家庭音响系统",
            "brand": "JBL",
            "model": "Charge 5",
        },
    ]
    results = generate_batch_elements(sample_data, registry)
    print_detail_report(results)
    sys.exit(0)


SAMPLE_DATA = [
    {
        "name": "激光投影仪",
        "hs_code": "8528690000",
        "brand_type": "3-境外品牌（其他）",
        "export_preference": "2-出口货物在最终目的国不享受优惠关税",
        "usage": "用于家庭影音播放",
        "display_principle": "激光",
        "brand": "海信",
        "model": "Vidda C1",
    },
    {
        "name": "蓝牙音箱",
        "hs_code": "8518220000",
        "brand_type": "3-境外品牌（其他）",
        "export_preference": "1-出口货物在最终目的国可享受优惠关税",
        "usage": "用于家庭音响系统",
        "brand": "JBL",
        "model": "Charge 5",
    },
]

if __name__ == "__main__":
    main()
