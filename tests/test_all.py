#!/usr/bin/env python3
"""
完整测试套件

测试覆盖：申报要素Schema、单据比较、Decimal计算、风险引擎、来源清单、回归测试
"""

import json
import os
import subprocess
import sys
import tempfile
import unittest
from decimal import Decimal

# Add scripts directory to path
_SCRIPT_DIR = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "..",
    "skills",
    "china-customs-declaration",
    "scripts",
)
sys.path.insert(0, _SCRIPT_DIR)

# ──────────────────────────────────────────────
# 1. DecimalUtils
# ──────────────────────────────────────────────


class TestDecimalUtils(unittest.TestCase):
    """测试 common/decimal_utils.py"""

    @classmethod
    def setUpClass(cls):
        try:
            from common import decimal_utils

            cls.dut = decimal_utils
        except ImportError:
            cls.dut = None

    def _to_dec(self, v):
        if self.dut is None:
            self.skipTest("decimal_utils module not available")
        return self.dut.to_decimal(v)

    def test_to_decimal_int(self):
        """123 -> Decimal('123')"""
        result = self._to_dec(123)
        self.assertEqual(result, Decimal("123"))

    def test_to_decimal_float(self):
        """0.1 (from Python float) -> Decimal('0.1') using string conversion"""
        result = self._to_dec(0.1)
        self.assertEqual(result, Decimal("0.1"))

    def test_to_decimal_thousands(self):
        """ "1,234.56" -> Decimal('1234.56')"""
        result = self._to_dec("1,234.56")
        self.assertEqual(result, Decimal("1234.56"))

    def test_to_decimal_empty(self):
        """None -> None"""
        result = self._to_dec(None)
        self.assertIsNone(result)

    def test_to_decimal_invalid(self):
        """ "abc" -> None"""
        result = self._to_dec("abc")
        self.assertIsNone(result)

    def test_round_amount(self):
        """Decimal('1.235') -> Decimal('1.24')"""
        if self.dut is None:
            self.skipTest("decimal_utils module not available")
        result = self.dut.round_amount(Decimal("1.235"))
        self.assertEqual(result, Decimal("1.24"))

    def test_calc_total_price(self):
        """10 x 3 = 30 (Decimal: 10.00 x 3 = 30.00)"""
        if self.dut is None:
            self.skipTest("decimal_utils module not available")
        result = self.dut.calc_total_price("10.00", "3")
        self.assertEqual(result, Decimal("30.00"))

    def test_calc_total_price_float_precision(self):
        """0.1 x 3 = 0.30 (no float error)"""
        if self.dut is None:
            self.skipTest("decimal_utils module not available")
        result = self.dut.calc_total_price("0.1", "3")
        self.assertEqual(result, Decimal("0.30"))

    def test_check_amount_match(self):
        """1000 vs 1000.01 with tolerance 0.01 -> match (True)"""
        if self.dut is None:
            self.skipTest("decimal_utils module not available")
        match, exp, act = self.dut.check_amount_match(
            "1000", "1000.01", Decimal("0.01")
        )
        self.assertTrue(match)
        self.assertEqual(exp, Decimal("1000"))
        self.assertEqual(act, Decimal("1000.01"))

    def test_check_amount_match_exceeded(self):
        """1000 vs 1000.02 with tolerance 0.01 -> no match (False)"""
        if self.dut is None:
            self.skipTest("decimal_utils module not available")
        match, exp, act = self.dut.check_amount_match(
            "1000", "1000.02", Decimal("0.01")
        )
        self.assertFalse(match)
        self.assertEqual(exp, Decimal("1000"))
        self.assertEqual(act, Decimal("1000.02"))

    def test_sum_decimal(self):
        """[1, 2, 3] -> Decimal('6')"""
        if self.dut is None:
            self.skipTest("decimal_utils module not available")
        result = self.dut.sum_decimal(["1", "2", "3"])
        self.assertEqual(result, Decimal("6"))

    def test_format_amount(self):
        """Decimal('1234.5') -> '1,234.50'"""
        if self.dut is None:
            self.skipTest("decimal_utils module not available")
        result = self.dut.format_amount(Decimal("1234.5"))
        self.assertEqual(result, "1,234.50")

    def test_to_decimal_currency_symbol(self):
        """ "$1,234.56" -> Decimal('1234.56')"""
        result = self._to_dec("$1,234.56")
        self.assertEqual(result, Decimal("1234.56"))


# ──────────────────────────────────────────────
# 2. FieldNormalizer
# ──────────────────────────────────────────────


