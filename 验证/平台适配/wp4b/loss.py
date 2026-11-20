"""Join observed output with the authoritative matrix; do not extrapolate sample gaps."""
import csv
import io
import json

from wp4b.common import CONTRACT, EVIDENCE, ROOT, check_field

MATRIX = ROOT.parent / "平台对标" / "数据要素对照矩阵.csv"
EXTENSION = "需平台扩展"
SERVICE = "需公共服务补齐"
UNAVAILABLE = "无法取得"
CONVERTED = "已转换"

# A missing prerequisite is distinct from the platform's ability to supply it.
REASONS = [
    (SERVICE, "身份、权利及保护引用须权威登记；用户表不是登记结果。",
     "OBJ-001 OBJ-002 OBJ-003 OBJ-004 OBJ-007 OBJ-010 OBJ-022 OBJ-042 OBJ-043 OBJ-044 OBJ-045 OBJ-046"),
    (SERVICE, "须有正式学期、授课关系、考核方案和具体历史课程版本。",
     "OBJ-006 OBJ-024 OBJ-025"),
    (SERVICE, "修读轮次及前序关系来自学校；重交、补考尝试或重新选课不能代替。",
     "OBJ-008 OBJ-009"),
    (EXTENSION, "当前内容导出不是可核验的版本历史；需发布时留存快照和引用。",
     "OBJ-005 OBJ-013 OBJ-014 EVT-001"),
    (EXTENSION, "需在形成时保存版本、作品、提交的可靠状态和适用的成员快照。",
     "OBJ-012 OBJ-020 OBJ-029 OBJ-030 OBJ-031 EVT-004 EVT-006 EVT-011 EVT-012 EVT-013 EVT-014 "
     "FLD-EVT-014 FLD-EVT-015 FLD-EVT-016 FLD-EVT-019"),
    (EXTENSION, "播放请求或查看日志没有有效区间、能力声明和缺失说明；不可推断真实观看。",
     "OBJ-021 EVT-005"),
    (SERVICE, "版本化权利档案、保护策略、资源分类/词表或受控存储须登记。",
     "FLD-RES-002 FLD-RES-003 FLD-RES-005 FLD-RES-007 FLD-RES-008 FLD-RES-009 FLD-RES-014"),
    (SERVICE, "接收端或权威注册字段未发生；不把原生或 ERB 标识、时间当学校接收或认证证据。",
     "FLD-EVT-001 FLD-EVT-004 FLD-EVT-005 FLD-EVT-012 FLD-EVT-013 FLD-EVT-018 FLD-EVT-021 "
     "FLD-EVT-022 FLD-EVT-023 EVT-003"),
    (EXTENSION, "需同时留存业务来源、接收语义和精确引用；原生日志/传输值组合不等于候选信封。",
     "FLD-EVT-002 FLD-EVT-003 FLD-EVT-006 FLD-EVT-007 FLD-EVT-008 FLD-EVT-009 FLD-EVT-010 "
     "FLD-EVT-011 FLD-EVT-017 FLD-EVT-020 EVT-002"),
    (EXTENSION, "原生评分历史/反馈不是人工确认、授权和可追加的决定链。",
     "OBJ-033 OBJ-034 OBJ-035 EVT-017 EVT-018 EVT-019 EVT-020 EVT-021"),
    (SERVICE, "没有冻结的导出任务、授权范围、权利结论或校级回执；离线诊断包不充当正式交换包。",
     "FLD-MAN-001 FLD-MAN-002 FLD-MAN-004 FLD-MAN-005 FLD-MAN-006 FLD-MAN-007 FLD-MAN-011 "
     "FLD-MAN-016 FLD-MAN-017"),
    (EXTENSION, "诊断清单可列出文件与缺口，但没有具备引用闭包的候选契约交换清单。",
     "FLD-MAN-003 FLD-MAN-008 FLD-MAN-009 FLD-MAN-010 FLD-MAN-012 FLD-MAN-013 FLD-MAN-014 FLD-MAN-015"),
]
POLICY = {key: (status, reason) for status, reason, keys in REASONS for key in keys.split()}


