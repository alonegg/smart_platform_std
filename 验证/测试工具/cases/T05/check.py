"""7.6、7.2.8、8.7；OBJ-029、FLD-EVT-001/020；H-11/H-27。"""
import copy
import json
from pathlib import Path


def run(ctx):
    app, grant = ctx.setup()
    event = ctx.event(app, grant)
    changes = json.loads((Path(__file__).parent / "inputs/variants.json").read_text())
    receipts, observations = [], []

    def call(method, **kwargs):
        return ctx.target.call(method, ctx.token(grant), **kwargs)

    def send(value):
        result = call("accept_event", event=value)
        receipts.append(result)
        return result

    def observe(id, ok, actual):
        observations.append(dict(id=id, status="passed" if ok else "failed", actual=actual, detail="合成请求的状态、计数及内容比较；不记录凭证"))

    first, duplicate = send(event), send(event)
    observe("T05-01", first.get("status") == "accepted" and duplicate.get("status") == "duplicate" and duplicate.get("original_receipt_id") == first.get("receipt_id"), "首次=" + str(first.get("status")) + "；重送=" + str(duplicate.get("status")) + "；检查原回执引用")
    counts = call("reconcile", instance=app["object_id"])
    observe("T05-02", all(counts.get(k) == v for k, v in {"facts": 1, "transmissions": 2, "duplicate": 1}.items()), "facts/transmissions/duplicate=" + "/".join(str(counts.get(k)) for k in ("facts", "transmissions", "duplicate")))
    changed = copy.deepcopy(event)
    changed.update(changes["conflict"])
    conflict = send(changed)
    conflicts = call("conflicts", instance=app["object_id"]).get("conflicts", [])
    stored = call("query_events", instance=app["object_id"]).get("events", [])
    unchanged = len(stored) == 1 and all(stored[0].get(k) == v for k, v in event.items())
    observe("T05-03", conflict.get("status") == "conflict" and len(conflicts) == 1 and unchanged, "冲突=" + str(conflict.get("status")) + "；隔离条数=" + str(len(conflicts)) + "；原事实未覆盖=" + str(unchanged))
    repaired = copy.deepcopy(event)
    repaired["source_event_id"] = ctx.identifier("repair")
    bad = {**repaired, **changes["receiver_fields"]}
    rejected = send(bad)
    queried = call("get_receipt", receipt_id=rejected["receipt_id"])
    accepted = send(repaired)
    events = call("query_events", instance=app["object_id"]).get("events", [])
    repair_facts = [e for e in events if e["source_event_id"] == repaired["source_event_id"]]
    observe("T05-04", rejected.get("status") == "rejected" and queried == rejected and accepted.get("status") == "accepted" and len(repair_facts) == 1,
            "带 auth_context=" + str(rejected.get("status")) + "；回执可查询=" + str(queried == rejected) + "；修复=" + str(accepted.get("status")) + "；修复事实=" + str(len(repair_facts)))
    valid = all(ctx.validate(r, "receipt")["result"] == "passed" for r in receipts)
    observe("T05-05", valid and len(receipts) == 5, "5 个受理/重复/冲突/拒收/修复回执 WP1 校验=" + str(valid))
    return observations