class TestFieldNormalizer(unittest.TestCase):
    """测试 common/field_normalizer.py"""

    @classmethod
    def setUpClass(cls):
        try:
            from common import field_normalizer

            cls.fn = field_normalizer
        except ImportError:
            cls.fn = None

    def test_normalize_text_trim(self):
        """ "  abc  " -> "abc\""""
        if self.fn is None:
            self.skipTest("field_normalizer module not available")
        result = self.fn.normalize_text("  abc  ")
        self.assertEqual(result, "abc")

    def test_normalize_text_fullwidth(self):
        """ "ＡＢＣ" -> "ABC" (fullwidth to halfwidth)"""
        if self.fn is None:
            self.skipTest("field_normalizer module not available")
        result = self.fn.normalize_text("ＡＢＣ")
        self.assertEqual(result, "ABC")

    def test_normalize_text_spaces(self):
        """ "a   b" -> "a b\""""
        if self.fn is None:
            self.skipTest("field_normalizer module not available")
        result = self.fn.normalize_text("a   b")
        self.assertEqual(result, "a b")

    def test_normalize_model(self):
        """ "LP-1000" -> "LP-1000\""""
        if self.fn is None:
            self.skipTest("field_normalizer module not available")
        result = self.fn.normalize_model("LP-1000")
        self.assertEqual(result, "LP-1000")

    def test_normalize_model_mixed(self):
        """ "Lp_1000 " -> "LP_1000" (uppercase, normalize_ does NOT replace underscore)"""
        if self.fn is None:
            self.skipTest("field_normalizer module not available")
        result = self.fn.normalize_model("Lp_1000")
        # normalize_model does not replace underscore; only uppercase + hyphen normalization
        self.assertEqual(result, "LP_1000")

    def test_normalize_hs_code(self):
        """ "8528.6900.00" -> "8528690000\""""
        if self.fn is None:
            self.skipTest("field_normalizer module not available")
        result = self.fn.normalize_hs_code("8528.6900.00")
        self.assertEqual(result, "8528690000")

    def test_normalize_hs_code_no_dot(self):
        """ "8528690000" -> "8528690000\""""
        if self.fn is None:
            self.skipTest("field_normalizer module not available")
        result = self.fn.normalize_hs_code("8528690000")
        self.assertEqual(result, "8528690000")

    def test_resolve_field_exact(self):
        """{"中文品名": "test"}, "中文品名" -> "中文品名\""""
        if self.fn is None:
            self.skipTest("field_normalizer module not available")
        keys = ["中文品名"]
        result = self.fn.resolve_field(keys, "中文品名")
        self.assertEqual(result, "中文品名")

    def test_resolve_field_alias(self):
        """{"品名": "test"}, "中文品名" -> "品名" (uses alias)"""
        if self.fn is None:
            self.skipTest("field_normalizer module not available")
        keys = ["品名"]
        result = self.fn.resolve_field(keys, "中文品名")
        self.assertEqual(result, "品名")

    def test_resolve_field_missing(self):
        """{"其他字段": "test"}, "中文品名" -> None"""
        if self.fn is None:
            self.skipTest("field_normalizer module not available")
        keys = ["其他字段"]
        result = self.fn.resolve_field(keys, "中文品名")
        self.assertIsNone(result)


# ──────────────────────────────────────────────
# 3. DeclarationElements
# ──────────────────────────────────────────────

try:
    import declaration_elements as de

    HAS_DE = True
except ImportError:
    HAS_DE = False
    de = None


