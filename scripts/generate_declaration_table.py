#!/usr/bin/env python3
"""
from __future__ import annotations
报关资料表格生成脚本
从商品数据生成：
  - 商品资料汇总表
  - 规范申报要素表
  - 商业发票草稿
  - 装箱单草稿
  - 待确认问题清单
  - 风险问题清单

支持格式：XLSX, CSV, JSON
"""

import csv
import json
import os
import sys
from datetime import datetime
from typing import Any


def generate_summary_table(data: list[dict]) -> list[dict]:
    """生成商品资料汇总表"""
    return [
        {
            "项号": i,
            "中文品名": row.get("中文品名", ""),
            "英文品名": row.get("英文品名", ""),
            "品牌": row.get("品牌", ""),
            "型号": row.get("型号", ""),
            "HS编码": row.get("HS编码", ""),
            "用途": row.get("用途", ""),
            "功能": row.get("功能", ""),
            "工作原理": row.get("工作原理", ""),
            "材质": row.get("材质", ""),
            "技术参数": row.get("技术参数", ""),
            "是否整机": row.get("是否整机", ""),
            "是否含无线": row.get("是否含无线", ""),
            "是否含电池": row.get("是否含电池", ""),
            "数量": row.get("数量", ""),
            "单位": row.get("单位", ""),
            "单价": row.get("单价", ""),
            "总价": row.get("总价", ""),
            "币种": row.get("币种", ""),
            "原产国": row.get("原产国", ""),
        }
        for i, row in enumerate(data, 1)
    ]


def generate_invoice(data: list[dict]) -> list[dict]:
    """生成商业发票草稿"""
    today = datetime.now().strftime("%Y-%m-%d")
    return [
        {
            "项号": i,
            "中文品名": row.get("中文品名", ""),
            "英文品名": row.get("英文品名", ""),
            "品牌型号": f"{row.get('品牌', '')} {row.get('型号', '')}".strip(),
            "HS编码": row.get("HS编码", ""),
            "数量": row.get("数量", ""),
            "单位": row.get("单位", ""),
            "单价": row.get("单价", ""),
            "总价": row.get("总价", ""),
            "币种": row.get("币种", "USD"),
            "原产国": row.get("原产国", ""),
        }
        for i, row in enumerate(data, 1)
    ], {"发票日期": today}


def generate_packing_list(data: list[dict]) -> list[dict]:
    """生成装箱单草稿"""
    return [
        {
            "箱号": i,
            "品名": row.get("中文品名", ""),
            "型号": row.get("型号", ""),
            "数量": row.get("数量", ""),
            "包装单位": row.get("包装单位", row.get("单位", "")),
            "净重(kg)": row.get("净重", ""),
            "毛重(kg)": row.get("毛重", ""),
            "包装尺寸(cm)": row.get("包装尺寸", ""),
            "体积(m³)": row.get("体积", ""),
        }
        for i, row in enumerate(data, 1)
    ]


def generate_declaration_elements(data: list[dict]) -> list[dict]:
    """生成申报要素明细表"""
    elements = []
    for i, row in enumerate(data, 1):
        elements.append(
            {
                "项号": i,
                "HS编码": row.get("HS编码", ""),
                "品名": row.get("中文品名", ""),
                "申报字段": "品牌类型",
                "申报内容": row.get("品牌类型", "待确认"),
                "信息来源": row.get("信息来源", ""),
                "状态": row.get("品牌类型状态", "待确认"),
            }
        )
        elements.append(
            {
                "项号": i,
                "HS编码": row.get("HS编码", ""),
                "品名": row.get("中文品名", ""),
                "申报字段": "出口享惠情况",
                "申报内容": row.get("出口享惠情况", "待确认"),
                "信息来源": "",
                "状态": "待确认",
            }
        )
        elements.append(
            {
                "项号": i,
                "HS编码": row.get("HS编码", ""),
                "品名": row.get("中文品名", ""),
                "申报字段": "用途",
                "申报内容": row.get("用途", "待确认"),
                "信息来源": row.get("信息来源", ""),
                "状态": "已确认" if row.get("用途") else "待确认",
            }
        )
        elements.append(
            {
                "项号": i,
                "HS编码": row.get("HS编码", ""),
                "品名": row.get("中文品名", ""),
                "申报字段": "品牌",
                "申报内容": row.get("品牌", "待确认"),
                "信息来源": row.get("信息来源", ""),
                "状态": "已确认" if row.get("品牌") else "待确认",
            }
        )
        elements.append(
            {
                "项号": i,
                "HS编码": row.get("HS编码", ""),
                "品名": row.get("中文品名", ""),
                "申报字段": "型号",
                "申报内容": row.get("型号", "待确认"),
                "信息来源": row.get("信息来源", ""),
                "状态": "已确认" if row.get("型号") else "待确认",
            }
        )
        elements.append(
            {
                "项号": i,
                "HS编码": row.get("HS编码", ""),
                "品名": row.get("中文品名", ""),
                "申报字段": "其他",
                "申报内容": row.get("其他", "待确认"),
                "信息来源": row.get("信息来源", ""),
                "状态": "待确认",
            }
        )
    return elements


