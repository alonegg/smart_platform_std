#!/usr/bin/env python3
"""从CSV及正文生成研究报告的证据段；--write更新，--check逐字校验。"""

import argparse
from collections import Counter
import hashlib
from pathlib import Path
import re

from summarize import BASE, named, read_matrix, synchronize, table
from validate_governance import AI_RELATIONS, CATEGORIES, OWNERS, SUFFICIENCIES
from validate_openedx import PLATFORMS


STANDARD = BASE.parents[1] / "标准/评审稿/智慧教学-数据模型标准.md"
REPORT = BASE / "研究报告-标准初稿可实现性与接入性评估.md"
FOCUS = {
    "课程资源": ("OBJ-005", "OBJ-020", "OBJ-021", "OBJ-022", "OBJ-023", "OBJ-024", "FLD-RES-001", "FLD-RES-012"),
    "教学过程与学习证据": ("OBJ-009", "OBJ-012", "OBJ-030", "OBJ-031", "OBJ-032", "OBJ-034", "FLD-EVT-001", "EVT-008", "EVT-016", "EVT-019"),
    "认知诊断": ("OBJ-037", "OBJ-038", "OBJ-039", "OBJ-040", "OBJ-041", "FLD-COG-003", "FLD-MTH-001"),
    "公共与交换": ("OBJ-001", "OBJ-008", "OBJ-042", "OBJ-044", "FLD-MAN-009", "FLD-MAN-017"),
}


def standard_metrics(source):
    clauses = re.findall(r"^((?:\d+|[A-Z])(?:\.\d+)+)\s", source, re.MULTILINE)
    if not source.strip() or not clauses:
        raise ValueError("正文为空或未找到编号条款")
    if len(clauses) != len(set(clauses)):
        raise ValueError("正文编号条款重复")
    decisions = []
    for line in source.splitlines():
        if re.match(r"^\| E\d+ \|", line):
            cells = [cell.strip() for cell in line.strip("|").split("|")]
            decisions.append((cells[0], cells[1], cells[-1]))
    if len({row[0] for row in decisions}) != len(decisions):
        raise ValueError("待决事项编号重复")
    subitems = re.findall(r"^\| (E23[a-z])\s", source, re.MULTILINE)
    stages = re.findall(r"^\| (D\d+)\s", source, re.MULTILINE)
    return {"characters": len(source), "han": len(re.findall(r"[\u4e00-\u9fff]", source)),
            "shall": source.count("应"), "clauses": len(clauses),
            "detailed_clauses": sum(bool(re.match(r"^\d", c)) or c.count(".") >= 2 for c in clauses),
            "decisions": decisions, "subitems": subitems, "stages": stages}


def average(rows, platform):
    return f"{sum(int(r[platform + '覆盖度']) for r in rows) / len(rows):.2f}" if rows else "—"


def distribution(rows):
    data = []
    for platform in PLATFORMS:
        counts = Counter(r[platform + "覆盖度"] for r in rows)
        data.append((platform, *(counts[str(i)] for i in range(4)), len(rows), average(rows, platform)))
    return table(["平台", "0 缺失", "1 弱对应", "2 可适配", "3 原生", "合计", "均值"], data)


def responsibilities(rows):
    owners = Counter(item for row in rows for item in row["缺失时补齐方"].split("；"))
    ai = Counter(item.split("（", 1)[0] for row in rows for item in row["AI应用接入关系"].split("；"))
    return "\n\n".join([
        "补齐责任与AI关系均为多选涉及行数，不是服务数量、开发工时或可任意替代的角色。",
        table(["补齐责任", "涉及行数"], [(o, owners[o]) for o in OWNERS]),
        table(["AI接入关系", "涉及行数"], [(a, ai[a]) for a in AI_RELATIONS]),
    ])


def evidence(rows, ids):
    index = {row["要素编号"]: row for row in rows}
    data = []
    for key in ids:
        if key not in index:
            continue
        row = index[key]
        for platform in PLATFORMS:
            data.append((named(row), row["标准条款"], platform,
                         row[platform + "覆盖度"], row[platform + "对应"], row[platform + "依据"]))
    return table(["要素", "标准条款", "平台", "覆盖度", "已存事实与差异", "源码路径/搜索范围"], data)


