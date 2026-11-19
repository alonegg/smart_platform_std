"""实时统计、Markdown同步及空/错误输入测试。"""

from copy import deepcopy
import csv
from pathlib import Path
import tempfile
import unittest

from summarize import block, generate, read_matrix, synchronize


class SummarizeTests(unittest.TestCase):
    def setUp(self):
        self.rows = [dict(要素编号="OBJ-001", 要素名="Person", 数据类别="公共与交换",
                          标准条款="5.1", OpenEdX状态="缺失", Moodle状态="缺失",
                          缺失时补齐方="校级公共服务；学校管理", AI应用接入关系="AI读取输入（9.4）",
                          标准定义充分性="充分", 意见建议="", **{"补齐路径(标准条款)": "5.1，待D2"})]

    def test_small_input_and_counts_are_dynamic(self):
        result = generate(self.rows)
        self.assertIn("1 张表、1 行要素", result["scope"])
        self.assertIn("两平台都缺失的要素（1项）", result["results"])
        self.assertIn("| 校级公共服务 | 1 |", result["results"])
        self.assertIn("判‘充分’1项", result["findings"])
        second = deepcopy(self.rows[0])
        second.update(要素编号="OBJ-002", Moodle状态="部分")
        self.rows.append(second)
        self.assertIn("1 张表、2 行要素", generate(self.rows)["scope"])
        self.assertIn("两平台都缺失的要素（1项）", generate(self.rows)["results"])

    def test_sync_deterministic_and_preserves_surroundings(self):
        sections = generate(self.rows)
        initial = "前言\n" + "\n".join(block(key, "旧内容") for key in sections) + "\n计划"
        updated = synchronize(initial, sections)
        self.assertEqual(updated, synchronize(updated, sections))
        self.assertTrue(updated.startswith("前言\n"))
        self.assertTrue(updated.endswith("\n计划"))
        self.assertNotEqual(initial, updated)

    def test_missing_and_duplicate_markers(self):
        for source in ("无标记", block("scope", "旧") * 2):
            with self.subTest(source=source), self.assertRaisesRegex(ValueError, "缺失或重复"):
                synchronize(source, {"scope": "新"})

    def test_empty_marker_body(self):
        initial = "<!-- summarize:scope:start -->\n<!-- summarize:scope:end -->"
        self.assertEqual(synchronize(initial, {"scope": "内容"}), block("scope", "内容"))

    def test_real_matrix_readme_agreement(self):
        base = Path(__file__).resolve().parents[1]
        rows = read_matrix(base / "数据要素对照矩阵.csv")
        current = (base / "README.md").read_text(encoding="utf-8")
        self.assertEqual(current, synchronize(current, generate(rows)))

    def test_csv_errors_and_valid_input(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "matrix.csv"
            path.write_bytes(b"")
            with self.assertRaisesRegex(ValueError, "BOM"):
                read_matrix(path)
            path.write_text("", encoding="utf-8-sig")
            with self.assertRaisesRegex(ValueError, "为空或缺少"):
                read_matrix(path)
            for mutation in (None, {"OpenEdX状态": "未知"}, {"缺失时补齐方": "供应商"},
                             {"AI应用接入关系": "随意读取"}, {"要素编号": "未知-001"}):
                rows = deepcopy(self.rows)
                if mutation:
                    rows[0].update(mutation)
                with path.open("w", encoding="utf-8-sig", newline="") as stream:
                    writer = csv.DictWriter(stream, fieldnames=rows[0])
                    writer.writeheader()
                    writer.writerows(rows)
                if mutation:
                    with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                        read_matrix(path)
                else:
                    self.assertEqual(read_matrix(path), rows)


if __name__ == "__main__":
    unittest.main()
