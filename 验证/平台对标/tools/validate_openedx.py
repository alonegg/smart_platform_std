#!/usr/bin/env python3
"""校验双平台列与源码路径；对照仓库外备份检查非目标列，不写入矩阵。

默认对照 ~/backup/数据要素对照矩阵.治理填写前.csv，仅允许治理五列变化。
Moodle 依据相对于 ~/ref/moodle，OpenEdX 依据相对于 ~/ref。
可用 --baseline、--changed-platform 和 --ref-root 指定其他填写步骤及源码位置。
"""

import argparse
from collections import Counter
import csv
from pathlib import Path

from validate_governance import report, validate_governance


BASE = Path(__file__).resolve().parents[1]
PLATFORMS = ("OpenEdX", "Moodle")
STATUSES = ("原生", "可派生", "部分", "缺失")
GOVERNANCE_COLUMNS = {"缺失时补齐方", "补齐路径(标准条款)", "AI应用接入关系", "标准定义充分性", "意见建议"}


def platform_columns(platform):
    return {platform + suffix for suffix in ("对应", "状态", "依据")}


def read_csv(path):
    if not path.read_bytes().startswith(b"\xef\xbb\xbf"):
        raise ValueError(f"缺少 UTF-8 BOM：{path.name}")
    with path.open(encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        return reader.fieldnames, list(reader)


def validate(headers, rows, old_headers, old_rows, ref_root, platform, changed_platform):
    columns = platform_columns(platform)
    changed_columns = GOVERNANCE_COLUMNS if changed_platform == "治理" else platform_columns(changed_platform)
    required = {"要素编号", "数据类别"} | set().union(*(platform_columns(p) for p in PLATFORMS))
    if (headers != old_headers or len(headers or []) != 17 or len(set(headers)) != 17
            or not required.issubset(headers) or len(rows) != 166 or len(old_rows) != 166):
        raise ValueError("表头或 166 行数据要求不符")
    if len({row['要素编号'] for row in rows}) != len(rows) or any(not row['要素编号'] for row in rows):
        raise ValueError("要素编号空白或重复")
    counts = {}
    paths = set()
    references = 0
    for row, old in zip(rows, old_rows):
        element = row["要素编号"]
        if set(row) != set(headers) or any(value is None for value in row.values()):
            raise ValueError(f"{element}：CSV 行列数不符")
        if any(row[key] != old[key] for key in headers if key not in changed_columns):
            target = "治理五列" if changed_platform == "治理" else changed_platform + " 三列"
            raise ValueError(f"{element}：修改了 {target}以外的内容")
        if any(not row[key].strip() for key in columns):
            raise ValueError(f"{element}：存在未填 {platform} 列")
        status = row[platform + "状态"]
        if status not in STATUSES:
            raise ValueError(f"{element}：非法状态 {status}")
        evidence = row[platform + "依据"]
        citations, marker, search = evidence.partition("；已搜索")
        if status == "缺失" and (not marker or not search.strip(" ：:（）()")):
            raise ValueError(f"{element}：缺少搜索记录")
        citations = citations.split("；")
        suffixes = (".php", ".xml") if platform == "Moodle" else (".py",)
        if not citations or any(not citation.endswith(suffixes) for citation in citations):
            raise ValueError(f"{element}：依据应为以中文分号分隔的仓库相对源码路径")
        root = ref_root / "moodle" if platform == "Moodle" else ref_root
        for citation in citations:
            path = Path(citation)
            if (path.is_absolute() or ".." in path.parts
                    or (platform == "Moodle" and path.parts[0] != "public")
                    or not (root / path).is_file()):
                raise ValueError(f"{element}：路径不存在或非相对文件路径 {citation}")
            paths.add(citation)
            references += 1
        counts.setdefault(row["数据类别"], Counter())[status] += 1
    return counts, paths, references


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ref-root", type=Path, default=Path.home() / "ref")
    parser.add_argument("--matrix", type=Path, default=BASE / "数据要素对照矩阵.csv")
    parser.add_argument("--baseline", type=Path)
    parser.add_argument("--changed-platform", choices=(*PLATFORMS, "治理"), default="治理")
    args = parser.parse_args()
    headers, rows = read_csv(args.matrix)
    baseline = args.baseline or Path.home() / "backup" / f"数据要素对照矩阵.{args.changed_platform}填写前.csv"
    old_headers, old_rows = read_csv(baseline)
    results = {}
    for platform in PLATFORMS:
        counts, paths, references = validate(
            headers, rows, old_headers, old_rows, args.ref_root, platform, args.changed_platform)
        results[platform] = counts
        print(f"PASS: 166/166 行 {platform} 三列已填；状态合法；编号唯一；UTF-8 BOM 保留")
        print(f"PASS: {platform} {references} 条路径引用、{len(paths)} 个唯一源码文件全部存在；缺失项均有搜索记录")
    target = "治理五列" if args.changed_platform == "治理" else args.changed_platform + " 三列"
    print(f"PASS: 与仓库外备份逐行比较，仅 {target}变化")
    if args.changed_platform == "治理":
        report(*validate_governance(rows))
        return
    counts = results[args.changed_platform]
    print("数据类别,原生,可派生,部分,缺失,合计")
    total = Counter()
    for category in ("课程资源", "教学过程与学习证据", "认知诊断", "公共与交换"):
        count = counts[category]
        print(",".join([category] + [str(count[s]) for s in STATUSES] + [str(sum(count.values()))]))
        total.update(count)
    print(",".join(["合计"] + [str(total[s]) for s in STATUSES] + [str(sum(total.values()))]))


if __name__ == "__main__":
    main()
