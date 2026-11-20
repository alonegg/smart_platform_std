"""8.11、A.8；OBJ-029；追溯完整性、空范围及错误条目检测。"""
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from helpers import ROOT

spec = importlib.util.spec_from_file_location("wp2_trace", ROOT / "tools/check_trace.py")
trace = importlib.util.module_from_spec(spec)
spec.loader.exec_module(trace)


class TraceTests(unittest.TestCase):
    def test_trace_positive_script(self):
        """8.11；OBJ-029；只读脚本覆盖范围内每项。"""
        result = subprocess.run([sys.executable, str(ROOT / "tools/check_trace.py")], text=True, capture_output=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("PASS:", result.stdout)

    def test_trace_reject_empty_and_unknown_missing_annotations(self):
        """8.11；OBJ-029；错误编号、空范围、文件与注释缺失不通过。"""
        with tempfile.TemporaryDirectory(dir=ROOT) as directory:
            scope = Path(directory) / "scope.json"
            table = Path(directory) / "trace.csv"
            scope.write_text(json.dumps({"element_ids": []}))
            self.assertTrue(trace.check(scope)[0])
            scope.write_text(json.dumps({"element_ids": ["NOT-IN-MATRIX", "OBJ-029"]}))
            table.write_text("element_id,条款,输出文件,状态,理由\nNOT-IN-MATRIX,8.11,验证/参考公共服务/missing.py,partial,synthetic\n")
            errors = trace.check(scope, table)[0]
            self.assertTrue(any("unknown matrix" in e for e in errors))
            self.assertTrue(any("missing trace" in e for e in errors))
            self.assertTrue(any("missing or outside" in e for e in errors))
            table.write_text("element_id,条款,输出文件,状态,理由\nOBJ-029,8.11,验证/参考公共服务/.gitignore,partial,synthetic\n")
            self.assertTrue(any("element absent" in e for e in trace.check(scope, table)[0]))
