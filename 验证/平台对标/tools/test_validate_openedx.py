"""双平台矩阵校验器的正常、空输入及错误输入测试。"""

from copy import deepcopy
from contextlib import redirect_stdout
import csv
import io
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from validate_openedx import main, read_csv, validate


class MatrixValidationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / "edx-platform").mkdir()
        (self.root / "edx-platform/model.py").touch()
        (self.root / "moodle/public").mkdir(parents=True)
        (self.root / "moodle/public/model.php").touch()
        self.headers = ["要素编号", "数据类别", "要素类型", "要素名", "标准条款", "标准定义摘要",
                        "OpenEdX对应", "OpenEdX状态", "OpenEdX依据", "Moodle对应", "Moodle状态", "Moodle依据",
                        "缺失时补齐方", "补齐路径(标准条款)", "AI应用接入关系", "标准定义充分性", "意见建议"]
        self.rows = []
        for index in range(166):
            row = dict.fromkeys(self.headers, "")
            row.update({"要素编号": f"OBJ-{index:03d}", "数据类别": "公共与交换",
                        "OpenEdX对应": "Model.id", "OpenEdX状态": "部分",
                        "OpenEdX依据": "edx-platform/model.py", "Moodle对应": "model.id",
                        "Moodle状态": "部分", "Moodle依据": "public/model.php"})
            self.rows.append(row)
        self.old = deepcopy(self.rows)
        for row in self.old:
            for suffix in ("对应", "状态", "依据"):
                row["Moodle" + suffix] = ""

    def check(self, platform="Moodle"):
        return validate(self.headers, self.rows, self.headers, self.old,
                        self.root, platform, "Moodle")

    def test_both_platforms_and_statuses(self):
        for index, status in enumerate(("原生", "可派生", "部分", "缺失")):
            self.rows[index]["Moodle状态"] = status
        self.rows[3]["Moodle依据"] += "；已搜索：model、missing_field"
        counts, paths, references = self.check()
        self.assertEqual(sum(counts["公共与交换"].values()), 166)
        self.assertEqual(paths, {"public/model.php"})
        self.assertEqual(references, 166)
        self.assertEqual(self.check("OpenEdX")[2], 166)

    def test_main_replays_openedx_before_moodle_is_filled(self):
        categories = ("课程资源", "教学过程与学习证据", "认知诊断", "公共与交换")
        rows = deepcopy(self.rows)
        for index, row in enumerate(rows):
            row["数据类别"] = categories[index % len(categories)]
            for suffix in ("对应", "状态", "依据"):
                row["Moodle" + suffix] = ""
        baseline = deepcopy(rows)
        for row in baseline:
            for suffix in ("对应", "状态", "依据"):
                row["OpenEdX" + suffix] = ""
        matrix_path = self.root / "matrix.csv"
        baseline_path = self.root / "baseline.csv"
        for path, data in ((matrix_path, rows), (baseline_path, baseline)):
            with path.open("w", encoding="utf-8-sig", newline="") as stream:
                writer = csv.DictWriter(stream, fieldnames=self.headers)
                writer.writeheader()
                writer.writerows(data)
        output = io.StringIO()
        with patch("sys.argv", ["validate_openedx.py", "--changed-platform", "OpenEdX",
                                "--matrix", str(matrix_path), "--baseline", str(baseline_path),
                                "--ref-root", str(self.root)]), redirect_stdout(output):
            main()
        self.assertIn("PASS: 166/166 行 OpenEdX 三列已填", output.getvalue())
        self.assertIn("仅 OpenEdX 三列变化", output.getvalue())
        self.assertNotIn("行 Moodle 三列已填", output.getvalue())

    def test_empty_or_wrong_row_count(self):
        for rows in ([], self.rows[:-1], self.rows + self.rows[:1]):
            with self.subTest(length=len(rows)), self.assertRaisesRegex(ValueError, "166 行"):
                validate(self.headers, rows, self.headers, self.old, self.root, "Moodle", "Moodle")

    def test_empty_columns(self):
        for suffix in ("对应", "状态", "依据"):
            with self.subTest(column=suffix):
                original = self.rows[0]["Moodle" + suffix]
                self.rows[0]["Moodle" + suffix] = " "
                with self.assertRaisesRegex(ValueError, "未填 Moodle"):
                    self.check()
                self.rows[0]["Moodle" + suffix] = original

    def test_illegal_status(self):
        self.rows[0]["Moodle状态"] = "支持"
        with self.assertRaisesRegex(ValueError, "非法状态"):
            self.check()

    def test_duplicate_or_empty_id(self):
        for identifier in ("", self.rows[1]["要素编号"]):
            with self.subTest(identifier=identifier), self.assertRaisesRegex(ValueError, "空白或重复"):
                self.rows[0]["要素编号"] = identifier
                self.check()

    def test_non_target_changes_including_openedx(self):
        for column in ("标准定义摘要", "OpenEdX对应", "缺失时补齐方", "要素名"):
            with self.subTest(column=column):
                original = self.rows[0][column]
                self.rows[0][column] = "不允许的变化"
                with self.assertRaisesRegex(ValueError, "三列以外"):
                    self.check()
                self.rows[0][column] = original

    def test_missing_search_record(self):
        self.rows[0]["Moodle状态"] = "缺失"
        for evidence in ("public/model.php", "public/model.php；已搜索："):
            with self.subTest(evidence=evidence), self.assertRaisesRegex(ValueError, "缺少搜索记录"):
                self.rows[0]["Moodle依据"] = evidence
                self.check()

    def test_bad_paths(self):
        for evidence in ("public/missing.php", "/absolute.php", "public/../model.php",
                         "model.php", "public/model.txt", "moodle/public/model.php"):
            with self.subTest(evidence=evidence), self.assertRaises(ValueError):
                self.rows[0]["Moodle依据"] = evidence
                self.check()

    def test_openedx_path_validation(self):
        self.rows[0]["OpenEdX依据"] = self.old[0]["OpenEdX依据"] = "edx-platform/missing.py"
        with self.assertRaisesRegex(ValueError, "路径不存在"):
            self.check("OpenEdX")

    def test_malformed_rows_and_headers(self):
        self.rows[0][None] = ["extra cell"]
        with self.assertRaisesRegex(ValueError, "行列数"):
            self.check()
        del self.rows[0][None]
        self.rows[0]["Moodle对应"] = None
        with self.assertRaisesRegex(ValueError, "行列数"):
            self.check()
        with self.assertRaisesRegex(ValueError, "表头"):
            validate([], [], [], [], self.root, "Moodle", "Moodle")

    def test_bom_and_empty_file(self):
        path = self.root / "matrix.csv"
        path.write_text("", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "BOM"):
            read_csv(path)
        path.write_text("", encoding="utf-8-sig")
        self.assertEqual(read_csv(path), (None, []))
        with self.assertRaisesRegex(ValueError, "166 行"):
            validate(*read_csv(path), self.headers, self.old, self.root, "Moodle", "Moodle")


if __name__ == "__main__":
    unittest.main()