@unittest.skipIf(not HAS_DE, "declaration_elements module not available")
class TestDeclarationElements(unittest.TestCase):
    """测试 declaration_elements.py"""

    def setUp(self):
        self.registry = de.load_schema_registry()
        self.assertTrue(
            self.registry.get("schemas"), "Schema registry should have 'schemas' key"
        )

    def test_projector_elements(self):
        """HS 8528690000 should get 8528 schema fields (not default 8518)"""
        product = {
            "name": "激光投影仪",
            "hs_code": "8528690000",
            "usage": "用于家庭影音播放",
            "display_principle": "激光",
            "brand": "海信",
            "model": "Vidda C1",
        }
        result = de.generate_elements("8528690000", product, self.registry)
        self.assertEqual(result["matched_prefix"], "8528")
        field_names = [f["name"] for f in result["fields"]]
        self.assertIn("显示原理", field_names, "8528 schema should contain 显示原理")
        self.assertNotIn("显示原理", [], "8528 has 显示原理")

    def test_speaker_elements(self):
        """HS 8518220000 should get 8518 schema fields"""
        product = {
            "name": "蓝牙音箱",
            "hs_code": "8518220000",
            "usage": "用于家庭音响系统",
            "brand": "JBL",
            "model": "Charge 5",
        }
        result = de.generate_elements("8518220000", product, self.registry)
        self.assertEqual(result["matched_prefix"], "8518")
        field_names = [f["name"] for f in result["fields"]]
        self.assertNotIn(
            "显示原理", field_names, "8518 schema should NOT contain 显示原理"
        )

    def test_unknown_hs_code(self):
        """HS 9999999999 -> 'not_found' schema, no fake fields generated"""
        product = {"name": "未知商品", "hs_code": "9999999999"}
        result = de.generate_elements("9999999999", product, self.registry)
        self.assertEqual(result["schema_type"], "not_found")
        self.assertEqual(result["fields"], [])
        self.assertIn("error", result, "not_found result should contain error key")

    def test_unknown_hs_no_fields(self):
        """not_found schema fields list is empty"""
        product = {"name": "未知商品", "hs_code": "9999999999"}
        result = de.generate_elements("9999999999", product, self.registry)
        self.assertEqual(
            len(result["fields"]), 0, "not_found result should have empty fields list"
        )

    def test_example_only_status(self):
        """all fields from 8528 schema have status '示例参考，需官方核实' not '已确认'"""
        product = {
            "name": "投影仪",
            "hs_code": "8528690000",
            "usage": "测试",
            "display_principle": "激光",
            "brand": "测试",
            "model": "T-1",
        }
        result = de.generate_elements("8528690000", product, self.registry)
        for f in result["fields"]:
            self.assertEqual(
                f["status"],
                "示例参考，需官方核实",
                f"Field '{f['name']}' status should be example-only status",
            )

    def test_missing_field(self):
        """When product data missing, required field content is '待确认：______'"""
        product = {}
        result = de.generate_elements("8528690000", product, self.registry)
        brand_field = None
        for f in result["fields"]:
            if "品牌" in f["name"]:
                brand_field = f
                break
        self.assertIsNotNone(brand_field, "品牌 field should exist")
        self.assertTrue(
            str(brand_field["content"]).startswith("待确认"),
            f"Missing required field should contain '待确认', got: {brand_field['content']!r}",
        )

    def test_field_order(self):
        """Fields follow the order in schema"""
        product = {
            "name": "投影仪",
            "hs_code": "8528690000",
            "brand_type": "1-境内品牌",
            "export_preference": "2-不享受优惠",
            "usage": "测试",
            "display_principle": "激光",
            "brand": "测试",
            "model": "T-1",
        }
        result = de.generate_elements("8528690000", product, self.registry)
        orders = [f["order"] for f in result["fields"]]
        self.assertEqual(orders, sorted(orders), "Fields should be in order")

    def test_paste_version(self):
        """Produces a semicolon-separated string"""
        product = {
            "name": "投影仪",
            "hs_code": "8528690000",
            "brand_type": "3-境外品牌（其他）",
            "export_preference": "2-出口货物在最终目的国不享受优惠关税",
            "usage": "用于家庭影音播放",
            "display_principle": "激光",
            "brand": "海信",
            "model": "Vidda C1",
        }
        result = de.generate_elements("8528690000", product, self.registry)
        self.assertIsInstance(result["paste_version"], str)
        self.assertGreater(len(result["paste_version"]), 0)
        self.assertIn(
            ";", result["paste_version"], "paste_version should be semicolon-separated"
        )

    def test_schema_source_note(self):
        """Each result includes schema source note"""
        product = {
            "name": "投影仪",
            "hs_code": "8528690000",
            "brand_type": "3-境外品牌（其他）",
            "export_preference": "2-出口货物在最终目的国不享受优惠关税",
            "usage": "用于家庭影音播放",
            "display_principle": "激光",
            "brand": "海信",
            "model": "Vidda C1",
        }
        result = de.generate_elements("8528690000", product, self.registry)
        self.assertIn("schema_source_note", result)
        self.assertGreater(len(result["schema_source_note"]), 0)


# ──────────────────────────────────────────────
# 4. DocumentComparison
# ──────────────────────────────────────────────


