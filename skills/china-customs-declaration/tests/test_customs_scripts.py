#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
海关报关辅助脚本测试套件
测试全部scripts/下的Python脚本
"""

import sys
import os
import json
import subprocess

# 添加scripts目录到路径
SCRIPT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "scripts")
sys.path.insert(0, SCRIPT_DIR)


def run_script(script_name: str, args: list[str] = None) -> tuple[int, str, str]:
    """运行脚本并返回返回码、stdout、stderr"""
    script_path = os.path.join(SCRIPT_DIR, script_name)
    cmd = [sys.executable, script_path] + (args or [])
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    return result.returncode, result.stdout, result.stderr


def test_validate_customs_data():
    """测试 validate_customs_data.py"""
    print("=" * 60)
    print("测试: validate_customs_data.py")
    print("=" * 60)

    # 使用内置示例数据运行
    returncode, stdout, stderr = run_script("validate_customs_data.py")
    print(stdout)
    if stderr:
        print("STDERR:", stderr)

    # 应该检测到示例数据中的错误（金额错误和毛重<净重）
    # 所以期望返回非零退出码
    assert returncode == 1, f"期望返回码1（有错误），实际{returncode}"
    assert "金额计算错误" in stdout, "应检测到金额计算错误"
    assert "毛重" in stdout and "净重" in stdout, "应检测到重量异常"

    print("✅ validate_customs_data.py 通过\n")
    return True


def test_generate_declaration_table():
    """测试 generate_declaration_table.py"""
    print("=" * 60)
    print("测试: generate_declaration_table.py")
    print("=" * 60)

    # 创建测试输出目录
    test_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "test_data")
    test_output = os.path.join(os.path.dirname(os.path.abspath(__file__)), "test_output")
    os.makedirs(test_dir, exist_ok=True)
    os.makedirs(test_output, exist_ok=True)

    # 创建测试数据JSON文件
    test_data = [
        {"中文品名": "测试投影仪", "英文品名": "Test Projector", "品牌": "TB", "型号": "TP-1",
         "HS编码": "8528690000", "用途": "家用", "功能": "投影", "工作原理": "DLP",
         "材质": "塑料", "技术参数": "1080p", "是否整机": "是", "是否含无线": "是",
         "是否含电池": "否", "数量": "5", "单位": "台", "单价": "300.00", "总价": "1500.00",
         "币种": "USD", "原产国": "中国", "毛重": "25.0", "净重": "20.0"}
    ]
    test_data_path = os.path.join(test_dir, "test_products.json")
    with open(test_data_path, "w", encoding="utf-8") as f:
        json.dump(test_data, f, ensure_ascii=False)

    returncode, stdout, stderr = run_script(
        "generate_declaration_table.py",
        [test_data_path, test_output, "json"]
    )
    print(stdout)

    # 检查输出文件
    json_path = os.path.join(test_output, "declaration_tables.json")
    issues_path = os.path.join(test_output, "issues.json")
    assert os.path.exists(json_path), f"JSON输出未生成: {json_path}"
    assert os.path.exists(issues_path), f"问题清单未生成: {issues_path}"

    # 验证JSON内容
    with open(json_path, "r", encoding="utf-8") as f:
        tables = json.load(f)
    assert "商品资料汇总" in tables, "应含商品资料汇总"
    assert "商业发票" in tables, "应含商业发票"
    assert "装箱单" in tables, "应含装箱单"

    with open(issues_path, "r", encoding="utf-8") as f:
        issues = json.load(f)
    assert "待确认问题" in issues, "应含待确认问题"
    assert "风险问题" in issues, "应含风险问题清单"
    assert len(issues["风险问题"]) > 0, "示例数据应检测到风险项"

    print("✅ generate_declaration_table.py 通过\n")
    return True


def test_compare_documents():
    """测试 compare_documents.py"""
    print("=" * 60)
    print("测试: compare_documents.py")
    print("=" * 60)

    test_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "test_data")
    os.makedirs(test_dir, exist_ok=True)

    # 创建测试用发票和箱单（故意设置不一致）
    invoice_data = [
        {
            "中文品名": "投影仪",
            "型号": "LP-1000",
            "数量": "10",
            "单价": "500.00",
            "总价": "5000.00",
            "币种": "USD",
            "原产国": "日本",
            "毛重": "150.0",
            "净重": "120.0",
        },
        {
            "中文品名": "音箱",
            "型号": "BS-200",
            "数量": "20",
            "单价": "50.00",
            "总价": "1000.00",
            "币种": "USD",
            "原产国": "中国",
            "毛重": "80.0",
            "净重": "70.0",
        },
    ]

    packing_data = [
        {
            "中文品名": "投影仪",
            "型号": "LP-1000",
            "数量": "10",
            "单价": "500.00",
            "总价": "5000.00",
            "币种": "USD",
            "原产国": "日本",
            "毛重": "120.0",  # 故意不一致（原来是150）
            "净重": "120.0",
        },
        {
            "中文品名": "音箱",
            "型号": "BS-200",
            "数量": "15",  # 故意不一致（原来是20）
            "单价": "50.00",
            "总价": "1000.00",
            "币种": "USD",
            "原产国": "中国",
            "毛重": "80.0",
            "净重": "70.0",
        },
    ]

    invoice_path = os.path.join(test_dir, "invoice.json")
    packing_path = os.path.join(test_dir, "packing.json")

    with open(invoice_path, "w", encoding="utf-8") as f:
        json.dump(invoice_data, f, ensure_ascii=False, indent=2)
    with open(packing_path, "w", encoding="utf-8") as f:
        json.dump(packing_data, f, ensure_ascii=False, indent=2)

    returncode, stdout, stderr = run_script(
        "compare_documents.py",
        [invoice_path, packing_path]
    )
    print(stdout)

    # 应检测到差异
    assert returncode == 1, f"期望返回码1（有差异），实际{returncode}"
    assert "差异" in stdout or "difference" in stdout.lower(), "应检测到字段差异"

    print("✅ compare_documents.py 通过\n")
    return True


def test_update_source_manifest():
    """测试 update_source_manifest.py"""
    print("=" * 60)
    print("测试: update_source_manifest.py")
    print("=" * 60)

    # 使用研究项目中的source-manifest.json
    manifest_path = os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        "..", "..", "china-customs-declaration-project", "research", "source-manifest.json"
    )

    if not os.path.exists(manifest_path):
        print("⚠️  source-manifest.json 未找到，跳过部分测试")
        return True

    # 测试 --status
    returncode, stdout, stderr = run_script(
        "update_source_manifest.py",
        ["--manifest", manifest_path, "--status"]
    )
    print(stdout)
    assert returncode == 0, f"status命令应成功，实际返回{returncode}"

    # 测试 --remind
    returncode, stdout, stderr = run_script(
        "update_source_manifest.py",
        ["--manifest", manifest_path, "--remind"]
    )
    print(stdout)
    assert returncode == 0, f"remind命令应成功"

    print("✅ update_source_manifest.py 通过\n")
    return True


def test_script_exists():
    """验证所有脚本文件存在"""
    print("=" * 60)
    print("检查脚本文件完整性")
    print("=" * 60)

    required_scripts = [
        "validate_customs_data.py",
        "generate_declaration_table.py",
        "compare_documents.py",
        "update_source_manifest.py",
    ]

    for script in required_scripts:
        path = os.path.join(SCRIPT_DIR, script)
        assert os.path.exists(path), f"缺少脚本: {script}"
        print(f"  ✓ {script}")

    print("✅ 脚本文件齐全\n")
    return True


if __name__ == "__main__":
    print("\n🔬 海关报关辅助脚本测试套件\n")

    results = []

    try:
        results.append(("脚本完整性", test_script_exists()))
    except Exception as e:
        print(f"❌ 脚本完整性检查失败: {e}")
        results.append(("脚本完整性", False))

    try:
        results.append(("validate_customs_data", test_validate_customs_data()))
    except Exception as e:
        print(f"❌ validate_customs_data 测试失败: {e}")
        results.append(("validate_customs_data", False))

    try:
        results.append(("generate_declaration_table", test_generate_declaration_table()))
    except Exception as e:
        print(f"❌ generate_declaration_table 测试失败: {e}")
        results.append(("generate_declaration_table", False))

    try:
        results.append(("compare_documents", test_compare_documents()))
    except Exception as e:
        print(f"❌ compare_documents 测试失败: {e}")
        results.append(("compare_documents", False))

    try:
        results.append(("update_source_manifest", test_update_source_manifest()))
    except Exception as e:
        print(f"❌ update_source_manifest 测试失败: {e}")
        results.append(("update_source_manifest", False))

    # 汇总
    print("\n" + "=" * 60)
    print("测试结果汇总")
    print("=" * 60)
    passed = 0
    failed = 0
    for name, ok in results:
        status = "✅ PASS" if ok else "❌ FAIL"
        print(f"  {status}: {name}")
        if ok:
            passed += 1
        else:
            failed += 1

    print(f"\n通过: {passed}/{len(results)}, 失败: {failed}/{len(results)}")

    if failed > 0:
        sys.exit(1)
    else:
        print("\n🎉 所有测试通过！")
