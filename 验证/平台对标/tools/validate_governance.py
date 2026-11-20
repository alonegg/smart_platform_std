"""治理五列的语法、一致性及正文规定的关键责任边界校验。

完整入口：python3 -B 验证/平台对标/tools/validate_openedx.py
条款解释与意见的实质判断仍需人工审阅，语法通过不等于标准符合性。
"""

from collections import Counter
import re


SUFFICIENCIES = ("充分", "需补样例", "歧义", "定义缺失")
OWNERS = ("无需补齐", "平台适配器", "平台扩展开发", "校级公共服务", "接入应用", "学校管理")
AI_RELATIONS = ("AI读取输入", "AI写入提议", "AI写入认知记录", "AI禁止写入", "不直接涉及")
CATEGORIES = ("课程资源", "教学过程与学习证据", "认知诊断", "公共与交换")
REQUIRED = ("缺失时补齐方", "补齐路径(标准条款)", "AI应用接入关系", "标准定义充分性")


def validate_governance(rows):
    if len(rows) != 166:
        raise ValueError("治理校验要求 166 行")
    counts = {category: Counter() for category in CATEGORIES}
    owners_count = Counter()
    ai_count = Counter()
    issues = []
    for row in rows:
        element = row["要素编号"]
        if any(not isinstance(row.get(key), str) or not row[key].strip() for key in REQUIRED):
            raise ValueError(f"{element}：治理必填列空白")
        if row["数据类别"] not in CATEGORIES:
            raise ValueError(f"{element}：非法数据类别")
        owners = row["缺失时补齐方"].split("；")
        if any(owner not in OWNERS for owner in owners) or len(set(owners)) != len(owners):
            raise ValueError(f"{element}：非法或重复补齐方")
        native = row["OpenEdX状态"] == row["Moodle状态"] == "原生"
        if (native and owners != ["无需补齐"]) or (not native and "无需补齐" in owners):
            raise ValueError(f"{element}：无需补齐与两平台状态不一致")
        if not re.search(r"\d+\.\d+", row["补齐路径(标准条款)"]):
            raise ValueError(f"{element}：补齐路径缺少条款号")
        sufficiency = row["标准定义充分性"]
        if sufficiency not in SUFFICIENCIES:
            raise ValueError(f"{element}：非法充分性")
        opinion = row.get("意见建议")
        if not isinstance(opinion, str):
            raise ValueError(f"{element}：意见建议列缺失")
        if sufficiency == "充分":
            if opinion != "":
                raise ValueError(f"{element}：充分时意见建议必须为空")
        elif not re.fullmatch(r"【[^】]*\d[^】]*】问题：.+；建议：.+", opinion):
            raise ValueError(f"{element}：非充分项意见须含【条款号】问题：…；建议：…")
        relations = []
        for relation in row["AI应用接入关系"].split("；"):
            match = re.fullmatch(r"(AI读取输入|AI写入提议|AI写入认知记录|AI禁止写入|不直接涉及)（(.+)）", relation)
            if not match or not re.search(r"\d+\.\d+|A\.2", match[2]):
                raise ValueError(f"{element}：非法AI关系或缺少括号条款依据")
            relations.append(match[1])
            if match[1] == "AI写入认知记录" and not all(term in match[2] for term in ("P-DIA", "10.13")):
                raise ValueError(f"{element}：认知写入缺少P-DIA/方法准入限制")
        if len(set(relations)) != len(relations):
            raise ValueError(f"{element}：AI关系重复")
        if "不直接涉及" in relations and len(relations) != 1:
            raise ValueError(f"{element}：不直接涉及不能与直接关系并列")
        if element in {"FLD-EVT-001", "FLD-EVT-021", "FLD-EVT-022"}:
            if owners != ["校级公共服务"] or relations != ["AI禁止写入"]:
                raise ValueError(f"{element}：接收端专属字段责任或AI边界错误")
        if element == "OBJ-041" or (element.startswith("FLD-MTH-") and int(element[-3:]) >= 8):
            if not {"校级公共服务", "学校管理"}.issubset(owners) or "AI禁止写入" not in relations:
                raise ValueError(f"{element}：方法批准缺少学校审定/公共准入责任或AI限制")
        if element in {"EVT-019", "EVT-020", "EVT-021"}:
            if "AI禁止写入" not in relations or "AI写入认知记录" in relations:
                raise ValueError(f"{element}：确认/更正/归档不得由AI写入")
        counts[row["数据类别"]][sufficiency] += 1
        owners_count.update(owners)
        ai_count.update(relations)
        if sufficiency in ("歧义", "定义缺失"):
            issues.append((element, row["要素名"], opinion))
    return counts, owners_count, ai_count, issues


def report(counts, owners_count, ai_count, issues):
    print("PASS: 166/166 行治理必填列已填；补齐方、AI关系及充分性枚举合法")
    print("PASS: 充分项意见为空；其余意见均含【条款号】及问题/建议；无需补齐与两平台皆原生一致")
    print("PASS: 接收端专属字段、方法批准及确认/更正/归档的责任与AI禁止写入边界检查通过")
    print("数据类别,充分,需补样例,歧义,定义缺失,合计")
    total = Counter()
    for category in CATEGORIES:
        count = counts[category]
        print(",".join([category, *(str(count[s]) for s in SUFFICIENCIES), str(sum(count.values()))]))
        total.update(count)
    print(",".join(["合计", *(str(total[s]) for s in SUFFICIENCIES), str(sum(total.values()))]))
    print("补齐方,行数（多选分别计数）")
    for owner in OWNERS:
        print(f"{owner},{owners_count[owner]}")
    print("AI应用接入关系,行数（多选分别计数）")
    for relation in AI_RELATIONS:
        print(f"{relation},{ai_count[relation]}")
    print("歧义/定义缺失意见：")
    for element, name, opinion in issues:
        print(f"{element} {name}：{opinion}")
