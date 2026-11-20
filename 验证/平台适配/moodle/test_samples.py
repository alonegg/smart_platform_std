import csv
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from export import collect, inspect


class SamplesTest(unittest.TestCase):
    def test_committed_sample(self):
        root = Path(__file__).parent / "samples"
        manifest = json.loads((root / "manifest.json").read_text())
        self.assertFalse(manifest["deployed"])
        for entry in manifest["files"]:
            data = (root / entry["file"]).read_bytes()
            self.assertEqual(len(data), entry["bytes"])
            self.assertEqual(hashlib.sha256(data).hexdigest(), entry["sha256"])
            self.assertEqual(inspect(data), entry["platform_version"])
            with tempfile.TemporaryDirectory() as out:
                collect(data, out)
                with self.assertRaises(ValueError):
                    collect(data, out)

    def test_bad_archive(self):
        for data in (b"", b"not a backup"):
            with self.assertRaises(Exception):
                inspect(data)

    def test_traceability(self):
        root = Path(__file__).resolve().parent
        with (root / "追溯表.csv").open(encoding="utf-8") as stream:
            entries = list(csv.DictReader(stream))
        with (root.parents[1] / "平台对标/数据要素对照矩阵.csv").open(encoding="utf-8") as stream:
            known = {row[0] for row in csv.reader(stream)}
        expected = {"OBJ-004", "OBJ-005", "OBJ-006", "OBJ-007", "OBJ-009",
                    "OBJ-012", "EVT-013", "FLD-EVT-014"}
        self.assertEqual({row["要素编号"] for row in entries}, expected)
        for row in entries:
            self.assertIn(row["要素编号"], known)
            self.assertTrue((root / row["产出文件"]).is_file())


if __name__ == "__main__":
    unittest.main()
