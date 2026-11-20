"""Cross-platform traceability and the offline test runner's success/failure paths."""

from contextlib import redirect_stderr, redirect_stdout
import csv
import io
from pathlib import Path
import re
import subprocess
import tempfile
import unittest
from unittest.mock import patch

import run_tests

ROOT = Path(__file__).resolve().parent


class PackageTest(unittest.TestCase):
    def test_both_trace_tables_use_matrix_ids(self):
        matrix = ROOT.parent / '平台对标' / '数据要素对照矩阵.csv'
        with matrix.open(encoding='utf-8-sig', newline='') as stream:
            known = {row['要素编号'] for row in csv.DictReader(stream)}
        self.assertTrue(known)
        for platform in ('moodle', 'openedx'):
            with self.subTest(platform=platform):
                with (ROOT / platform / '追溯表.csv').open(encoding='utf-8-sig', newline='') as stream:
                    rows = list(csv.DictReader(stream))
                self.assertTrue(rows)
                for row in rows:
                    self.assertIn(row['要素编号'], known)
                    for name in row['样本文件'].split(';'):
                        self.assertTrue((ROOT / platform / 'samples' / name).is_file(), name)

    def test_documented_local_links_exist(self):
        for name in ('README.md', '发现的标准问题.md'):
            for target in re.findall(r'\]\(([^)]+)\)', (ROOT / name).read_text(encoding='utf-8')):
                with self.subTest(document=name, target=target):
                    self.assertTrue((ROOT / target.split('#')[0]).exists())


class RunnerTest(unittest.TestCase):
    def test_runner_launches_all_suites_in_separate_processes(self):
        success = subprocess.CompletedProcess([], 0)
        with patch.object(run_tests.subprocess, 'run', return_value=success) as run, redirect_stdout(io.StringIO()):
            self.assertEqual(run_tests.run_suites(), 0)
        self.assertEqual(run.call_count, 3)
        for call, (_, directory, pattern) in zip(run.call_args_list, run_tests.SUITES):
            self.assertEqual(call.args[0], [run_tests.sys.executable, '-B', '-m', 'unittest', 'discover',
                                          '-s', str(directory), '-p', pattern, '-v'])
            self.assertEqual(call.kwargs['cwd'], run_tests.REPO)

    def test_runner_continues_after_failure(self):
        results = [subprocess.CompletedProcess([], code) for code in (0, 1, 0)]
        with patch.object(run_tests.subprocess, 'run', side_effect=results) as run, redirect_stdout(io.StringIO()):
            self.assertEqual(run_tests.run_suites(), 1)
        self.assertEqual(run.call_count, 3)

    def test_runner_rejects_empty_suite_list(self):
        with patch.object(run_tests.subprocess, 'run') as run, redirect_stderr(io.StringIO()):
            self.assertEqual(run_tests.run_suites(()), 2)
        run.assert_not_called()

    def test_runner_rejects_empty_or_missing_test_directory(self):
        with tempfile.TemporaryDirectory() as temporary:
            for directory in (Path(temporary), Path(temporary) / 'missing'):
                with self.subTest(directory=directory), patch.object(run_tests.subprocess, 'run') as run, \
                        redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
                    self.assertEqual(run_tests.run_suites((('empty', directory, 'test_*.py'),)), 1)
                run.assert_not_called()


if __name__ == '__main__':
    unittest.main()
