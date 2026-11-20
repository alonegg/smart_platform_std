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
                          OpenEdX对应="未见", Moodle对应="未见", OpenEdX覆盖度="0", Moodle覆盖度="0",
                          缺失时补齐方="校级公共服务；学校管理", AI应用接入关系="AI读取输入（9.4）",
                          标准定义充分性="充分", 意见建议="", **{"补齐路径(标准条款)": "5.1，待D2"})]

    def test_small_input_and_counts_are_dynamic(self):
        result = generate(self.rows)
        self.assertIn("1 张表、1 行要素", result["scope"])
        self.assertIn("两平台都缺失的要素（1项）", result["results"])
        self.assertIn("| 校级公共服务 | 1 |", result["results"])
        self.assertIn("判‘充分’1项", result["findings"])
        second = deepcopy(self.rows[0])
        second.update(要素编号="OBJ-002", Moodle状态="部分", Moodle覆盖度="2",
                      Moodle对应="已有核心事实〔覆盖度2：转换已有字段即可〕")
        self.rows.append(second)
        self.assertIn("1 张表、2 行要素", generate(self.rows)["scope"])
        self.assertIn("两平台都缺失的要素（1项）", generate(self.rows)["results"])
        self.assertIn("| 公共与交换 | Moodle | 1 | 0 | 1 | 0 | 2 | 1.00 |", generate(self.rows)["results"])

    def test_coverage_counts_means_and_representatives(self):
        rows = []
        for i, score in enumerate(("0", "1", "2", "3", "2", "2", "2")):
            row = deepcopy(self.rows[0])
            row.update(要素编号=f"OBJ-{i + 1:03d}", 要素名=f"Element{i}", 数据类别="课程资源",
                       OpenEdX覆盖度=score, Moodle覆盖度=score)
            rows.append(row)
        result = generate(rows)["results"]
        self.assertIn("| 课程资源 | OpenEdX | 1 | 1 | 4 | 1 | 7 | 1.71 |", result)
        line = next(line for line in result.splitlines() if line.startswith("| 课程资源 | OpenEdX | 2 | `"))
        for key in ("OBJ-003", "OBJ-005", "OBJ-006"):
            self.assertIn(key, line)
        self.assertNotIn("OBJ-007", line)
        self.assertIn("（仅1项，全部列出）", result)
        self.assertIn("无（仅0项，全部列出）", result)

    def test_empty_coverage_summary_has_no_division_error(self):
        result = generate([])["results"]
        self.assertIn("| 全部类别 | OpenEdX | 0 | 0 | 0 | 0 | 0 | — |", result)
        self.assertIn("无（仅0项，全部列出）", result)

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
                             {"AI应用接入关系": "随意读取"}, {"要素编号": "未知-001"},
                             {"OpenEdX覆盖度": ""}, {"Moodle覆盖度": "4"},
                             {"Moodle覆盖度": "2"}, {"OpenEdX状态": "部分", "OpenEdX覆盖度": "1"}):
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
