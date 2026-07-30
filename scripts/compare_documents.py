#!/usr/bin/env python3
"""
多份单据一致性比对脚本
比较：合同、发票、箱单、商品资料、申报资料
检查字段：品名、型号、数量、单价、总价、毛重、净重、件数、币种、原产国
"""

import csv
import json
import os
import sys


def load_document(filepath: str) -> list[dict]:
    """加载单据文件"""
    if not os.path.exists(filepath):
        return []
    with open(filepath, "r", encoding="utf-8-sig") as f:
        if filepath.endswith(".json"):
            return json.load(f)
        elif filepath.endswith(".csv"):
            reader = csv.DictReader(f)
            return list(reader)
        else:
            raise ValueError(f"不支持的文件格式: {filepath}")


def compare_field(
    doc1: list[dict], doc2: list[dict], field: str, doc1_name: str, doc2_name: str
) -> list[dict]:
    """逐行比较两个单据的指定字段"""
    differences = []
    max_rows = max(len(doc1), len(doc2))

    for i in range(max_rows):
        val1 = ""
        val2 = ""
        item1 = ""
        item2 = ""

        if i < len(doc1):
            row1 = doc1[i]
            val1 = str(row1.get(field, "")).strip()
            item1 = row1.get("中文品名", row1.get("品名", f"第{i + 1}行"))

        if i < len(doc2):
            row2 = doc2[i]
            val2 = str(row2.get(field, "")).strip()
            item2 = row2.get("中文品名", row2.get("品名", f"第{i + 1}行"))

        if val1 != val2:
            differences.append(
                {
                    "行号": i + 1,
                    "字段": field,
                    "商品": item1 or item2,
                    f"{doc1_name}": val1 or "(缺失)",
                    f"{doc2_name}": val2 or "(缺失)",
                }
            )

    # 行数不一致
    if len(doc1) != len(doc2):
        differences.append(
            {
                "行号": "-",
                "字段": "(行数)",
                "商品": "",
                f"{doc1_name}": f"{len(doc1)}行",
                f"{doc2_name}": f"{len(doc2)}行",
            }
        )

    return differences


def check_calculations(doc: list[dict], doc_name: str) -> list[dict]:
    """校验单据内部计算"""
    issues = []
    total_from_items = 0.0
    total_net = 0.0
    total_gross = 0.0

    for i, row in enumerate(doc, 1):
        # 单价×数量=总价
        try:
            up = float(row.get("单价", 0))
            qty = float(row.get("数量", 0))
            tp = float(row.get("总价", 0))
            expected = round(up * qty, 2)
            if abs(expected - tp) > 0.01:
                issues.append(
                    {
                        "单据": doc_name,
                        "行号": i,
                        "问题": f"金额计算错误: 单价({up})×数量({qty})={expected}, 总价={tp}",
                    }
                )
            total_from_items += tp
        except (ValueError, TypeError):
            pass

        # 毛重≥净重
        try:
            g = float(row.get("毛重", -1))
            n = float(row.get("净重", -1))
            if g >= 0 and n >= 0 and g < n:
                issues.append(
                    {
                        "单据": doc_name,
                        "行号": i,
                        "问题": f"毛重({g})<净重({n})",
                    }
                )
            if g > 0:
                total_gross += g
            if n > 0:
                total_net += n
        except (ValueError, TypeError):
            pass

    # 总毛重≥总净重
    if total_gross > 0 and total_net > 0 and total_gross < total_net:
        issues.append(
            {
                "单据": doc_name,
                "行号": "合计",
                "问题": f"总毛重({total_gross})<总净重({total_net})",
            }
        )

    return issues


