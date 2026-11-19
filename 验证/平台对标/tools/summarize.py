#!/usr/bin/env python3
"""从矩阵生成 README 的规模、结果、主要发现；默认输出 Markdown。

--write 更新带标记段落，--check 只检查逐字一致性；不改矩阵。
"""

import argparse
from collections import Counter
import csv
from pathlib import Path
import re

from validate_governance import AI_RELATIONS, CATEGORIES, OWNERS, SUFFICIENCIES
from validate_openedx import STATUSES


BASE = Path(__file__).resolve().parents[1]
TABLES = {
    "OBJ": "表5-1 核心对象", "FLD-RES": "表6-2 Resource版本字段",
    "FLD-RGT": "表6-3 RightsRecord成员", "FLD-EVT": "表7-1 事件公共结构",
    "EVT": "表7-2 最小事件词表", "FLD-MAN": "表8-1 manifest成员",
    "FLD-COG": "表10-1 CognitiveState字段", "FLD-MTH": "表10-2 方法登记与批准",
}


def read_matrix(path):
    if not path.read_bytes().startswith(b"\xef\xbb\xbf"):
        raise ValueError("矩阵缺少UTF-8 BOM")
    with path.open(encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        rows = list(reader)
    required = {"要素编号", "要素名", "数据类别", "标准条款", "补齐路径(标准条款)",
                "缺失时补齐方", "AI应用接入关系", "标准定义充分性", "意见建议",
                "OpenEdX状态", "Moodle状态"}
    if not rows or not required.issubset(reader.fieldnames or []):
        raise ValueError("矩阵为空或缺少汇总所需列")
    ids = set()
    for row in rows:
        element = row["要素编号"]
        if (set(row) != set(reader.fieldnames) or any(v is None for v in row.values())
                or not element or element in ids or element.rsplit("-", 1)[0] not in TABLES):
            raise ValueError("矩阵行结构、编号或来源表无效")
        ids.add(element)
        if (row["数据类别"] not in CATEGORIES or row["标准定义充分性"] not in SUFFICIENCIES
                or any(row[p + "状态"] not in STATUSES for p in ("OpenEdX", "Moodle"))):
            raise ValueError(f"{element}：统计枚举非法")
        if any(owner not in OWNERS for owner in row["缺失时补齐方"].split("；")):
            raise ValueError(f"{element}：补齐方非法")
        if any(not re.fullmatch(r"(?:" + "|".join(AI_RELATIONS) + r")（.+）", item)
               for item in row["AI应用接入关系"].split("；")):
            raise ValueError(f"{element}：AI关系非法")
    return rows


def cell(value):
    return str(value).replace("|", "\\|").replace("\n", " ")


def table(headers, rows):
    return "\n".join(["| " + " | ".join(map(cell, headers)) + " |",
                       "| " + " | ".join("---" for _ in headers) + " |",
                       *("| " + " | ".join(map(cell, row)) + " |" for row in rows)])


def named(row):
    return f"`{row['要素编号']}` {row['要素名']}"


def generate(rows):
    sources = Counter(row["要素编号"].rsplit("-", 1)[0] for row in rows)
    scope = f"矩阵取自正文 **{len(sources)} 张表、{len(rows)} 行要素**，保留原表合并字段，不擅自拆行。\n\n"
    scope += table(["来源", "数据行数"], [(label, sources[prefix]) for prefix, label in TABLES.items()])
    scope += "\n\n类别按业务含义归入课程资源、教学过程与学习证据、认知诊断、公共与交换，而非仅按抽取表所在章节机械分组。"

    counts = {p: Counter(r[p + "状态"] for r in rows) for p in ("OpenEdX", "Moodle")}
    owners = Counter(owner for r in rows for owner in r["缺失时补齐方"].split("；"))
    ai = Counter(item.split("（", 1)[0] for r in rows for item in r["AI应用接入关系"].split("；"))
    sufficient = [r for r in rows if r["标准定义充分性"] == "充分"]
    d2 = [r for r in sufficient if "待D2" in r["补齐路径(标准条款)"]]
    samples = [r for r in rows if r["标准定义充分性"] == "需补样例"]
    ambiguities = [r for r in rows if r["标准定义充分性"] == "歧义"]
    gaps = [r for r in rows if r["标准定义充分性"] == "定义缺失"]
    both_missing = [r for r in rows if r["OpenEdX状态"] == r["Moodle状态"] == "缺失"]
    index = {r["要素编号"]: r for r in rows}

    def examples(*ids):
        return "、".join(named(index[key]) for key in ids if key in index)

    result = ["### 两平台状态交叉统计", "行轴为Open edX，列轴为Moodle；单元格表示同一要素的状态组合。边际合计可用于读取各平台状态分布。"]
    for category in (*CATEGORIES, "全部类别"):
        subset = rows if category == "全部类别" else [r for r in rows if r["数据类别"] == category]
        cross = Counter((r["OpenEdX状态"], r["Moodle状态"]) for r in subset)
        data = [(s, *(cross[s, t] for t in STATUSES), sum(cross[s, t] for t in STATUSES)) for s in STATUSES]
        data.append(("合计", *(sum(cross[s, t] for s in STATUSES) for t in STATUSES), len(subset)))
        result += [f"#### {category}", table(["Open edX ＼ Moodle", *STATUSES, "合计"], data)]
    result += [f"### 两平台都缺失的要素（{len(both_missing)}项）",
               table(["编号", "名称"], [(r["要素编号"], r["要素名"]) for r in both_missing]),
               "缺失是当前源码对标范围内的结论，不是生态内所有插件均不可能实现。应按矩阵责任和路径补齐，而不是删除标准约束。",
               "### 补齐方统计", "多选分别计数，不相加作为要素总数。",
               table(["补齐方", "要素行数"], [(owner, owners[owner]) for owner in OWNERS]),
               "### AI接入关系统计", "多选分别计数。AI禁止写入针对括号列明的操作，与同一行允许获准提议不矛盾。",
               table(["AI关系", "要素行数"], [(label, ai[label]) for label in AI_RELATIONS]),
               "### 标准定义充分性统计"]
    suff_rows = []
    for category in CATEGORIES:
        c = Counter(r["标准定义充分性"] for r in rows if r["数据类别"] == category)
        suff_rows.append((category, *(c[s] for s in SUFFICIENCIES), sum(c.values())))
    c = Counter(r["标准定义充分性"] for r in rows)
    suff_rows.append(("合计", *(c[s] for s in SUFFICIENCIES), len(rows)))
    result += [table(["数据类别", *SUFFICIENCIES, "合计"], suff_rows)]

    cognitive = {p: Counter(r[p + "状态"] for r in rows if r["数据类别"] == "认知诊断") for p in counts}
    findings = ["## 5. 主要发现", "### a) 平台不是标准语义的基线",
        f"在{len(rows)}行中，Open edX原生{counts['OpenEdX']['原生']}项、部分{counts['OpenEdX']['部分']}项；"
        f"Moodle原生{counts['Moodle']['原生']}项、部分{counts['Moodle']['部分']}项。应准确表述为两平台均以‘部分’为主，而非‘几乎全部’都部分。"
        f"认知诊断中，Open edX缺失{cognitive['OpenEdX']['缺失']}项、部分{cognitive['OpenEdX']['部分']}项；"
        f"Moodle缺失{cognitive['Moodle']['缺失']}项、部分{cognitive['Moodle']['部分']}项。",
        f"代表性要素为{examples('OBJ-005', 'OBJ-006', 'OBJ-008', 'OBJ-037', 'OBJ-040', 'OBJ-041')}。"
        "Open edX的course run不能直接等同课程版本与开课的分离模型；Moodle虽有能力证据、分析模型及版本，仍不等于标准认知状态和用途批准。标准必须自带对象、事件和验证定义，不能以任一平台为基线。",
        "### b) 语义有规可循，机器契约仍是前置",
        f"{len(rows)}项中判‘充分’{len(sufficient)}项，其中补齐路径标注‘待D2’{len(d2)}项。"
        + ("即本矩阵的‘充分’项全部仍有D2契约交付前置。" if sufficient and len(d2) == len(sufficient) else "") +
        "‘待D2’表示按正文交付安排仍需冻结结构/适用性契约，不表示每项都同时缺少Schema、逐事件定义、词表和夹具，也不是对D2实际发布物的独立盘点。",
        "据此，当前AI应用‘有规可循’在语义层成立，在跨应用机器可校验层尚不成立；D2契约是接入的关键前置。"
        f"如{examples('FLD-EVT-002', 'FLD-EVT-004', 'FLD-EVT-020', 'FLD-MTH-011')}，应按正文4.1.2、5.4、7.3.3、8.11及E12发布同版本Schema、逐事件定义、词表和正反夹具。不能用平台私有字段补写未冻结的公共契约。",
        "### c) 校级公共职责不得下放给平台或AI自行决定",
        f"矩阵有{owners['校级公共服务']}项列入‘校级公共服务’补齐责任；这是多选涉及行数，不是独立服务数量。"
        f"代表性要素包括{examples('FLD-EVT-001', 'OBJ-001', 'FLD-EVT-021', 'FLD-EVT-022', 'FLD-MAN-017', 'EVT-003', 'OBJ-041')}。",
        "按A.3/A.8，首次受理event_id、标识映射与成对学习者假名、学校接收/登记回执、撤权传播和方法准入权威校验由校级公共服务承担。"
        "平台及应用仍负责源事实、源端保存、适配与本地撤权；学校管理负责人工审定和批准。厂商可受托建设公共服务，但不能因此以普通平台或AI应用身份自行生成权威决定。",
        "### d) AI接入按操作而非按对象整体放权",
        f"允许任务获准读取输入的范围涉及{ai['AI读取输入']}项，例如{examples('OBJ-020', 'OBJ-030', 'OBJ-037')}；"
        "不代表可读取全量数据或默认外发，仍受最小化、授权及外发网关控制。",
        f"列入‘AI写入提议’{ai['AI写入提议']}项，例如{examples('OBJ-023', 'OBJ-024', 'OBJ-034', 'EVT-018')}。拟入正式记录的输出只能是待确认提议，不能自动确认或发布。",
        f"列入‘AI写入认知记录’{ai['AI写入认知记录']}项，例如{examples('OBJ-037', 'OBJ-038', 'OBJ-039', 'EVT-022', 'EVT-023')}，须声明P-AI与P-DIA并通过10.13的方法、版本、批准范围、用途和有效期校验；不能据此取得正式评分权限。",
        f"列入‘AI禁止写入’{ai['AI禁止写入']}项，例如{examples('FLD-EVT-001', 'FLD-EVT-022', 'EVT-019', 'EVT-020', 'EVT-021')}。"
        "禁止项包括接收端专属赋值、冒充人员生成真实事实以及确认/更正/归档、发布、导出和授权操作；不否认同一对象上的提议权限。",
        f"‘不直接涉及’{ai['不直接涉及']}项。另须避免将{examples('OBJ-032', 'EVT-016', 'EVT-008')}误判为一律只能提议：9.5.1 b)、9.5.6允许获准的即时帮助直接呈现，讨论引导还须满足7.3.6 b)，矩阵在括号中说明其边界。",
        "### e) 按条款提交样例与歧义意见",
        f"需补样例{len(samples)}项、歧义{len(ambiguities)}项、定义缺失{len(gaps)}项。以下为全部需补样例条目；完整‘问题/建议’见CSV的意见建议列。",
        table(["编号", "要素名", "评议条款"], [(r['要素编号'], r['要素名'], r['意见建议'].split('】', 1)[0].lstrip('【')) for r in samples])]
    for r in ambiguities + gaps:
        findings += [f"**{named(r)}（{r['标准定义充分性']}）**", r["意见建议"]]
    findings += ["拟通过站内意见表单按对应条款提交上述评议；本次只整理材料，尚未提交意见，也未修改标准正文。不得为适配平台而放宽标准。"]
    return {"scope": scope, "results": "\n\n".join(result), "findings": "\n\n".join(findings)}


def block(name, content):
    return f"<!-- summarize:{name}:start -->\n{content}\n<!-- summarize:{name}:end -->"


def synchronize(readme, sections):
    for name, content in sections.items():
        pattern = re.compile(r"<!-- summarize:" + name + r":start -->\n(?:.*?\n)?<!-- summarize:" + name + r":end -->", re.DOTALL)
        if len(pattern.findall(readme)) != 1:
            raise ValueError(f"README的{name}统计标记缺失或重复")
        readme = pattern.sub(lambda _: block(name, content), readme)
    return readme


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--matrix", type=Path, default=BASE / "数据要素对照矩阵.csv")
    parser.add_argument("--readme", type=Path, default=BASE / "README.md")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--write", action="store_true")
    mode.add_argument("--check", action="store_true")
    args = parser.parse_args()
    sections = generate(read_matrix(args.matrix))
    if not (args.write or args.check):
        print("\n\n".join(block(name, content) for name, content in sections.items()))
        return
    current = args.readme.read_text(encoding="utf-8")
    expected = synchronize(current, sections)
    if args.write:
        args.readme.write_text(expected, encoding="utf-8")
        print("已从CSV更新README的scope/results/findings统计段落")
    elif current != expected:
        parser.exit(1, "FAIL: README统计段落与CSV实时汇总不一致，请运行summarize.py --write\n")
    else:
        print("PASS: summarize输出与README的scope/results/findings段落逐字一致")


if __name__ == "__main__":
    main()