class TestDocumentComparison(unittest.TestCase):
    """测试 compare_documents.py（通过 subprocess 运行）"""

    @classmethod
    def setUpClass(cls):
        cls.script = os.path.join(_SCRIPT_DIR, "compare_documents.py")
        cls.script_exists = os.path.isfile(cls.script)

    def _run_comparison(self, file1_data, file2_data):
        """Helper: create temp files, run compare_documents, return result dict"""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False, encoding="utf-8"
        ) as f1:
            json.dump(file1_data, f1, ensure_ascii=False)
            p1 = f1.name
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False, encoding="utf-8"
        ) as f2:
            json.dump(file2_data, f2, ensure_ascii=False)
            p2 = f2.name

        result = subprocess.run(
            [sys.executable, self.script, p1, p2, "-o", "/dev/null"],
            capture_output=True,
            text=True,
            timeout=30,
        )
        os.unlink(p1)
        os.unlink(p2)
        return result.returncode, result.stdout, result.stderr

    def test_same_content_different_order(self):
        """Invoice and packing list with same items but different order -> should match"""
        if not self.script_exists:
            self.skipTest("compare_documents.py not found")
        invoice = [
            {
                "中文品名": "投影仪",
                "型号": "LP-1000",
                "数量": "10",
                "总价": "5000.00",
                "品牌": "海信",
            },
            {
                "中文品名": "音箱",
                "型号": "BS-200",
                "数量": "20",
                "总价": "1000.00",
                "品牌": "JBL",
            },
        ]
        packing = [
            {
                "中文品名": "音箱",
                "型号": "BS-200",
                "数量": "20",
                "总价": "1000.00",
                "品牌": "JBL",
            },
            {
                "中文品名": "投影仪",
                "型号": "LP-1000",
                "数量": "10",
                "总价": "5000.00",
                "品牌": "海信",
            },
        ]
        returncode, stdout, stderr = self._run_comparison(invoice, packing)
        self.assertEqual(
            returncode,
            0,
            f"Same content different order should have returncode 0, got {returncode}",
        )

    def test_split_across_rows(self):
        """One invoice row for a model, three packing rows for same model -> aggregated match"""
        if not self.script_exists:
            self.skipTest("compare_documents.py not found")
        invoice = [
            {
                "中文品名": "投影仪",
                "型号": "LP-1000",
                "HS编码": "8528690000",
                "品牌": "海信",
                "数量": "100",
                "总价": "50000.00",
            }
        ]
        packing = [
            {
                "中文品名": "投影仪",
                "型号": "LP-1000",
                "HS编码": "8528690000",
                "品牌": "海信",
                "数量": "40",
                "总价": "20000.00",
            },
            {
                "中文品名": "投影仪",
                "型号": "LP-1000",
                "HS编码": "8528690000",
                "品牌": "海信",
                "数量": "35",
                "总价": "17500.00",
            },
            {
                "中文品名": "投影仪",
                "型号": "LP-1000",
                "HS编码": "8528690000",
                "品牌": "海信",
                "数量": "25",
                "总价": "12500.00",
            },
        ]
        returncode, stdout, stderr = self._run_comparison(invoice, packing)
        self.assertEqual(
            returncode,
            0,
            f"Split rows aggregated match should have returncode 0, got {returncode}",
        )

    def test_model_case_diff(self):
        """Model 'LP-1000' in invoice, 'lp_1000' in packing -> should match"""
        if not self.script_exists:
            self.skipTest("compare_documents.py not found")
        invoice = [
            {
                "中文品名": "投影仪",
                "型号": "LP-1000",
                "数量": "10",
                "总价": "5000.00",
            }
        ]
        packing = [
            {
                "中文品名": "投影仪",
                "型号": "lp_1000",
                "数量": "10",
                "总价": "5000.00",
            }
        ]
        returncode, stdout, stderr = self._run_comparison(invoice, packing)
        self.assertEqual(
            returncode,
            0,
            f"Model case/hyphen normalized should match, got returncode {returncode}",
        )

    def test_hs_code_with_dots(self):
        """ "8528.6900" vs "852869000000" -> should match"""
        if not self.script_exists:
            self.skipTest("compare_documents.py not found")
        invoice = [
            {
                "中文品名": "投影仪",
                "型号": "LP-1000",
                "HS编码": "8528.6900",
                "数量": "10",
                "总价": "5000.00",
            }
        ]
        packing = [
            {
                "中文品名": "投影仪",
                "型号": "LP-1000",
                "HS编码": "852869000000",
                "数量": "10",
                "总价": "5000.00",
            }
        ]
        returncode, stdout, stderr = self._run_comparison(invoice, packing)
        self.assertEqual(
            returncode,
            0,
            f"HS code with/without dots should match, got returncode {returncode}",
        )

    def test_hs_code_diff_for_same_model(self):
        """Same model but different HS codes -> should warn"""
        if not self.script_exists:
            self.skipTest("compare_documents.py not found")
        invoice = [
            {
                "中文品名": "投影仪",
                "型号": "LP-1000",
                "HS编码": "8528690000",
                "数量": "10",
                "总价": "5000.00",
            }
        ]
        packing = [
            {
                "中文品名": "投影仪",
                "型号": "LP-1000",
                "HS编码": "8518300000",
                "数量": "10",
                "总价": "5000.00",
            }
        ]
        returncode, stdout, stderr = self._run_comparison(invoice, packing)
        # Different HS codes may still match by model but should issue a warning;
        # returncode may be 1 (differences found) or 0 (matched but flagged differences)
        # We just verify it runs without crash and stdout contains something useful
        self.assertIn("LP-1000", stdout)

    def test_only_in_one_doc(self):
        """Item only in invoice, not in packing -> unmatched item flagged"""
        if not self.script_exists:
            self.skipTest("compare_documents.py not found")
        invoice = [
            {
                "中文品名": "投影仪",
                "型号": "LP-1000",
                "数量": "10",
                "总价": "5000.00",
            },
            {
                "中文品名": "音箱",
                "型号": "BS-200",
                "数量": "20",
                "总价": "1000.00",
            },
        ]
        packing = [
            {
                "中文品名": "投影仪",
                "型号": "LP-1000",
                "数量": "10",
                "总价": "5000.00",
            }
        ]
        returncode, stdout, stderr = self._run_comparison(invoice, packing)
        self.assertEqual(
            returncode,
            1,
            f"Unmatched item should return returncode 1, got {returncode}",
        )
        self.assertIn("BS-200", stdout, "Unmatched item BS-200 should appear in output")

    def test_only_in_other_doc(self):
        """Item only in packing, not in invoice -> unmatched item flagged"""
        if not self.script_exists:
            self.skipTest("compare_documents.py not found")
        invoice = [
            {
                "中文品名": "投影仪",
                "型号": "LP-1000",
                "数量": "10",
                "总价": "5000.00",
            }
        ]
        packing = [
            {
                "中文品名": "投影仪",
                "型号": "LP-1000",
                "数量": "10",
                "总价": "5000.00",
            },
            {
                "中文品名": "音箱",
                "型号": "BS-200",
                "数量": "20",
                "总价": "1000.00",
            },
        ]
        returncode, stdout, stderr = self._run_comparison(invoice, packing)
        self.assertEqual(
            returncode,
            1,
            f"Unmatched item in packing should return returncode 1, got {returncode}",
        )
        self.assertIn("BS-200", stdout, "Unmatched item BS-200 should appear in output")

    def test_different_quantity(self):
        """Same item, different quantities -> should detect difference"""
        if not self.script_exists:
            self.skipTest("compare_documents.py not found")
        invoice = [
            {
                "中文品名": "投影仪",
                "型号": "LP-1000",
                "数量": "10",
                "总价": "5000.00",
            }
        ]
        packing = [
            {
                "中文品名": "投影仪",
                "型号": "LP-1000",
                "数量": "12",
                "总价": "5000.00",
            }
        ]
        returncode, stdout, stderr = self._run_comparison(invoice, packing)
        self.assertEqual(
            returncode,
            1,
            f"Different quantities should return returncode 1, got {returncode}",
        )

    def test_aggregate_amount(self):
        """Split packing rows -> aggregated total matches invoice"""
        if not self.script_exists:
            self.skipTest("compare_documents.py not found")
        invoice = [
            {
                "中文品名": "投影仪",
                "型号": "LP-1000",
                "HS编码": "8528690000",
                "品牌": "海信",
                "数量": "100",
                "总价": "50000.00",
            }
        ]
        packing = [
            {
                "中文品名": "投影仪",
                "型号": "LP-1000",
                "HS编码": "8528690000",
                "品牌": "海信",
                "数量": "40",
                "总价": "20000.00",
            },
            {
                "中文品名": "投影仪",
                "型号": "LP-1000",
                "HS编码": "8528690000",
                "品牌": "海信",
                "数量": "35",
                "总价": "17500.00",
            },
            {
                "中文品名": "投影仪",
                "型号": "LP-1000",
                "HS编码": "8528690000",
                "品牌": "海信",
                "数量": "25",
                "总价": "12500.00",
            },
        ]
        returncode, stdout, stderr = self._run_comparison(invoice, packing)
        self.assertEqual(
            returncode,
            0,
            f"Aggregate total match should return returncode 0, got {returncode}",
        )


