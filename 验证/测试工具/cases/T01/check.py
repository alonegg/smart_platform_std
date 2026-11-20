"""5.1、5.2、表12-1；OBJ-005/006/008/009；旧活动版本引用链。"""
import copy
import json
from pathlib import Path
from conformance.checks import Checks
from conformance.context import ref


def run(ctx):
    c = Checks(ctx, "T01")
    inputs = json.loads((Path(__file__).parent / "inputs/records.json").read_text())
    # 5.1.3 c)、3.17：TaskAttempt 经 activity_ref 引用旧 LearningActivity 版本。
    records = json.loads(json.dumps(inputs).replace("https://example.edu/t01", ctx.prefix))
    valid = all(ctx.validate(v)["result"] == "passed" for v in records.values())
    c.observe("contracts", valid, "全部合成课程/开课/轮次/活动/作答 WP1=" + str(valid))
    versions = [records["version1"], records["version2"]]
    offerings = [records["offering1"], records["offering2"]]
    rounds = [records["round1"], records["round2"]]
    separate = len({v["object_id"] for v in versions}) == 2 and len({v["version_id"] for v in versions}) == 2 and len({v["object_id"] for v in offerings}) == 2 and len({v["object_id"] for v in rounds}) == 2
    c.observe("identifiers", separate, "课程版本、开课、修读轮次标识未合并=" + str(separate))
    c.observe("prior", rounds[1]["prior_round_ref"] == ref(rounds[0]), "重修 prior_round_ref 精确解析首轮=" + str(rounds[1]["prior_round_ref"] == ref(rounds[0])))
    old = records["attempt1"]["activity_ref"] == ref(records["activity1"]) and records["activity1"]["course_version_ref"] == ref(versions[0])
    alias = copy.deepcopy(records["attempt1"])
    alias["activity_ref"]["version_id"] = "latest"
    invalid = ctx.validate(alias)["result"] == "failed"
    c.observe("old-version", old and invalid, {"old_activity_course_chain": old, "latest_rejected": invalid})
    missing = copy.deepcopy(rounds[1])
    missing.pop("prior_round_ref")
    c.observe("missing-prior", ctx.validate(missing)["result"] == "failed", "缺 prior_round_ref 的重修 WP1=" + ctx.validate(missing)["result"])
    for i in (1, 2):
        event = c.event("round" + str(i))
        event["attempt_ref"] = ref(records["attempt" + str(i)])
        event["object_ref"]["object_id"] = ctx.identifier("submission" + str(i))
        c.status("send" + str(i), c.call("accept_event", event=event), "accepted")
    rows = c.events()
    c.observe("facts", len(rows) == 2 and {r["attempt_ref"]["object_id"] for r in rows} == {records["attempt1"]["object_id"], records["attempt2"]["object_id"]}, "两轮次作答事实分别可查=" + str(len(rows) == 2 and len({r["attempt_ref"]["object_id"] for r in rows}) == 2))
    return c.results