def domain(rows, category):
    subset = [row for row in rows if row["数据类别"] == category]
    adaptable = []
    for platform in PLATFORMS:
        for row in subset:
            if row[platform + "覆盖度"] == "2":
                description = row[platform + "对应"]
                reason = description.split("〔覆盖度2：", 1)[-1].removesuffix("〕")
                adaptable.append((platform, named(row), reason, row["标准条款"], row[platform + "依据"]))
    suff = Counter(row["标准定义充分性"] for row in subset)
    issues = [row for row in subset if row["标准定义充分性"] != "充分"]
    return "\n\n".join([
        f"本领域共{len(subset)}行。分值分布与等权均值如下；弱对应不算已经可适配。",
        distribution(subset), "#### 可适配项及其转换依据（全部列出）",
        table(["平台", "要素", "为何只需适配", "条款", "源码路径"], adaptable),
        "#### 关键弱对应/缺失的证据定位",
        evidence(subset, FOCUS[category]),
        "#### 补齐责任与AI接入关系", responsibilities(subset),
        "#### 标准自身的定义问题",
        table(["充分性", "行数"], [(s, suff[s]) for s in SUFFICIENCIES]),
        table(["要素", "充分性", "完整评议意见"],
              [(named(row), row["标准定义充分性"], row["意见建议"]) for row in issues]),
        "以上是矩阵评议，不是已提交或已采纳的标准修订；充分项也不等于机器契约已经交付。",
    ])


