"""治理五列的正常、空输入、非法枚举及越权边界测试。"""

from copy import deepcopy
from pathlib import Path
import unittest

from validate_governance import validate_governance
from validate_openedx import read_csv, validate


class GovernanceValidationTests(unittest.TestCase):
    def setUp(self):
        self.rows = [{
            "要素编号": f"TEST-{index:03d}", "要素名": "示例", "数据类别": "课程资源",
            "OpenEdX状态": "部分", "Moodle状态": "部分",
            "缺失时补齐方": "平台适配器；接入应用", "补齐路径(标准条款)": "6.2、8.6，结构契约待D2",
            "AI应用接入关系": "AI读取输入（9.4.1）", "标准定义充分性": "充分", "意见建议": "",
        } for index in range(166)]

    def test_normal_and_all_sufficiencies(self):
        for index, sufficiency in enumerate(("需补样例", "歧义", "定义缺失")):
            self.rows[index]["标准定义充分性"] = sufficiency
            self.rows[index]["意见建议"] = "【6.2】问题：具体问题；建议：具体建议"
        self.rows[3]["OpenEdX状态"] = self.rows[3]["Moodle状态"] = "原生"
        self.rows[3]["缺失时补齐方"] = "无需补齐"
        self.rows[4]["AI应用接入关系"] += "；AI写入认知记录（P-DIA，10.13）"
        counts, owners, ai, issues = validate_governance(self.rows)
        self.assertEqual(counts["课程资源"]["充分"], 163)
        self.assertEqual(owners["无需补齐"], 1)
        self.assertEqual(ai["AI写入认知记录"], 1)
        self.assertEqual(len(issues), 2)

    def test_empty_and_wrong_row_count(self):
        for rows in ([], self.rows[:-1]):
            with self.subTest(length=len(rows)), self.assertRaisesRegex(ValueError, "166 行"):
                validate_governance(rows)

    def test_empty_required_columns(self):
        for column in ("缺失时补齐方", "补齐路径(标准条款)", "AI应用接入关系", "标准定义充分性"):
            rows = deepcopy(self.rows)
            rows[0][column] = " "
            with self.subTest(column=column), self.assertRaisesRegex(ValueError, "空白"):
                validate_governance(rows)

    def test_owner_enumeration_and_duplicates(self):
        for owners in ("厂商", "平台适配器；平台适配器", "平台适配器；"):
            self.rows[0]["缺失时补齐方"] = owners
            with self.subTest(owners=owners), self.assertRaisesRegex(ValueError, "非法或重复补齐方"):
                validate_governance(self.rows)

    def test_native_consistency(self):
        for openedx, moodle, owners in (("部分", "原生", "无需补齐"),
                                        ("原生", "原生", "接入应用"),
                                        ("原生", "原生", "无需补齐；接入应用")):
            self.rows[0].update({"OpenEdX状态": openedx, "Moodle状态": moodle, "缺失时补齐方": owners})
            with self.subTest(statuses=(openedx, moodle)), self.assertRaisesRegex(ValueError, "状态不一致"):
                validate_governance(self.rows)

    def test_sufficiency_and_opinion_consistency(self):
        for sufficiency, opinion in (("足够", ""), ("充分", "不应出现的意见"), ("充分", " "),
                                      ("需补样例", ""), ("歧义", "【6.2】建议补充"),
                                      ("定义缺失", "问题：未给条款；建议：完善")):
            self.rows[0].update({"标准定义充分性": sufficiency, "意见建议": opinion})
            with self.subTest(sufficiency=sufficiency, opinion=opinion), self.assertRaises(ValueError):
                validate_governance(self.rows)

    def test_ai_enumeration_and_evidence(self):
        for relation in ("AI自由写入（9.4）", "AI读取输入", "AI读取输入（依据正文）",
                         "AI读取输入（9.4）；AI读取输入（9.4）",
                         "不直接涉及（A.2）；AI读取输入（9.4）",
                         "AI写入认知记录（P-AI，9.4）"):
            self.rows[0]["AI应用接入关系"] = relation
            with self.subTest(relation=relation), self.assertRaises(ValueError):
                validate_governance(self.rows)

    def test_path_requires_clause(self):
        self.rows[0]["补齐路径(标准条款)"] = "直接开发插件"
        with self.assertRaisesRegex(ValueError, "条款号"):
            validate_governance(self.rows)

    def test_receiver_exclusive_fields(self):
        self.rows[0]["要素编号"] = "FLD-EVT-001"
        with self.assertRaisesRegex(ValueError, "接收端专属"):
            validate_governance(self.rows)
        self.rows[0].update({"缺失时补齐方": "校级公共服务", "AI应用接入关系": "AI禁止写入（7.2.3）"})
        validate_governance(self.rows)

    def test_approval_and_confirmation_boundaries(self):
        for element in ("OBJ-041", "FLD-MTH-012", "EVT-019", "EVT-020", "EVT-021"):
            self.rows[0]["要素编号"] = element
            with self.subTest(element=element), self.assertRaises(ValueError):
                validate_governance(self.rows)

    def test_non_target_platform_column_changes_rejected(self):
        headers, rows = read_csv(Path(__file__).resolve().parents[1] / "数据要素对照矩阵.csv")
        original = deepcopy(rows)
        for column in ("OpenEdX对应", "Moodle状态", "标准定义摘要"):
            changed = deepcopy(rows)
            changed[0][column] = "不允许修改"
            with self.subTest(column=column), self.assertRaisesRegex(ValueError, "治理五列以外"):
                validate(headers, changed, headers, original, Path("unused"), "OpenEdX", "治理")


if __name__ == "__main__":
    unittest.main()
