"""附录 A.6；四值结果，跳过不计为通过。"""
from collections import Counter
import importlib.util
import json

from . import ROOT, __version__
from .context import Context
from .profiles import CASE_IDS, PROFILES, select

LABELS = {"passed": "通过", "failed": "不通过", "skipped": "跳过", "not_applicable": "不适用"}
EVIDENCE = "合成样例通过（4.4.5.2）；非认证/非 D2 冻结/非真实平台数据"


def metadata(case_id):
    path = ROOT / "cases" / case_id / "case.json"
    if path.exists():
        return json.loads(path.read_text())
    return dict(case_id=case_id, title=case_id + "（未实现）", clauses=[], elements=[],
                profiles=[p for p, v in PROFILES.items() if case_id in v["basic"]],
                bearer="未实现，未声明承担观察点", handoff="未执行", observations=[], out_of_tool_scope=[])


def counts(values):
    c = Counter(values)
    return {k: c[k] for k in LABELS}


def run(target, target_name, role, profiles, grd_stages=("P", "C", "A", "R"), cases=None, triggers=()):
    selected = select(profiles, grd_stages, triggers)
    if cases is not None and set(cases) - set(CASE_IDS):
        raise ValueError("unknown case")
    results = []
    for case_id in CASE_IDS:
        meta = metadata(case_id)
        expected = meta.pop("observations")
        observations = []
        status, reason = "not_applicable", "声明 Profile " + ", ".join(profiles) + " 按表 A.9 未选择该用例"
        if case_id in selected:
            status, reason = "skipped", "首批未实现该用例"
            if cases is not None and case_id not in cases:
                reason = "--cases 未选"
            elif (ROOT / "cases" / case_id / "check.py").is_file() and case_id not in ("T08", "T12", "T20"):
                if not target.admin_token:
                    reason = "前置条件缺失：HTTP 无管理令牌"
                else:
                    try:
                        spec = importlib.util.spec_from_file_location("wp3_" + case_id.replace("-", "_"), ROOT / "cases" / case_id / "check.py")
                        module = importlib.util.module_from_spec(spec)
                        spec.loader.exec_module(module)
                        actual = module.run(Context(target, case_id))
                        by_id = {o["id"]: o for o in actual}
                        if len(by_id) != len(actual) or set(by_id) - {e["id"] for e in expected}:
                            raise ValueError("duplicate or undeclared observation")
                        for exp in expected:
                            obs = by_id.get(exp["id"], dict(id=exp["id"], status="skipped", actual="未返回必需观察点", detail="前置观察未完成"))
                            if obs["status"] not in ("passed", "failed", "skipped"):
                                raise ValueError("invalid observation status")
                            observations.append({**exp, **obs})
                        status = "failed" if any(o["status"] == "failed" for o in observations) else "skipped" if not observations or any(o["status"] == "skipped" for o in observations) else "passed"
                        reason = "必需观察点跳过" if status == "skipped" else "观察点全部通过" if status == "passed" else "观察点不通过"
                    except Exception as exc:
                        status, reason = "failed", "被测异常或无法解析：" + type(exc).__name__
                        observations = [{**e, "status": "failed", "actual": "执行异常：" + type(exc).__name__, "detail": "未记录响应或凭证"} for e in expected]
            if case_id in triggers:
                reason += "；显式 --trigger " + case_id
        for obs in observations:
            obs["status_label"] = LABELS[obs["status"]]
        results.append({**meta, "status": status, "status_label": LABELS[status], "reason": reason, "observations": observations})
    for parent in ("T08", "T12", "T20"):
        row = next(c for c in results if c["case_id"] == parent)
        children = [c for c in results if c["case_id"].startswith(parent + "-")]
        statuses = {c["status"] for c in children}
        status = next((s for s in ("failed", "skipped", "passed") if s in statuses), "not_applicable")
        row.update(container=True, status=status, status_label=LABELS[status],
                   reason="父项按子用例聚合，不重复计数", title=parent + " 子用例汇总", observations=[],
                   bearer="按子用例承担方", handoff="按子用例交接点")
    summary = {"cases": counts(c["status"] for c in results if not c.get("container")), "observations": counts(o["status"] for c in results for o in c["observations"])}
    overall = "failed" if summary["cases"]["failed"] else "incomplete" if summary["cases"]["skipped"] else "passed"
    return dict(tool="wp3-conformance", tool_version=__version__, contract_version="0.1.0-candidate", target=target_name, role=role,
                profiles=list(profiles), grd_stages=list(grd_stages), triggers=list(triggers), evidence_scope=EVIDENCE,
                summary=summary, overall=overall, cases=results)


def exit_code(result):
    return {"passed": 0, "failed": 1, "incomplete": 2}[result["overall"]]
