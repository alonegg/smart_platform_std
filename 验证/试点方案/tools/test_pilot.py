"""WP6 正例、反例和空输入；unittest 与 pytest 均可收集。"""

import copy
import hashlib
from pathlib import Path
import subprocess
import sys
import unittest

sys.dont_write_bytecode = True
TOOLS = Path(__file__).resolve().parent
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from check_pilot import EXPECTED, load_bundle, validate
from compute_metrics import PACKAGE, calculate, compute, decide


class PilotTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.original = load_bundle()

    def setUp(self):
        self.bundle = copy.deepcopy(self.original)

    def assert_detected(self, expected):
        self.assertTrue(any(expected in error for error in validate(self.bundle)),
                        validate(self.bundle))

    def test_package_valid(self):
        self.assertEqual(validate(self.bundle), [])
        self.assertEqual(len(self.bundle["metrics"]), 73)
        self.assertEqual(len(EXPECTED), 47)

    def test_required_fields(self):
        for key in ("定义", "采集方式", "基线获取方式", "判定阈值建议"):
            with self.subTest(key=key):
                self.bundle = copy.deepcopy(self.original)
                self.bundle["metrics"][0][key] = ""
                self.assert_detected("必填为空")

    def test_unknown_element(self):
        self.bundle["metrics"][0]["数据来源要素编号"] = "EVT-999"
        self.assert_detected("未知")

    def test_malformed_element(self):
        self.bundle["metrics"][0]["数据来源要素编号"] = "not-an-element"
        self.assert_detected("格式错误")

    def test_unknown_clause(self):
        self.bundle["metrics"][0]["标准条款"] = "99.99.99"
        self.assert_detected("未知条款")

    def test_document_reference(self):
        self.bundle["documents"]["试点方案.md"] += "\n参考 99.99.99；EVT-999；E99。"
        self.assert_detected("文档未知条款")
        self.assert_detected("文档未知要素")
        self.assert_detected("文档未知待决事项")

    def test_csv_encoding(self):
        for name in ("度量指标.csv", "放行条件对应表.csv", "追溯表.csv"):
            with self.subTest(name=name):
                self.assertTrue((PACKAGE / name).read_bytes().startswith(b"\xef\xbb\xbf"))

    def test_unknown_decision(self):
        self.bundle["conditions"][0]["待决事项"] = "E99"
        self.assert_detected("未知待决事项")

    def test_missing_assumption(self):
        self.bundle["metrics"][0]["临时假设编号"] = "H-WP6-99"
        self.assert_detected("临时假设未登记")

    def test_assumption_without_decision(self):
        self.bundle["assumptions"] = "| H-WP6-03 | 未登记 |"
        self.assert_detected("缺 E 编号")

    def test_condition_missing(self):
        self.bundle["conditions"].pop()
        self.assert_detected("条件覆盖")

    def test_condition_unknown_metric(self):
        self.bundle["conditions"][0]["对应指标编号"] = "M999"
        self.assert_detected("未知指标")

    def test_condition_no_mapping(self):
        self.bundle["conditions"][0]["对应指标编号"] = ""
        self.bundle["conditions"][0]["对应清单项/任务脚本"] = ""
        self.assert_detected("条件无对应")

    def test_trace_missing(self):
        self.bundle["trace"] = [r for r in self.bundle["trace"]
                                if r["要素编号"] != "EVT-019"]
        self.assert_detected("追溯遗漏")

    def test_restriction_missing(self):
        for index in (0, 1, 2, 3, 4, 16):
            with self.subTest(index=index):
                self.bundle = copy.deepcopy(self.original)
                self.bundle["metrics"][index]["用途限制"] = "一般用途"
                self.assert_detected("敏感用途")

    def test_evidence_upgrade_rejected(self):
        self.bundle["metrics"][0]["证据等级"] = "真实平台数据通过"
        self.assert_detected("证据等级")

    def test_personal_information(self):
        for value in ("13812345678", "110101200001011234", "person@example.test"):
            with self.subTest(value=value):
                self.bundle["sample"]["identifiers"]["learner"] = value
                self.assert_detected("个人信息")

    def test_expected_computations(self):
        rows = compute(self.bundle["sample"], self.bundle["metrics"])
        values = [row["合成计算值"] for row in rows[:26]]
        self.assertEqual(values, [
            150.0, 40.0, 0.5, 0.25, 300.0, 2, 1, 3.0, 50.0, 20,
            1.0, 0, 1800.0, 1, 1.0, 0.75, 235.0, 1, 0.75, 1,
            0.5, 3, 0.666667, 0, 1.0, 1.0,
        ])
        self.assertEqual(rows[15]["合成阈值比较"], "不通过")
        self.assertEqual(rows[23]["合成阈值比较"], "通过")
        self.assertTrue(all(r["合成计算值"] is None for r in rows[26:]))
        self.assertTrue(all(r["真实试点证据等级"] == "未执行" for r in rows))
        self.assertTrue(all(r["真实放行判定"] == "待审定" for r in rows))

    def test_empty_inputs(self):
        for metric in self.bundle["metrics"][:26]:
            with self.subTest(metric=metric["指标编号"]):
                key = metric["计算规则"].split(":")[1]
                self.bundle["sample"]["quantitative"][key] = []
                value = calculate(metric, self.bundle["sample"])
                self.assertEqual(value, 0 if metric["计算规则"].startswith("count:") else None)
                self.assertEqual(decide(value, metric["机器阈值"]), "待审定")

    def test_invalid_numeric_inputs(self):
        metric = self.bundle["metrics"][0]
        for value in (-1, float("nan"), float("inf"), True, "10"):
            with self.subTest(value=value):
                self.bundle["sample"]["quantitative"]["grading_seconds"] = [value]
                with self.assertRaises(ValueError):
                    calculate(metric, self.bundle["sample"])

    def test_invalid_rate_and_audit(self):
        self.bundle["sample"]["quantitative"]["adopted"] = [2]
        with self.assertRaises(ValueError):
            calculate(self.bundle["metrics"][2], self.bundle["sample"])
        metric = self.bundle["metrics"][26]
        self.bundle["sample"]["audits"]["C-12.10.1"] = "1"
        with self.assertRaises(ValueError):
            calculate(metric, self.bundle["sample"])

    def test_binary_audit_comparison(self):
        metric = self.bundle["metrics"][26]
        for value, expected in ((None, "待审定"), (0, "不通过"), (1, "通过")):
            with self.subTest(value=value):
                self.bundle["sample"]["audits"]["C-12.10.1"] = value
                self.assertEqual(decide(calculate(metric, self.bundle["sample"]),
                                        metric["机器阈值"]), expected)

    def test_unknown_rule_missing_key_bad_threshold(self):
        metric = self.bundle["metrics"][0]
        metric["计算规则"] = "unsupported:grading_seconds"
        with self.assertRaises(ValueError):
            calculate(metric, self.bundle["sample"])
        metric["计算规则"] = "sum:absent"
        with self.assertRaises(KeyError):
            calculate(metric, self.bundle["sample"])
        with self.assertRaises(ValueError):
            decide(1, "unknown:1")

    def test_deduplicated_tickets(self):
        self.bundle["sample"]["quantitative"]["review_tickets"] = ["ticket-syn-1"] * 2
        self.assertEqual(calculate(self.bundle["metrics"][5], self.bundle["sample"]), 1)

    def test_determinism_and_read_only(self):
        def hashes():
            return {p.relative_to(PACKAGE).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
                    for p in PACKAGE.rglob("*") if p.is_file() and "__pycache__" not in p.parts}
        before = hashes()
        command = [sys.executable, "-B", str(TOOLS / "compute_metrics.py")]
        first = subprocess.run(command, check=True, capture_output=True, cwd=PACKAGE.parent,
                               text=True).stdout
        second = subprocess.run(command, check=True, capture_output=True, cwd=PACKAGE,
                                text=True).stdout
        self.assertEqual(first, second)
        self.assertEqual(len(first.splitlines()), 75)
        self.assertEqual(before, hashes())

    def test_cli_bad_input(self):
        result = subprocess.run(
            [sys.executable, "-B", str(TOOLS / "compute_metrics.py"),
             "--input", str(PACKAGE / "samples/不存在.json")],
            capture_output=True, text=True,
        )
        self.assertEqual(result.returncode, 1)
        self.assertIn("计算失败", result.stderr)


if __name__ == "__main__":
    unittest.main()