def compare_documents(files: dict[str, str]) -> dict:
    """
    比较多份单据

    Args:
        files: {单据名称: 文件路径} 的字典
               例: {"合同": "contract.csv", "发票": "invoice.csv", ...}

    Returns:
        比较结果
    """
    docs: dict[str, list] = {}
    for name, path in files.items():
        docs[name] = load_document(path)
        if not docs[name]:
            print(f"警告: '{name}'文件为空或不存在 ({path})")

    compare_fields = [
        ("品名", "中文品名"),
        ("型号", "型号"),
        ("数量", "数量"),
        ("单价", "单价"),
        ("总价", "总价"),
        ("币种", "币种"),
        ("原产国", "原产国"),
    ]

    all_differences: list[dict] = []
    all_calc_issues: list[dict] = []

    doc_names = list(docs.keys())

    # 两两比较
    for i in range(len(doc_names)):
        for j in range(i + 1, len(doc_names)):
            name1, name2 = doc_names[i], doc_names[j]
            if not docs[name1] or not docs[name2]:
                continue

            for field, alt_field in compare_fields:
                # 尝试主字段名，如果不存在则用备选
                has_field = False
                for doc_data in [docs[name1], docs[name2]]:
                    if (
                        doc_data
                        and field in doc_data[0]
                        or doc_data
                        and alt_field in doc_data[0]
                    ):
                        has_field = True

                if has_field:
                    actual_field = field
                    if (
                        docs[name1]
                        and field not in docs[name1][0]
                        and alt_field in docs[name1][0]
                    ):
                        actual_field = alt_field
                    diffs = compare_field(
                        docs[name1], docs[name2], actual_field, name1, name2
                    )
                    all_differences.extend(diffs)

    # 计算校验
    for name, doc_data in docs.items():
        if doc_data:
            issues = check_calculations(doc_data, name)
            all_calc_issues.extend(issues)

    return {
        "field_differences": all_differences,
        "calculation_issues": all_calc_issues,
        "summary": {
            "compared_documents": doc_names,
            "total_field_diffs": len(all_differences),
            "total_calc_issues": len(all_calc_issues),
        },
    }


def print_report(result: dict) -> None:
    """打印比较报告"""
    print("=" * 60)
    print("单据一致性比较报告")
    print("=" * 60)

    summary = result["summary"]
    print(f"\n比较的单据: {', '.join(summary['compared_documents'])}")

    if result["field_differences"]:
        print(f"\n❌ 字段差异 ({len(result['field_differences'])}处):")
        print("-" * 60)
        for diff in result["field_differences"]:
            srcs = [k for k in diff if k not in ("行号", "字段", "商品")]
            print(f"  行{diff['行号']} | {diff['字段']} | {diff['商品']}")
            for src in srcs:
                print(f"    {src}: {diff[src]}")
            print()
    else:
        print("\n✅ 未发现字段差异")

    if result["calculation_issues"]:
        print(f"\n❌ 计算问题 ({len(result['calculation_issues'])}处):")
        for issue in result["calculation_issues"]:
            print(f"  [{issue['单据']}] 行{issue['行号']}: {issue['问题']}")
    else:
        print("\n✅ 未发现计算问题")

    print("=" * 60)


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("用法: python compare_documents.py <文件1> <文件2> [文件3 ...]")
        print("      或 python compare_documents.py --dir <目录>")
        print()
        print("示例: python compare_documents.py invoice.csv packing.csv contract.json")
        print("      python compare_documents.py --dir ./documents/")
        sys.exit(1)

    files: dict[str, str] = {}

    if sys.argv[1] == "--dir":
        directory = sys.argv[2]
        if not os.path.isdir(directory):
            print(f"错误: '{directory}'不是目录")
            sys.exit(1)
        for f in os.listdir(directory):
            if f.endswith((".csv", ".json")):
                name = os.path.splitext(f)[0]
                files[name] = os.path.join(directory, f)
    else:
        for filepath in sys.argv[1:]:
            if not os.path.exists(filepath):
                print(f"错误: 文件'{filepath}'不存在")
                continue
            name = os.path.splitext(os.path.basename(filepath))[0]
            files[name] = filepath

    if len(files) < 2:
        print("错误: 至少需要2个文件进行比较")
        sys.exit(1)

    result = compare_documents(files)
    print_report(result)

    # 保存结果
    output_path = "comparison_report.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    print(f"\n报告已保存到: {output_path}")

    # 返回退出码
    if (
        result["summary"]["total_field_diffs"] > 0
        or result["summary"]["total_calc_issues"] > 0
    ):
        sys.exit(1)
