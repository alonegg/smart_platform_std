"""10.6.5、表12-1；OBJ-037/038、FLD-COG-*；未知不是零分。"""
import copy
import json
from pathlib import Path
from conformance.checks import Checks
from conformance.context import ref


def run(ctx):
    c = Checks(ctx, "T09")
    records = json.loads((Path(__file__).parent / "inputs/states.json").read_text())
    for name in ("unknown", "insufficient_evidence"):
        record = records[name]
        c.observe(name, ctx.validate(record)["result"] == "passed", "WP1=" + ctx.validate(record)["result"])
        for variant in ("number", "missing-reason"):
            bad = copy.deepcopy(record)
            if variant == "number":
                bad["value"] = 0.7
            else:
                bad["missing_reasons"] = [r for r in bad["missing_reasons"] if r["pointer"] != "/value"]
            result = ctx.validate(bad)["result"]
            c.observe(name + "-" + variant, result == "failed", "WP1=" + result)
    reviewed, unreviewed = records["reviewed"], records["unreviewed"]
    distinct = reviewed["evidence_links"][0]["role"] == "inconclusive" and unreviewed["evidence_links"] is None and reviewed.get("review") is not None and "review" not in unreviewed
    valid = all(ctx.validate(r)["result"] == "passed" for r in (reviewed, unreviewed))
    c.observe("review", distinct and valid, {"inconclusive_distinct_from_unreviewed": distinct, "valid": valid})
    event = ctx.fixture("event", "event-cognition.updated.json")
    event.update(source_instance=c.app["object_id"], source_event_id=ctx.identifier("cognition"), scope_refs=c.grant["scope_refs"], offering_id=c.grant["scope_refs"][0]["object_id"], object_ref=ref(reviewed))
    c.status("send", c.call("accept_event", event=event), "accepted")
    rows = c.events()
    unchanged = len(rows) == 1 and all(rows[0].get(k) == v for k, v in event.items())
    c.observe("unchanged", unchanged, "认知事件引用与空载荷原样承载=" + str(unchanged))
    return c.results
