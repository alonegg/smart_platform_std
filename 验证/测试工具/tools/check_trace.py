"""只读检查本步范围、矩阵、追溯路径与元素注释。"""
import csv
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parents[1]


def check():
    scope = json.loads((ROOT / "scope.json").read_text())
    with (REPO / scope["matrix"]).open() as f:
        matrix = {r[0] for r in csv.reader(f)}
    with (ROOT / "追溯表.csv").open() as f:
        rows = list(csv.DictReader(f))
    assert set(scope["element_ids"]) == {r["element_id"] for r in rows}
    for row in rows:
        assert row["element_id"] in matrix, row
        for name in row["输出文件"].split(";"):
            path = REPO / name
            assert path.is_file(), name
            assert row["element_id"] in path.read_text(), (name, row["element_id"])
    return "追溯检查通过：" + str(len(rows)) + " 个范围要素（仅本步子集）"


if __name__ == "__main__":
    print(check())
