"""研究报告的动态统计、正文口径和同步检查。"""

from contextlib import redirect_stdout, redirect_stderr
from copy import deepcopy
import io
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from report_stats import (BASE, REPORT, STANDARD, domain, generate, input_hashes,
                          main, standard_metrics)
from summarize import block, read_matrix, synchronize


SOURCE = """# 标题
1.1 应记录。
1.1.1 不应覆盖。
A.1.1 应登记。
E.1 说明。
| E01 | 责任 | 处理 | 主体 | 条款 | D1 |
| E23 | 分项 | 处理 | 主体 | 条款 | D2、D4 |
| E23a 交换语义 | 输入 | D2 | 主体 |
| E23b 评分 | 输入 | D4 | 主体 |
| E23c 取证 | 输入 | D4 | 主体 |
| D1 审议 | 成果 | 条件 |
| D2 冻结 | 成果 | 条件 |
"""


class ReportTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rows = read_matrix(BASE / "数据要素对照矩阵.csv")

    def test_standard_metrics_explicit_counting_rules(self):
        metrics = standard_metrics(SOURCE)
        self.assertEqual(metrics["characters"], len(SOURCE))
        self.assertEqual(metrics["shall"], 3)
        self.assertEqual(metrics["clauses"], 4)
        self.assertEqual(metrics["detailed_clauses"], 3)
        self.assertEqual(metrics["subitems"], ["E23a", "E23b", "E23c"])
        self.assertEqual(metrics["stages"], ["D1", "D2"])
        self.assertEqual(len(metrics["decisions"]), 2)

    def test_empty_and_duplicate_inputs_rejected(self):
        for source in ("", "无编号文本", SOURCE + "1.1 重复。\n", SOURCE + "| E01 | 重复 | D1 |\n"):
            with self.subTest(source=source), self.assertRaises(ValueError):
                standard_metrics(source)
        with self.assertRaisesRegex(ValueError, "空矩阵"):
            generate([], SOURCE)

    def test_counts_are_dynamic_and_subset_has_no_division_error(self):
        row = deepcopy(self.rows[0])
        row.update(数据类别="认知诊断", 要素类型="字段", OpenEdX覆盖度="2", Moodle覆盖度="1")
        first = generate([row], SOURCE)
        self.assertIn("矩阵共1行", first["report-abstract"])
        self.assertIn("| OpenEdX | 0 | 0 | 1 | 0 | 1 | 2.00 |", first["report-overall"])
        self.assertIn("| 课程资源 | OpenEdX | 0 | — | 0 | — |", first["report-hypothesis"])
        second = deepcopy(row)
        second.update(要素编号="OBJ-002", OpenEdX覆盖度="0")
        changed = generate([row, second], SOURCE)
        self.assertIn("矩阵共2行", changed["report-abstract"])
        self.assertIn("| OpenEdX | 1 | 0 | 1 | 0 | 2 | 1.00 |", changed["report-overall"])

    def test_domain_lists_source_paths_reasons_and_all_opinions(self):
        result = domain(self.rows, "课程资源")
        for row in self.rows:
            if row["数据类别"] != "课程资源":
                continue
            if row["标准定义充分性"] != "充分":
                self.assertIn(row["意见建议"], result)
            for platform in ("OpenEdX", "Moodle"):
                if row[platform + "覆盖度"] == "2":
                    self.assertIn(row[platform + "依据"], result)
                    self.assertIn(row["标准条款"], result)
        self.assertIn("6.4.1", result)
        self.assertIn("6.4.2", result)

    def test_real_report_agrees_and_stale_text_is_detected(self):
        sections = generate(self.rows, STANDARD.read_text(encoding="utf-8"))
        sections["report-inputs"] = input_hashes(BASE / "数据要素对照矩阵.csv", STANDARD)
        current = REPORT.read_text(encoding="utf-8")
        self.assertEqual(current, synchronize(current, sections))
        stale = current.replace("<!-- summarize:report-abstract:start -->\n",
                                "<!-- summarize:report-abstract:start -->\n过期统计\n")
        self.assertNotEqual(stale, synchronize(stale, sections))

    def test_cli_check_rejects_stale_report(self):
        sections = generate(self.rows, STANDARD.read_text(encoding="utf-8"))
        sections["report-inputs"] = input_hashes(BASE / "数据要素对照矩阵.csv", STANDARD)
        with tempfile.TemporaryDirectory() as directory:
            report = Path(directory) / "report.md"
            report.write_text("\n".join(block(name, "过期") for name in sections), encoding="utf-8")
            with patch("sys.argv", ["report_stats.py", "--check", "--report", str(report)]), redirect_stderr(io.StringIO()):
                with self.assertRaises(SystemExit) as result:
                    main()
            self.assertEqual(result.exception.code, 1)
            with patch("sys.argv", ["report_stats.py", "--write", "--report", str(report)]), redirect_stdout(io.StringIO()):
                main()
            self.assertEqual(report.read_text(encoding="utf-8"), synchronize(report.read_text(encoding="utf-8"), sections))


if __name__ == "__main__":
    unittest.main()