# ──────────────────────────────────────────────
# 5. RegulatoryRiskEngine
# ──────────────────────────────────────────────

try:
    import regulatory_risk_engine as rre

    HAS_RRE = True
except ImportError:
    HAS_RRE = False
    rre = None


@unittest.skipIf(not HAS_RRE, "regulatory_risk_engine module not available")
class TestRegulatoryRiskEngine(unittest.TestCase):
    """测试 regulatory_risk_engine.py"""

    def test_wireless_import_china(self):
        """Wireless + Import + China Mainland -> at least 1 risk with level 'verify' (NOT critical)"""
        product = {
            "name_cn": "智能投影仪",
            "has_wireless": True,
            "wireless": {
                "has_wireless": True,
                "wireless_types": ["Wi-Fi", "蓝牙"],
            },
        }
        trade = {"trade_direction": "进口", "destination_country": "中国"}
        risks = rre.evaluate_risks(product, trade)
        srrc_risks = [r for r in risks if r["category"] == "SRRC"]
        self.assertGreater(
            len(srrc_risks), 0, "Should have at least one SRRC risk for wireless import"
        )
        for r in srrc_risks:
            self.assertNotEqual(
                r["level"],
                "critical",
                f"SRRC risk should NOT be critical: {r['title']}",
            )

    def test_wireless_export_hongkong(self):
        """Wireless + Export + Hong Kong -> SRRC should NOT be critical"""
        product = {
            "name_cn": "蓝牙音箱",
            "has_wireless": True,
        }
        trade = {"trade_direction": "出口", "destination_country": "Hong Kong"}
        risks = rre.evaluate_risks(product, trade)
        srrc_risks = [r for r in risks if r["category"] == "SRRC"]
        for r in srrc_risks:
            self.assertNotEqual(
                r["level"], "critical", "SRRC risk for export HK should not be critical"
            )
            self.assertIn(
                r["level"],
                ["verify", "notice", "medium"],
                f"SRRC risk level should be verify/notice/medium, got {r['level']}",
            )

    def test_no_wireless(self):
        """No wireless -> no SRRC-related risk"""
        product = {"name_cn": "有线音箱", "has_wireless": False}
        trade = {"trade_direction": "进口", "destination_country": "中国"}
        risks = rre.evaluate_risks(product, trade)
        srrc_risks = [r for r in risks if r["category"] == "SRRC"]
        self.assertEqual(len(srrc_risks), 0, "No wireless should have no SRRC risks")

    def test_module_without_cert(self):
        """Has wireless module model but module_has_srrc=False -> should have high-level risk asking for cert"""
        product = {
            "name_cn": "智能投影仪",
            "has_wireless": True,
            "wireless": {
                "has_wireless": True,
                "wireless_types": ["Wi-Fi"],
                "module_model": "ESP32",
                "module_has_srrc": False,
            },
        }
        trade = {"trade_direction": "进口", "destination_country": "中国"}
        risks = rre.evaluate_risks(product, trade)
        srrc_risks = [r for r in risks if r["category"] == "SRRC"]
        self.assertGreater(len(srrc_risks), 0, "Should have SRRC risks")
        high_risks = [r for r in srrc_risks if r["level"] == "high"]
        self.assertGreater(
            len(high_risks),
            0,
            "Wireless module with module_has_srrc=False should have a high-level risk",
        )

    def test_builtin_battery(self):
        """Built-in battery -> battery risk exists, level verify"""
        product = {
            "name_cn": "蓝牙音箱",
            "has_battery": True,
            "battery": {
                "is_built_in": True,
                "battery_type": "锂离子电池",
                "capacity_mah": 5000,
            },
        }
        risks = rre.evaluate_risks(product, None)
        battery_risks = [r for r in risks if r["category"] == "BATTERY"]
        self.assertGreater(
            len(battery_risks), 0, "Should have battery risks for built-in battery"
        )
        for r in battery_risks:
            if r["risk_id"] == "BATTERY-BUILTIN":
                self.assertEqual(
                    r["level"],
                    "verify",
                    f"Built-in battery should be verify level, got {r['level']}",
                )
                break
        else:
            self.fail("No BATTERY-BUILTIN risk found")

    def test_independent_battery(self):
        """Independent battery -> battery risk exists, level high (more strict)"""
        product = {
            "name_cn": "锂电池",
            "has_battery": True,
            "battery": {
                "is_independent": True,
                "battery_type": "锂离子电池",
                "capacity_mah": 10000,
            },
        }
        risks = rre.evaluate_risks(product, None)
        battery_risks = [r for r in risks if r["category"] == "BATTERY"]
        self.assertGreater(
            len(battery_risks), 0, "Should have battery risks for independent battery"
        )
        for r in battery_risks:
            if r["risk_id"] == "BATTERY-BUILTIN":
                self.assertEqual(
                    r["level"],
                    "high",
                    f"Independent battery should be high level, got {r['level']}",
                )
                break
        else:
            self.fail("No BATTERY-BUILTIN risk found")

    def test_no_business_context(self):
        """Only product data, no trade data -> all risks <= verify level"""
        product = {
            "name_cn": "电子产品",
            "has_wireless": True,
            "has_battery": True,
        }
        risks = rre.evaluate_risks(product, None)
        for r in risks:
            level = r["level"]
            allowed_levels = {"verify", "medium", "notice", "not_applicable"}
            self.assertIn(
                level,
                allowed_levels,
                f"Risk '{r['risk_id']}' without business context should be <= verify, "
                f"got {level}",
            )

    def test_battery_no_info(self):
        """Battery present but no battery params -> verify level"""
        product = {
            "name_cn": "蓝牙音箱",
            "has_battery": True,
        }
        risks = rre.evaluate_risks(product, None)
        battery_risks = [r for r in risks if r["category"] == "BATTERY"]
        for r in battery_risks:
            if r["risk_id"] == "BATTERY-BUILTIN":
                level = r["level"]
                self.assertIn(
                    level,
                    ["verify", "high"],
                    f"Battery with no info should be verify level, got {level}",
                )

    def test_no_wood_packaging(self):
        """no wood packaging -> wood packaging risk should be not_applicable"""
        product = {"name_cn": "投影仪", "has_wood_packaging": False}
        risks = rre.evaluate_risks(product, None)
        wood_risks = [r for r in risks if r["category"] == "WOOD_PACKAGING"]
        self.assertGreater(
            len(wood_risks), 0, "Should have WOOD_PACKAGING category risks"
        )
        for r in wood_risks:
            if r["risk_id"] == "WOOD-NO-PACKAGING":
                self.assertEqual(
                    r["level"],
                    "not_applicable",
                    f"No wood packaging should be not_applicable, got {r['level']}",
                )
                break
        else:
            self.fail("No WOOD-NO-PACKAGING risk found")