def generate_pending_questions(data: list[dict]) -> list[str]:
    """生成待确认问题清单"""
    questions = []
    for i, row in enumerate(data, 1):
        prefix = f"第{i}项 ({row.get('中文品名', '')}): "
        if not row.get("用途"):
            questions.append(f"{prefix}产品的主要用途是什么（家用/商用/工业等）？")
        if not row.get("功能"):
            questions.append(f"{prefix}产品的主要功能是什么？")
        if not row.get("工作原理"):
            questions.append(f"{prefix}产品的工作原理是什么？")
        if not row.get("是否含无线"):
            questions.append(f"{prefix}产品是否含WiFi、蓝牙等无线功能？")
        if not row.get("是否含电池"):
            questions.append(f"{prefix}产品是否含锂电池？如有，请提供容量（mAh/Wh）")
        if not row.get("是否整机"):
            questions.append(f"{prefix}产品是整机还是零件/附件？")
        if not row.get("原产国"):
            questions.append(f"{prefix}产品的原产国是哪里？")
    return questions


def detect_risks(data: list[dict]) -> list[dict]:
    """检测风险项目"""
    risks = []
    for i, row in enumerate(data, 1):
        prefix = f"第{i}项"
        # 含无线功能但未提示SRRC
        if str(row.get("是否含无线", "")).strip() in ("是", "yes", "Yes"):
            risks.append(
                {
                    "风险等级": "严重",
                    "问题位置": prefix,
                    "问题说明": "含无线功能，需确认是否取得SRRC型号核准证",
                    "修改建议": "确认SRRC认证状态，如未取得需办理",
                }
            )
        # 含电池但未提示
        if str(row.get("是否含电池", "")).strip() in ("是", "yes", "Yes"):
            risks.append(
                {
                    "风险等级": "严重",
                    "问题位置": prefix,
                    "问题说明": "含电池，需确认UN38.3/MSDS/危包证及CCC认证状态",
                    "修改建议": "准备UN38.3报告、MSDS、危包证，确认CCC证书",
                }
            )
        # 品名过宽
        pname = str(row.get("中文品名", "")).strip()
        if pname in ("电子产品", "设备", "配件", "零件", "机器", "仪器"):
            risks.append(
                {
                    "风险等级": "中等",
                    "问题位置": prefix,
                    "问题说明": f"品名'{pname}'过于宽泛，建议具体化",
                    "修改建议": "改为具体品名，如'激光投影仪'、'蓝牙音箱'等",
                }
            )
        # 缺少型号
        if not str(row.get("型号", "")).strip():
            risks.append(
                {
                    "风险等级": "中等",
                    "问题位置": prefix,
                    "问题说明": "型号缺失，可能影响申报",
                    "修改建议": "补充产品型号",
                }
            )
    return risks


def save_as_xlsx(tables: dict[str, Any], output_path: str) -> None:
    """保存为Excel文件（多sheet）"""
    try:
        from openpyxl import Workbook
    except ImportError:
        print("需要安装openpyxl: pip install openpyxl")
        return

    wb = Workbook()
    wb.remove(wb.active)

    for sheet_name, table_data in tables.items():
        if not table_data or len(table_data) == 0:
            continue
        ws = wb.create_sheet(title=sheet_name[:31])  # Excel sheet name limit

        # 写表头
        if isinstance(table_data, list):
            headers = list(table_data[0].keys())
            ws.append(headers)
            for row in table_data:
                ws.append([row.get(h, "") for h in headers])
        elif isinstance(table_data, dict):
            for key, value in table_data.items():
                ws.append([key, value])

    wb.save(output_path)
    print(f"Excel已保存到: {output_path}")


