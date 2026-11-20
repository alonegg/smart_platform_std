"""WP6 引用与覆盖核验，不核发真实试点放行结论。"""

import csv
import json
from pathlib import Path
import re
import sys

sys.dont_write_bytecode = True
from compute_metrics import PACKAGE, compute, load_metrics, load_sample

ROOT = Path(__file__).resolve().parents[3]
CLAUSE = re.compile(r"(?<![\w.])(?:\d+(?:\.\d+){1,3}|[A-E](?:\.\d+){1,3})(?![\w.])")
ELEMENT = re.compile(r"(?:OBJ|FLD|EVT)-\d{3}")
DECISION = re.compile(r"\bE\d{2}\b")
EXPECTED = (
    {f"C-12.10.{i}" for i in range(1, 6)}
    | {f"C-12.11.1-{letter}" for letter in "abcd"}
    | {f"C-12.11.{i}" for i in range(2, 6)}
    | {f"C-D3-{i}" for i in range(1, 12)}
    | {f"C-D4-{i}" for i in range(1, 12)}
    | {f"C-D.3.{section}-{i}" for section, count in
       ((1, 3), (2, 2), (3, 1), (4, 2), (5, 4)) for i in range(1, count + 1)}
)


def read_csv(path):
    with path.open(encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def load_bundle(package=PACKAGE):
    return {
        "metrics": load_metrics(package),
        "conditions": read_csv(package / "放行条件对应表.csv"),
        "trace": read_csv(package / "追溯表.csv"),
        "assumptions": (package / "临时假设.md").read_text(encoding="utf-8"),
        "documents": {p.name: p.read_text(encoding="utf-8") for p in package.glob("*.md")},
        "sample": json.loads((package / "samples/合成试点记录.json").read_text(encoding="utf-8")),
    }


def validate(bundle):
    errors = []
    standard = (ROOT / "标准/评审稿/智慧教学-数据模型标准.md").read_text(encoding="utf-8")
    clauses = set(re.findall(r"^(?:#{1,6}\s+)?((?:\d+|[A-E])(?:\.\d+)+)\b",
                             standard, re.MULTILINE))
    clauses.update(re.findall(r"表\s+([A-E]\.\d+)", standard))
    decisions = set(re.findall(r"^\|\s*(E\d{2})\s*\|", standard, re.MULTILINE))
    elements = {r["要素编号"] for r in read_csv(ROOT / "验证/平台对标/数据要素对照矩阵.csv")}
    metrics = bundle["metrics"]
    mids = {m["指标编号"] for m in metrics}
    if len(mids) != len(metrics):
        errors.append("指标编号重复")
    cids = {c["条件编号"] for c in bundle["conditions"]}
    if cids != EXPECTED or len(cids) != len(bundle["conditions"]):
        errors.append("放行条件覆盖缺失/多余/重复：" + ";".join(sorted(EXPECTED ^ cids)))
    required = ("指标编号", "指标名", "定义", "计算公式", "分子", "分母", "汇总粒度",
                "采集方式", "数据来源要素编号", "基线获取方式", "判定阈值建议", "阈值性质",
                "临时假设编号", "待决事项", "标准条款", "对应放行条件编号",
                "用途限制", "证据等级", "计算规则", "机器阈值")
    referenced = set()
    for m in metrics:
        for key in required:
            if not m.get(key, "").strip():
                errors.append(m.get("指标编号", "?") + " 必填为空：" + key)
        referenced.update(m.get("数据来源要素编号", "").split(";"))
        if m.get("证据等级") != "未执行":
            errors.append("真实试点前证据等级须为未执行")
        if m.get("阈值性质") not in {"标准规定", "临时假设", "待试点前审定"}:
            errors.append("阈值性质非法")
        if m.get("阈值性质") == "临时假设":
            hid = m.get("临时假设编号", "")
            line = next((line for line in bundle["assumptions"].splitlines()
                         if line.startswith("| " + hid + " |")), "")
            if not re.fullmatch(r"H-WP6-\d{2}", hid) or not DECISION.search(line):
                errors.append("临时假设未登记或缺 E 编号：" + hid)
        if any(term in m.get("指标名", "") for term in
               ("教师", "采纳率", "改分率", "确认时长", "T16 任务耗时")):
            restriction = m.get("用途限制", "")
            if "11.4.7" not in restriction or "课程/批次" not in restriction:
                errors.append("敏感用途限制缺失：" + m["指标编号"])
        for cid in m.get("对应放行条件编号", "").split(";"):
            if cid not in cids:
                errors.append("指标引用未知条件：" + cid)
    for c in bundle["conditions"]:
        refs = c.get("对应指标编号", "")
        if not refs and not c.get("对应清单项/任务脚本", ""):
            errors.append("条件无对应：" + c["条件编号"])
        for mid in filter(None, refs.split(";")):
            if mid not in mids:
                errors.append("条件引用未知指标：" + mid)
        if not c.get("证据材料") or not c.get("判定方式"):
            errors.append("条件证据/判定缺失")
    trace_elements = {r["要素编号"] for r in bundle["trace"]}
    if not (referenced | trace_elements) <= elements:
        errors.append("指标/追溯存在未知或格式错误的要素编号")
    if not referenced <= trace_elements:
        errors.append("追溯遗漏：" + ";".join(sorted(referenced - trace_elements)))
    for row in metrics + bundle["conditions"] + bundle["trace"]:
        for key, value in row.items():
            if key in {"标准条款", "来源条款"}:
                for ref in value.split(";"):
                    if ref not in clauses:
                        errors.append("未知条款：" + ref)
            for element in ELEMENT.findall(value):
                if element not in elements:
                    errors.append("未知要素：" + element)
            for decision in DECISION.findall(value):
                if decision not in decisions:
                    errors.append("未知待决事项：" + decision)
    texts = list(bundle["documents"].values()) + [bundle["assumptions"]]
    for doc in texts:
        cleaned = re.sub(r"(?:WCAG\s+2\.2|Python\s+3\.11)", "", doc)
        for ref in CLAUSE.findall(cleaned):
            if ref not in clauses:
                errors.append("文档未知条款：" + ref)
        for ref in ELEMENT.findall(doc):
            if ref not in elements:
                errors.append("文档未知要素：" + ref)
        for ref in DECISION.findall(doc):
            if ref not in decisions:
                errors.append("文档未知待决事项：" + ref)
    for line in bundle["assumptions"].splitlines():
        if re.match(r"\| H-WP6-\d{2} \|", line) and not DECISION.search(line):
            errors.append("H 条目缺少 E 编号")
    raw = json.dumps(bundle["sample"], ensure_ascii=False)
    personal = (r"(?<!\d)1[3-9]\d{9}(?!\d)", r"(?<!\d)\d{17}[\dXx](?!\d)",
                r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}")
    if any(re.search(pattern, raw) for pattern in personal):
        errors.append("样例含疑似真实个人信息形态")
    try:
        first = compute(bundle["sample"], metrics)
        if first != compute(bundle["sample"], metrics):
            errors.append("计算结果不确定")
    except (ValueError, KeyError, TypeError) as error:
        errors.append("合成计算失败：" + str(error))
    return errors


def main():
    bundle = load_bundle()
    errors = validate(bundle)
    if errors:
        print("\n".join(errors))
        return 1
    print(f'WP6 核验通过：{len(bundle["metrics"])} 个指标，'
          f'{len(bundle["conditions"])} 个放行条件；真实试点未执行。')
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