def generate(rows, source):
    if not rows:
        raise ValueError("研究报告不能使用空矩阵")
    metrics = standard_metrics(source)
    subsets = {category: [row for row in rows if row["数据类别"] == category] for category in CATEGORIES}
    suff = Counter(row["标准定义充分性"] for row in rows)
    d2 = sum(row["标准定义充分性"] == "充分" and "待D2" in row["补齐路径(标准条款)"] for row in rows)
    native = {p: sum(row[p + "覆盖度"] == "3" for row in subsets["课程资源"]) for p in PLATFORMS}
    weak = {p: sum(row[p + "覆盖度"] == "1" for row in subsets["认知诊断"]) for p in PLATFORMS}
    trajectories = "；".join(f"{p}：" + " / ".join(average(subsets[c], p) for c in CATEGORIES[:3]) for p in PLATFORMS)
    summary = (
        f"矩阵共{len(rows)}行。按课程资源／教学过程与学习证据／认知诊断的顺序，覆盖度均值为：**{trajectories}**。"
        f"课程资源原生项为Open edX {native['OpenEdX']}项、Moodle {native['Moodle']}项；认知诊断弱对应分别为"
        f"{weak['OpenEdX']}项、{weak['Moodle']}项。这里只证明本样本的适配距离次序，不是符合性或统计显著性检验。"
    )
    content = {
        "report-abstract": summary,
        "report-hypothesis": "\n\n".join([
            "#### 不依赖分值等距假设的补充读数",
            table(["类别", "平台", "原生项", "原生占比", "可适配或原生项", "可适配或原生占比"], [
                (category, p, sum(r[p + "覆盖度"] == "3" for r in subset),
                 f"{sum(r[p + '覆盖度'] == '3' for r in subset) / len(subset):.1%}" if subset else "—",
                 sum(int(r[p + "覆盖度"]) >= 2 for r in subset),
                 f"{sum(int(r[p + '覆盖度']) >= 2 for r in subset) / len(subset):.1%}" if subset else "—")
                for category, subset in subsets.items() for p in PLATFORMS]),
            "#### 对象、字段与事件的分母检查",
            table(["类别", "要素类型", "行数", "OpenEdX均值", "Moodle均值"], [
                (category, kind, len(part), *(average(part, p) for p in PLATFORMS))
                for category, subset in subsets.items() for kind in dict.fromkeys(r["要素类型"] for r in subset)
                if (part := [r for r in subset if r["要素类型"] == kind])]),
            "只保留对象行时，Moodle按课程资源／学习过程／认知诊断的均值为：" +
            " / ".join(average([r for r in subsets[c] if r["要素类型"] == "对象"], "Moodle") for c in CATEGORIES[:3]) +
            "。这说明全类别均值的方向不能直接外推为所有要素类型的方向，应结合对象/字段构成解读。",
            "上述分层用于暴露样本构成，不把对象与其成员当作互相独立的重复验证。",
        ]),
        "report-scope": f"研究样本为{len(rows)}行，来源表数量为{len(set(r['要素编号'].rsplit('-', 1)[0] for r in rows))}；"
                        "对象、字段、事件及合并字段等权，存在层次重叠，不是独立观测。\n\n" +
                        table(["类别", "行数"], [(c, len(subsets[c])) for c in CATEGORIES]),
        "report-overall": "\n\n".join([
            "### 全样本覆盖度", distribution(rows),
            "### 全样本定义充分性",
            table(["充分性", "行数"], [(s, suff[s]) for s in SUFFICIENCIES]),
            f"充分项中补齐路径标记待D2的有{d2}项。标记表示契约冻结前置，不表示每项都同时缺少所有附件，也不是独立的D2发布物审计。",
            responsibilities(rows),
        ]),
        "report-text": "\n\n".join([
            table(["正文指标", "脚本实测", "口径"], [
                ("UTF-8解码后的Unicode字符", metrics["characters"], "含Markdown、空白和换行，不等于汉字数"),
                ("约万字符", f"{metrics['characters'] / 10000:.1f}", "上项除以万后取一位小数"),
                ("基本汉字区字符", metrics["han"], "U+4E00–U+9FFF"),
                ("应字出现次数", metrics["shall"], "全文字面计数，含不应、表格和说明；不等于独立强制要求数"),
                ("行首编号段落（不含Markdown标题）", metrics["clauses"], "含附录E.1引导段，不含列表a/b/c"),
                ("扣除附录章级引导段后的编号条款", metrics["detailed_clauses"], "正文数字编号段落及附录至少两级小数编号段落"),
                ("表E.1主事项", len(metrics["decisions"]), "按E编号计数，不认定均已解决"),
                ("E23分项", len(metrics["subitems"]), "独立跟踪：" + "、".join(metrics["subitems"])),
                ("拆分E23后的跟踪单元", len(metrics["decisions"]) - bool(metrics["subitems"]) + len(metrics["subitems"]), "替换主项，不重复相加"),
                ("表D.1阶段", len(metrics["stages"]), "、".join(metrics["stages"])),
            ]),
            "因此，文稿体量不能只称为汉字数；编号条款的既有说法对应排除附录引导段的口径。"
            "实施安排不止技术冻结与试点，还包括常态维护阶段。文字规模和应字频率只能提示阅读/维护负担，不能据此推算工期或证明标准不可实施。",
            "外部采用与版本核定的代表待决项：",
            table(["事项", "待决内容", "节点"], [d for d in metrics["decisions"] if d[0] in {f"E{i:02d}" for i in range(6, 12)}]),
        ]),
    }
    for key, category in zip(("course", "process", "cognition", "public"), CATEGORIES):
        content["report-" + key] = domain(rows, category)
    return content


def input_hashes(*paths):
    return table(["输入文件", "SHA-256"], [
        (path.name, hashlib.sha256(path.read_bytes()).hexdigest()) for path in paths])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--matrix", type=Path, default=BASE / "数据要素对照矩阵.csv")
    parser.add_argument("--standard", type=Path, default=STANDARD)
    parser.add_argument("--report", type=Path, default=REPORT)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--write", action="store_true")
    mode.add_argument("--check", action="store_true")
    args = parser.parse_args()
    rows = read_matrix(args.matrix)
    source = args.standard.read_text(encoding="utf-8")
    sections = generate(rows, source)
    sections["report-inputs"] = input_hashes(args.matrix, args.standard)
    if not (args.write or args.check):
        print(synchronize("\n\n".join(f"<!-- summarize:{key}:start -->\n<!-- summarize:{key}:end -->" for key in sections), sections))
        return
    current = args.report.read_text(encoding="utf-8")
    expected = synchronize(current, sections)
    if args.write:
        args.report.write_text(expected, encoding="utf-8")
        print("已从CSV和标准正文更新研究报告的统计、逐项证据及输入摘要")
    elif current != expected:
        parser.exit(1, "FAIL: 研究报告证据段已过期，请运行report_stats.py --write\n")
    else:
        print("PASS: 研究报告统计、逐项源码依据及正文指标与输入逐字一致")


if __name__ == "__main__":
    main()
