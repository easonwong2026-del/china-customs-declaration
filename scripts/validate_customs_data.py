#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
海关报关资料校验脚本
检查：必填字段缺失、数量错误、金额计算错误、重量异常、
      HS编码格式、型号重复、申报要素一致性等问题。
"""

import json
import csv
import sys
import os
from typing import Any


def validate_field(value: Any, field_name: str, row_num: int) -> list[str]:
    """检查单个字段是否为空"""
    errors = []
    if value is None or str(value).strip() == "":
        errors.append(f"第{row_num}行: 必填字段'{field_name}'为空")
    return errors


def validate_hs_code(code: str, row_num: int) -> list[str]:
    """校验HS编码格式（10位数字）"""
    errors = []
    code_str = str(code).strip().replace(".", "").replace(" ", "")
    if not code_str:
        errors.append(f"第{row_num}行: HS编码为空")
        return errors
    if not code_str.isdigit():
        errors.append(f"第{row_num}行: HS编码'{code}'包含非数字字符")
        return errors
    if len(code_str) != 10:
        errors.append(
            f"第{row_num}行: HS编码'{code}'长度不是10位（当前{len(code_str)}位）"
        )
    return errors


def validate_quantity(quantity: Any, row_num: int) -> list[str]:
    """校验数量"""
    errors = []
    if quantity is None or str(quantity).strip() == "":
        errors.append(f"第{row_num}行: 数量为空")
        return errors
    try:
        qty = float(quantity)
        if qty <= 0:
            errors.append(f"第{row_num}行: 数量必须大于0（当前{qty}）")
    except (ValueError, TypeError):
        errors.append(f"第{row_num}行: 数量'{quantity}'不是有效数字")
    return errors


def validate_amount(unit_price: Any, quantity: Any, total_price: Any,
                    row_num: int, tolerance: float = 0.01) -> list[str]:
    """校验单价×数量=总价"""
    errors = []
    try:
        up = float(unit_price) if unit_price else 0
        qty = float(quantity) if quantity else 0
        tp = float(total_price) if total_price else 0
        expected = round(up * qty, 2)
        if abs(expected - tp) > tolerance:
            errors.append(
                f"第{row_num}行: 金额计算错误 - "
                f"单价({up})×数量({qty})={expected}, 但总价为{tp}"
            )
    except (ValueError, TypeError):
        errors.append(f"第{row_num}行: 金额字段不是有效数字")
    return errors


def validate_weight(gross: Any, net: Any, row_num: int) -> list[str]:
    """校验毛重≥净重"""
    errors = []
    try:
        g = float(gross) if gross else 0
        n = float(net) if net else 0
        if g <= 0 or n <= 0:
            errors.append(f"第{row_num}行: 重量必须大于0（毛重{g}, 净重{n}）")
        if g < n:
            errors.append(
                f"第{row_num}行: 毛重({g})小于净重({n})，物理不可能"
            )
    except (ValueError, TypeError):
        errors.append(f"第{row_num}行: 重量字段不是有效数字")
    return errors


def validate_customs_data(data: list[dict[str, Any]]) -> dict:
    """
    对海关商品数据进行全面校验

    Args:
        data: 商品数据列表，每项为字典

    Returns:
        校验结果字典，含 errors, warnings, summary
    """
    errors: list[str] = []
    warnings: list[str] = []

    if not data:
        return {
            "errors": ["数据为空"],
            "warnings": [],
            "summary": {"total_rows": 0, "error_count": 1, "warning_count": 0}
        }

    # 必填字段检查
    required_fields = [
        "中文品名", "品牌", "型号", "数量", "单位",
        "单价", "总价", "币种", "HS编码", "原产国"
    ]

    hs_code_map: dict[str, int] = {}  # HS编码 -> 行号
    model_hs_map: dict[str, set] = {}  # 型号 -> {HS编码}
    total_amount = 0.0
    total_net_weight = 0.0
    total_gross_weight = 0.0
    currencies: set[str] = set()

    for i, row in enumerate(data, 1):
        # 必填字段
        for field in required_fields:
            errors.extend(validate_field(row.get(field), field, i))

        # HS编码格式
        hs = row.get("HS编码", "")
        errors.extend(validate_hs_code(hs, i))

        # HS编码重复检查
        hs_clean = str(hs).strip().replace(".", "")
        if hs_clean in hs_code_map:
            prev_row = hs_code_map[hs_clean]
            warnings.append(
                f"第{i}行与第{prev_row}行使用相同HS编码'{hs}'，请确认是否应合并或使用不同子目"
            )
        else:
            hs_code_map[hs_clean] = i

        # 型号-HS编码映射（检查同型号是否不同编码）
        model = str(row.get("型号", "")).strip()
        if model and model not in ("无", "N/A", "-"):
            if model not in model_hs_map:
                model_hs_map[model] = set()
            model_hs_map[model].add(hs_clean)

        # 数量和金额校验
        errors.extend(validate_quantity(row.get("数量"), i))
        errors.extend(validate_amount(
            row.get("单价"), row.get("数量"), row.get("总价"), i
        ))

        # 收集币种
        currency = str(row.get("币种", "")).strip()
        if currency:
            currencies.add(currency)

        # 金额累计
        try:
            total_amount += float(row.get("总价", 0))
        except (ValueError, TypeError):
            pass

        # 重量校验（如有）
        if "毛重" in row and "净重" in row:
            errors.extend(validate_weight(row.get("毛重"), row.get("净重"), i))
            try:
                total_gross_weight += float(row.get("毛重", 0))
                total_net_weight += float(row.get("净重", 0))
            except (ValueError, TypeError):
                pass

    # 同型号不同编码检查
    for model_name, codes in model_hs_map.items():
        if len(codes) > 1:
            warnings.append(
                f"型号'{model_name}'使用了{len(codes)}个不同的HS编码: {codes}"
            )

    # 币种一致性检查
    if len(currencies) > 1:
        warnings.append(f"存在多种币种: {currencies}，请确认是否正确")

    summary = {
        "total_rows": len(data),
        "error_count": len(errors),
        "warning_count": len(warnings),
        "total_amount": round(total_amount, 2),
        "currencies": list(currencies),
        "unique_hs_codes": len(hs_code_map),
        "total_gross_weight": round(total_gross_weight, 2),
        "total_net_weight": round(total_net_weight, 2),
    }

    if total_gross_weight > 0 and total_gross_weight < total_net_weight:
        errors.append(
            f"总计毛重({total_gross_weight})小于总计净重({total_net_weight})"
        )

    return {"errors": errors, "warnings": warnings, "summary": summary}


def print_report(result: dict) -> None:
    """打印格式化的校验报告"""
    print("=" * 60)
    print("海关报关资料校验报告")
    print("=" * 60)

    summary = result["summary"]
    print(f"\n数据概览:")
    print(f"  总行数: {summary['total_rows']}")
    print(f"  总金额: {summary['total_amount']}")
    print(f"  币种: {summary['currencies']}")
    print(f"  不同HS编码数: {summary['unique_hs_codes']}")
    if summary.get("total_gross_weight"):
        print(f"  总毛重: {summary['total_gross_weight']} kg")
        print(f"  总净重: {summary['total_net_weight']} kg")

    print(f"\n校验结果: {summary['error_count']}个错误, "
          f"{summary['warning_count']}个警告")

    if result["errors"]:
        print(f"\n❌ 错误 ({len(result['errors'])}):")
        for err in result["errors"]:
            print(f"  {err}")

    if result["warnings"]:
        print(f"\n⚠️  警告 ({len(result['warnings'])}):")
        for warn in result["warnings"]:
            print(f"  {warn}")

    if not result["errors"] and not result["warnings"]:
        print("\n✅ 所有校验通过！")

    print("=" * 60)


def load_data_from_csv(filepath: str) -> list[dict]:
    """从CSV加载数据"""
    data = []
    with open(filepath, "r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            data.append(row)
    return data


def load_data_from_json(filepath: str) -> list[dict]:
    """从JSON加载数据"""
    with open(filepath, "r", encoding="utf-8") as f:
        return json.load(f)


# 示例测试数据
SAMPLE_DATA = [
    {
        "中文品名": "激光投影仪",
        "英文品名": "Laser Projector",
        "品牌": "BrandA",
        "型号": "LP-1000",
        "HS编码": "8528690000",
        "数量": "10",
        "单位": "台",
        "单价": "500.00",
        "总价": "5000.00",
        "币种": "USD",
        "原产国": "日本",
        "毛重": "150.0",
        "净重": "120.0",
    },
    {
        "中文品名": "蓝牙音箱",
        "英文品名": "Bluetooth Speaker",
        "品牌": "BrandB",
        "型号": "BS-200",
        "HS编码": "8518220000",
        "数量": "20",
        "单位": "台",
        "单价": "50.00",
        "总价": "1000.00",
        "币种": "USD",
        "原产国": "中国",
        "毛重": "80.0",
        "净重": "70.0",
    },
    # 错误示例：总价计算错误
    {
        "中文品名": "电源适配器",
        "英文品名": "Power Adapter",
        "品牌": "BrandC",
        "型号": "PA-50",
        "HS编码": "8504401499",
        "数量": "100",
        "单位": "个",
        "单价": "10.00",
        "总价": "900.00",  # 应该是1000.00
        "币种": "USD",
        "原产国": "越南",
        "毛重": "50.0",
        "净重": "45.0",
    },
    # 错误示例：毛重<净重
    {
        "中文品名": "回音壁",
        "英文品名": "Soundbar",
        "品牌": "BrandD",
        "型号": "SB-300",
        "HS编码": "8518220000",
        "数量": "5",
        "单位": "台",
        "单价": "200.00",
        "总价": "1000.00",
        "币种": "USD",
        "原产国": "中国",
        "毛重": "45.0",  # 小于净重
        "净重": "50.0",
    },
]


if __name__ == "__main__":
    if len(sys.argv) > 1:
        filepath = sys.argv[1]
        if not os.path.exists(filepath):
            print(f"错误: 文件'{filepath}'不存在")
            sys.exit(1)
        if filepath.endswith(".csv"):
            data = load_data_from_csv(filepath)
        elif filepath.endswith(".json"):
            data = load_data_from_json(filepath)
        else:
            print("错误: 仅支持CSV和JSON格式")
            sys.exit(1)
    else:
        print("使用示例数据运行校验...\n")
        data = SAMPLE_DATA

    result = validate_customs_data(data)
    print_report(result)

    # 返回退出码
    if result["errors"]:
        sys.exit(1)
