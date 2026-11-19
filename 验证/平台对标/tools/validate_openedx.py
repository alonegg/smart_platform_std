#!/usr/bin/env python3
"""校验 OpenEdX 三列、引用路径及填写前后其他列不变；不写入矩阵。"""

import argparse
from collections import Counter
import csv
from pathlib import Path


BASE = Path(__file__).resolve().parents[1]
COLUMNS = {"OpenEdX对应", "OpenEdX状态", "OpenEdX依据"}
STATUSES = ("原生", "可派生", "部分", "缺失")


def read_csv(path):
    if not path.read_bytes().startswith(b"\xef\xbb\xbf"):
        raise ValueError(f"缺少 UTF-8 BOM：{path.name}")
    with path.open(encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        return reader.fieldnames, list(reader)


def validate(headers, rows, old_headers, old_rows, ref_root):
    if headers != old_headers or len(rows) != 166 or len(old_rows) != 166:
        raise ValueError("表头或 166 行数据要求不符")
    if len({row['要素编号'] for row in rows}) != len(rows):
        raise ValueError("要素编号重复")
    counts = {}
    paths = set()
    references = 0
    for row, old in zip(rows, old_rows):
        element = row["要素编号"]
        if any(row[key] != old[key] for key in headers if key not in COLUMNS):
            raise ValueError(f"{element}：修改了 OpenEdX 三列以外的内容")
        if any(not row[key].strip() for key in COLUMNS):
            raise ValueError(f"{element}：存在未填 OpenEdX 列")
        status = row["OpenEdX状态"]
        if status not in STATUSES:
            raise ValueError(f"{element}：非法状态 {status}")
        evidence = row["OpenEdX依据"]
        if status == "缺失" and "已搜索" not in evidence:
            raise ValueError(f"{element}：缺少搜索记录")
        citations = evidence.split("；已搜索", 1)[0].split("；")
        if not citations or any(not citation.endswith(".py") for citation in citations):
            raise ValueError(f"{element}：依据应为以中文分号分隔的仓库相对源码路径")
        for citation in citations:
            path = Path(citation)
            if path.is_absolute() or ".." in path.parts or not (ref_root / path).is_file():
                raise ValueError(f"{element}：路径不存在或非相对文件路径 {citation}")
            paths.add(citation)
            references += 1
        counts.setdefault(row["数据类别"], Counter())[status] += 1
    return counts, paths, references


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ref-root", type=Path, default=Path.home() / "ref")
    args = parser.parse_args()
    headers, rows = read_csv(BASE / "数据要素对照矩阵.csv")
    old_headers, old_rows = read_csv(BASE / "数据要素对照矩阵.OpenEdX填写前.csv")
    counts, paths, references = validate(headers, rows, old_headers, old_rows, args.ref_root)
    print("PASS: 166/166 行 OpenEdX 三列已填；状态合法；编号唯一；UTF-8 BOM 保留")
    print("PASS: 与备份逐行比较，仅 OpenEdX 三列变化；缺失项均有搜索位置/关键词")
    print(f"PASS: {references} 条路径引用、{len(paths)} 个唯一源码文件全部存在；无无效路径")
    print("数据类别,原生,可派生,部分,缺失,合计")
    total = Counter()
    for category in ("课程资源", "教学过程与学习证据", "认知诊断", "公共与交换"):
        count = counts[category]
        print(",".join([category] + [str(count[s]) for s in STATUSES] + [str(sum(count.values()))]))
        total.update(count)
    print(",".join(["合计"] + [str(total[s]) for s in STATUSES] + [str(sum(total.values()))]))


if __name__ == "__main__":
    main()