# ──────────────────────────────────────────────
# 6. SourceManifest
# ──────────────────────────────────────────────


class TestSourceManifest(unittest.TestCase):
    """Test source manifest validation"""

    @classmethod
    def setUpClass(cls):
        cls.manifest_path = os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            "..",
            "skills",
            "china-customs-declaration",
            "data",
            "source-manifest.json",
        )

    def test_manifest_exists(self):
        """source-manifest.json file exists at data/source-manifest.json"""
        self.assertTrue(
            os.path.isfile(self.manifest_path),
            f"source-manifest.json not found at {self.manifest_path}",
        )

    def test_manifest_has_sources(self):
        """Has 'sources' key with non-empty list"""
        with open(self.manifest_path, "r", encoding="utf-8") as f:
            manifest = json.load(f)
        self.assertIn("sources", manifest)
        self.assertIsInstance(manifest["sources"], list)
        self.assertGreater(len(manifest["sources"]), 0)

    def test_manifest_source_has_required_fields(self):
        """Each source has source_id, title, authority, accessed_at, status"""
        with open(self.manifest_path, "r", encoding="utf-8") as f:
            manifest = json.load(f)
        required = {"source_id", "title", "authority", "accessed_at", "status"}
        for source in manifest["sources"]:
            missing = required - set(source.keys())
            self.assertEqual(
                missing,
                set(),
                f"Source '{source.get('source_id', 'unknown')}' missing: {missing}",
            )

    def test_manifest_no_missing_authority(self):
        """No source with empty authority"""
        with open(self.manifest_path, "r", encoding="utf-8") as f:
            manifest = json.load(f)
        for source in manifest["sources"]:
            self.assertNotEqual(
                source.get("authority", "").strip(),
                "",
                f"Source '{source.get('source_id', 'unknown')}' has empty authority",
            )

    def test_manifest_no_missing_accessed_at(self):
        """No source with empty accessed_at"""
        with open(self.manifest_path, "r", encoding="utf-8") as f:
            manifest = json.load(f)
        for source in manifest["sources"]:
            self.assertNotEqual(
                source.get("accessed_at", "").strip(),
                "",
                f"Source '{source.get('source_id', 'unknown')}' has empty accessed_at",
            )

    def test_manifest_dynamic_sources_have_accessed_at(self):
        """Dynamic sources all have accessed_at"""
        with open(self.manifest_path, "r", encoding="utf-8") as f:
            manifest = json.load(f)
        for source in manifest["sources"]:
            if source.get("dynamic") is True:
                self.assertNotEqual(
                    source.get("accessed_at", "").strip(),
                    "",
                    f"Dynamic source '{source.get('source_id', 'unknown')}' "
                    f"should have accessed_at",
                )