def remediation(element):
    if element.startswith("FLD-RGT-"):
        return SERVICE, "需权利档案和学校审定；不能从原生文件许可标签默认投影。"
    if element.startswith("FLD-MTH-") or element in {"OBJ-040", "OBJ-041"}:
        return SERVICE, "样本没有方法注册、验证或用途准入，不能从内部配置推断。"
    if element.startswith("FLD-COG-") or element in {"OBJ-037", "OBJ-038", "EVT-022", "EVT-023", "EVT-024"}:
        return UNAVAILABLE, "未执行诊断、推荐或干预；不能用答题结果或平台推荐近似物代替。"
    return POLICY.get(element, (UNAVAILABLE, "未见可复核的目标语义；不据静态近似物或未取样能力补造。"))


def native_sources(platform, observed):
    files = set()
    for r in observed:
        files.update(s.split("#", 1)[0] for s in r["sources"])
    return ";".join(f"{platform}/samples/{x}" for x in sorted(files))


def loss_rows(projections):
    scope = json.loads((CONTRACT / "scope.json").read_bytes())
    in_scope = set(scope["element_ids"])
    passed = {p.platform: {id(record) for record in p.passed} for p in projections}
    with MATRIX.open(encoding="utf-8-sig", newline="") as source:
        matrix = list(csv.DictReader(source))
    assert in_scope <= {r["要素编号"] for r in matrix}
    for row in matrix:
        element = row["要素编号"]
        for p in projections:
            platform = p.platform
            static = "Moodle" if platform == "moodle" else "OpenEdX"
            observed = [r for r in [*p.records, *p.observations]
                        if element in r["elements"] or element in r.get("fields", {}).values()]
            mapped = []
            for record in p.records:
                fields = [key for key, eid in record["fields"].items() if eid == element]
                for pointer in fields:
                    check_field(record["instance"], pointer)
                if fields or (element in record["elements"] and id(record) in passed[platform]):
                    mapped.append(record)
            status, reason = remediation(element)
            if mapped:
                status = CONVERTED
                reason = ("所列成员从原生证据转换；不计为所在对象整体通过。"
                          if all(element in r["fields"].values() for r in mapped)
                          else "候选输入通过 WP1；权威引用及业务前置条件未核验。")
            if element in {"FLD-EVT-020", "FLD-EVT-015", "FLD-EVT-016"} and mapped:
                reason = "所列记录中转换了该字段；部分事件及引用解析仍不足。"
            if element == "EVT-002" and observed:
                reason = ("tracking/历史有变化证据，ERB 标识不能替代学校修读及采集实例。"
                          if platform == "openedx" else "更新日志没有新旧状态；当前名单不是历史变化。")
            if element == "FLD-EVT-020" and not mapped:
                reason = "没有足够源证据构建候选载荷。"
            if element.startswith("FLD-MAN-"):
                reason += " WP1 清单候选见 manifest-attempt.json。"
            coverage = int(row[static + "覆盖度"])
            if mapped:
                comparison = "样本证实较多" if coverage < 2 else "样本支持映射"
            elif coverage >= 2 and (observed or element.startswith("FLD-MAN-")):
                comparison = "样本低于静态潜力"
            elif not observed:
                comparison = "未获动态证据，不推翻"
            else:
                comparison = "观察到部分事实，未推翻"
            yield dict(element_id=element, element=row["要素名"], clause=row["标准条款"],
                       platform=platform, wp1_scope="首批" if element in in_scope else "首批外参考",
                       status=status, observed_records=len(observed), mapped_records=len(mapped),
                       evidence=(EVIDENCE if observed else
                                 EVIDENCE + "＋离线包生成检查" if element.startswith("FLD-MAN-") else "静态推断／未执行"),
                       static_status=row[static + "状态"], static_coverage=coverage, comparison=comparison,
                       reason=reason, sources=native_sources(platform, observed),
                       output=f"{platform}/adapter/convert.py;wp4b/run.py;wp4b/test_wp4b.py",
                       runtime_output=f"{platform}/manifest-attempt.json" if element.startswith("FLD-MAN-") else
                       f"{platform}/candidate-passed.json;{platform}/candidate-blocked.json;{platform}/native-evidence.json")


def csv_bytes(rows):
    buf = io.StringIO(newline="")
    writer = csv.DictWriter(buf, fieldnames=list(rows[0]), lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return buf.getvalue().encode()