def save_as_csv(data: list[dict], output_path: str) -> None:
    """保存为CSV"""
    if not data:
        print(f"数据为空，跳过: {output_path}")
        return
    with open(output_path, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=data[0].keys())
        writer.writeheader()
        writer.writerows(data)
    print(f"CSV已保存到: {output_path}")


def save_as_json(data: Any, output_path: str) -> None:
    """保存为JSON"""
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"JSON已保存到: {output_path}")


# 示例数据
SAMPLE_DATA = [
    {
        "中文品名": "家用激光投影仪",
        "英文品名": "Home Laser Projector",
        "品牌": "BrandA",
        "型号": "LP-1000",
        "HS编码": "8528690000",
        "用途": "家庭影音娱乐",
        "功能": "视频投射",
        "工作原理": "DLP数字光处理，��光光源",
        "材质": "塑料+金属+光学玻璃",
        "技术参数": "4K, 2000流明",
        "是否整机": "是",
        "是否含无线": "是",
        "是否含电池": "否",
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
        "用途": "便携音乐播放",
        "功能": "音频播放",
        "工作原理": "电动式扬声器",
        "材质": "塑料+金属网罩",
        "技术参数": "20W, 蓝牙5.2",
        "是否整机": "是",
        "是否含无线": "是",
        "是否含电池": "是",
        "数量": "20",
        "单位": "台",
        "单价": "50.00",
        "总价": "1000.00",
        "币种": "USD",
        "原产国": "中国",
        "毛重": "80.0",
        "净重": "70.0",
    },
]


if __name__ == "__main__":
    # 加载数据
    if len(sys.argv) > 1:
        filepath = sys.argv[1]
        if not os.path.exists(filepath):
            print(f"错误: 文件'{filepath}'不存在")
            sys.exit(1)
        with open(filepath, "r", encoding="utf-8") as f:
            if filepath.endswith(".json"):
                data = json.load(f)
            elif filepath.endswith(".csv"):
                data = []
                reader = csv.DictReader(f)
                for row in reader:
                    data.append(row)
            else:
                print("错误: 仅支持JSON和CSV格式")
                sys.exit(1)
    else:
        print("使用示例数据生成表格...\n")
        data = SAMPLE_DATA

    # 确定输出目录和格式
    output_dir = sys.argv[2] if len(sys.argv) > 2 else "./output"
    output_format = sys.argv[3] if len(sys.argv) > 3 else "xlsx"
    os.makedirs(output_dir, exist_ok=True)

    # 生成各类表格
    summary = generate_summary_table(data)
    invoice_info = generate_invoice(data)
    if isinstance(invoice_info, tuple):
        invoice, invoice_meta = invoice_info
    else:
        invoice, invoice_meta = invoice_info, {}
    packing = generate_packing_list(data)
    elements = generate_declaration_elements(data)
    questions = generate_pending_questions(data)
    risks = detect_risks(data)

    # 构建输出
    tables = {
        "商品资料汇总": summary,
        "商业发票": invoice,
        "装箱单": packing,
        "申报要素明细": elements,
    }

    if output_format == "xlsx":
        output_path = os.path.join(output_dir, "declaration_tables.xlsx")
        save_as_xlsx(tables, output_path)
    elif output_format == "csv":
        for name, table in tables.items():
            fname = f"{name}.csv"
            save_as_csv(table, os.path.join(output_dir, fname))
    elif output_format == "json":
        output_path = os.path.join(output_dir, "declaration_tables.json")
        save_as_json(tables, output_path)

    # 待确认问题
    print("\n" + "=" * 60)
    print("待确认问题清单")
    print("=" * 60)
    for q in questions:
        print(f"  - {q}")
    print(f"\n共 {len(questions)} 个待确认问题")

    # 风险问题
    print("\n" + "=" * 60)
    print("风险问题清单")
    print("=" * 60)
    for r in risks:
        print(f"  [{r['风险等级']}] {r['问题位置']}: {r['问题说明']}")
    print(f"\n共 {len(risks)} 个风险项")

    # 保存问题和风险
    problems = {"待确认问题": questions, "风险问题": risks}
    save_as_json(problems, os.path.join(output_dir, "issues.json"))