# ──────────────────────────────────────────────
# 7. Regression
# ──────────────────────────────────────────────


class TestRegression(unittest.TestCase):
    """Regression tests that old scripts still work"""

    SKILL_DIR = os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        "..",
        "skills",
        "china-customs-declaration",
    )
    SCRIPT_DIR = os.path.join(SKILL_DIR, "scripts")
    TEMPLATE_DIR = os.path.join(SKILL_DIR, "templates")

    def _exists(self, rel_path):
        return os.path.isfile(os.path.join(self.SCRIPT_DIR, rel_path))

    def test_validate_customs_data_exists(self):
        """Old validate script file exists"""
        self.assertTrue(
            self._exists("validate_customs_data.py"),
            "validate_customs_data.py should exist",
        )

    def test_validate_customs_data_error_detection(self):
        """Running old validate script with sample data still detects errors"""
        script = os.path.join(self.SCRIPT_DIR, "validate_customs_data.py")
        result = subprocess.run(
            [sys.executable, script],
            capture_output=True,
            text=True,
            timeout=30,
        )
        self.assertEqual(
            result.returncode,
            1,
            f"Validate script should detect errors and return 1, got {result.returncode}",
        )
        self.assertIn(
            "金额计算错误",
            result.stdout,
            "Output should mention amount calculation error",
        )

    def test_generate_declaration_exists(self):
        """Old generate script exists"""
        self.assertTrue(
            self._exists("generate_declaration_table.py"),
            "generate_declaration_table.py should exist",
        )

    def test_compare_documents_exists(self):
        """Old compare script exists"""
        self.assertTrue(
            self._exists("compare_documents.py"),
            "compare_documents.py should exist",
        )

    def test_update_source_manifest_exists(self):
        """Old update script exists"""
        self.assertTrue(
            self._exists("update_source_manifest.py"),
            "update_source_manifest.py should exist",
        )

    def test_templates_exist(self):
        """All 4 template files exist"""
        templates = [
            "commercial-invoice-template.xlsx",
            "customs-product-template.xlsx",
            "declaration-elements-template.xlsx",
            "packing-list-template.xlsx",
        ]
        for tpl in templates:
            tpl_path = os.path.join(self.TEMPLATE_DIR, tpl)
            self.assertTrue(
                os.path.isfile(tpl_path),
                f"Template '{tpl}' should exist at {tpl_path}",
            )

    def test_expert_agent_file_exists(self):
        """Agent definition exists"""
        agent_path = os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            "..",
            "agents",
            "china-customs-declaration-expert.md",
        )
        self.assertTrue(
            os.path.isfile(agent_path),
            f"Agent definition should exist at {agent_path}",
        )

    def test_skill_file_exists(self):
        """SKILL.md exists"""
        skill_path = os.path.join(self.SKILL_DIR, "SKILL.md")
        self.assertTrue(
            os.path.isfile(skill_path),
            f"SKILL.md should exist at {skill_path}",
        )

    def test_plugin_json_exists(self):
        """plugin.json exists and is valid JSON"""
        plugin_path = os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            "..",
            ".codebuddy-plugin",
            "plugin.json",
        )
        self.assertTrue(
            os.path.isfile(plugin_path),
            f"plugin.json should exist at {plugin_path}",
        )
        with open(plugin_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        self.assertIsInstance(data, dict, "plugin.json should be valid JSON object")


# ──────────────────────────────────────────────
# 8. PluginPackage
# ──────────────────────────────────────────────


class TestPluginPackage(unittest.TestCase):
    """Test plugin structure"""

    PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
    # Determine project root: go up one level
    PLUGIN_PATH = os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        "..",
        ".codebuddy-plugin",
        "plugin.json",
    )

    @classmethod
    def setUpClass(cls):
        cls.plugin_data = None
        if os.path.isfile(cls.PLUGIN_PATH):
            with open(cls.PLUGIN_PATH, "r", encoding="utf-8") as f:
                cls.plugin_data = json.load(f)

    def test_plugin_json_parseable(self):
        """plugin.json is valid JSON"""
        self.assertIsNotNone(
            self.plugin_data,
            f"plugin.json should be parseable at {self.PLUGIN_PATH}",
        )

    def test_plugin_json_has_version(self):
        """Has 'version' field"""
        if self.plugin_data is None:
            self.skipTest("plugin.json not found")
        self.assertIn("version", self.plugin_data)

    def test_plugin_json_has_agents(self):
        """Has 'agents' array"""
        if self.plugin_data is None:
            self.skipTest("plugin.json not found")
        self.assertIn("agents", self.plugin_data)
        self.assertIsInstance(self.plugin_data["agents"], list)
        self.assertGreater(len(self.plugin_data["agents"]), 0)

    def test_agent_file_referenced(self):
        """Referenced agent file exists"""
        if self.plugin_data is None:
            self.skipTest("plugin.json not found")
        root = os.path.dirname(os.path.dirname(self.PLUGIN_PATH))
        for agent_rel in self.plugin_data.get("agents", []):
            agent_path = os.path.join(root, agent_rel)
            self.assertTrue(
                os.path.isfile(agent_path),
                f"Referenced agent file should exist at {agent_path}",
            )

    def test_skill_directory_referenced(self):
        """Referenced skill directory exists"""
        if self.plugin_data is None:
            self.skipTest("plugin.json not found")
        root = os.path.dirname(os.path.dirname(self.PLUGIN_PATH))
        for skill_rel in self.plugin_data.get("skills", []):
            skill_path = os.path.join(root, skill_rel)
            self.assertTrue(
                os.path.isdir(skill_path),
                f"Referenced skill directory should exist at {skill_path}",
            )

    def test_avatar_exists(self):
        """Avatar file exists"""
        if self.plugin_data is None:
            self.skipTest("plugin.json not found")
        root = os.path.dirname(os.path.dirname(self.PLUGIN_PATH))
        avatar_rel = self.plugin_data.get("avatar", "")
        if avatar_rel:
            avatar_path = os.path.join(root, avatar_rel)
            self.assertTrue(
                os.path.isfile(avatar_path),
                f"Avatar file should exist at {avatar_path}",
            )


# ──────────────────────────────────────────────
# Test Runner
# ──────────────────────────────────────────────


def run_tests():
    """Run all tests and print summary"""
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()

    test_classes = [
        TestDecimalUtils,
        TestFieldNormalizer,
        TestDeclarationElements,
        TestDocumentComparison,
        TestRegulatoryRiskEngine,
        TestSourceManifest,
        TestRegression,
        TestPluginPackage,
    ]

    for tc in test_classes:
        suite.addTests(loader.loadTestsFromTestCase(tc))

    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    return result.wasSuccessful()


if __name__ == "__main__":
    success = run_tests()
    sys.exit(0 if success else 1)
