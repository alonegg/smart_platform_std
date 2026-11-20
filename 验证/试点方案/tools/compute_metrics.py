"""只读候选口径计算；合成结果不是试点证据（4.4.5.2）。"""

import argparse
import csv
import json
import math
from pathlib import Path
import sys

sys.dont_write_bytecode = True
PACKAGE = Path(__file__).resolve().parents[1]


def load_metrics(package=PACKAGE):
    with (package / "度量指标.csv").open(encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def load_sample(path=None):
    return json.loads((Path(path) if path else PACKAGE / "samples/合成试点记录.json")
                      .read_text(encoding="utf-8"))


def calculate(metric, sample):
    operation, key = metric["计算规则"].split(":", 1)
    if operation == "audit":
        value = sample["audits"].get(key)
        if value is not None and (type(value) is not int or value not in (0, 1)):
            raise ValueError("核验值必须为 0/1 或空")
        return value
    allowed = {"mean", "rate", "sum", "max", "count", "person_days"}
    if operation not in allowed:
        raise ValueError("未知计算规则：" + operation)
    values = sample["quantitative"][key]
    if not isinstance(values, list):
        raise ValueError("定量输入必须为列表")
    if operation == "count":
        if any(not isinstance(v, str) or not v for v in values):
            raise ValueError("工单/原因必须为非空合成文本")
        return len(set(values)) if key.endswith("tickets") else len(values)
    if any(type(v) not in (int, float) or not math.isfinite(v) or v < 0 for v in values):
        raise ValueError("数值必须有限且非负")
    if operation == "rate" and any(v not in (0, 1) for v in values):
        raise ValueError("比例输入只能为 0/1")
    if not values:
        return None
    if operation in {"mean", "rate"}:
        return sum(values) / len(values)
    if operation == "sum":
        return sum(values)
    if operation == "max":
        return max(values)
    return sum(values) / 8


def decide(value, threshold):
    if threshold == "pending" or value is None:
        return "待审定"
    operation, raw = threshold.split(":", 1)
    limit = float(raw)
    if not math.isfinite(limit) or operation not in {"eq", "ge", "le"}:
        raise ValueError("未知或无效阈值")
    passed = {"eq": value == limit, "ge": value >= limit, "le": value <= limit}[operation]
    return "通过" if passed else "不通过"


def compute(sample, metrics=None):
    rows = []
    for metric in load_metrics() if metrics is None else metrics:
        value = calculate(metric, sample)
        rows.append({
            "指标编号": metric["指标编号"],
            "指标名": metric["指标名"],
            "合成计算值": None if value is None else round(value, 6),
            "合成阈值比较": decide(value, metric["机器阈值"]),
            "阈值性质": metric["阈值性质"],
            "真实试点证据等级": "未执行",
            "真实放行判定": "待审定",
        })
    return rows


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, help="只接受合成记录；不写入仓库")
    args = parser.parse_args()
    try:
        result = compute(load_sample(args.input))
    except (ValueError, KeyError, TypeError, OSError) as error:
        print("计算失败：" + str(error), file=sys.stderr)
        return 1
    print("合成计算仅证明口径可算；全部真实试点指标：未执行。")
    print("编号\t合成值\t候选阈值比较\t真实放行判定")
    for row in result:
        value = "空" if row["合成计算值"] is None else str(row["合成计算值"])
        print(f'{row["指标编号"]}\t{value}\t{row["合成阈值比较"]}\t{row["真实放行判定"]}')
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
