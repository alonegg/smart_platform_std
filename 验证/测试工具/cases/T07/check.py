"""8.7.3、8.8；OBJ-029、EVT-013/014；回执保存边界。"""
from conformance.checks import Checks


def run(ctx):
    c = Checks(ctx, "T07")
    event = c.event("lost-response")
    first = c.call("accept_event", event=event)
    c.observe("boundary", first.get("status") == "accepted" and first.get("durability") == "evidence_store" and "source_persisted" in first.get("pending_stages", []),
              {"status": first.get("status"), "durability": first.get("durability"), "pending_stages": first.get("pending_stages")})
    rejected = c.call("accept_event", event={})
    c.observe("rejection", rejected.get("status") == "rejected" and rejected.get("durability") == "none" and rejected.get("completed_stages") == [],
              {"status": rejected.get("status"), "durability": rejected.get("durability"), "completed_stages": rejected.get("completed_stages")})
    duplicate = c.call("accept_event", event=event)
    counts = c.call("reconcile", instance=c.app["object_id"])
    c.observe("lost-retry", duplicate.get("status") == "duplicate" and duplicate.get("original_receipt_id") == first.get("receipt_id") and counts.get("facts") == 1,
              {"status": duplicate.get("status"), "original_matches": duplicate.get("original_receipt_id") == first.get("receipt_id"), "facts": counts.get("facts")})
    second = c.event("second-submission")
    c.status("second", c.call("accept_event", event=second), "accepted")
    withdrawn = ctx.fixture("event", "event-submission.withdrawn.json")
    withdrawn.update({k: v for k, v in second.items() if k not in ("event_type", "payload", "source_event_id")})
    withdrawn["source_event_id"] = ctx.identifier("withdrawn")
    c.status("withdrawn", c.call("accept_event", event=withdrawn), "accepted")
    rows = c.events()
    counts = c.call("reconcile", instance=c.app["object_id"])
    c.observe("facts", len(rows) == 3 and counts.get("facts") == 3 and counts.get("transmissions") == 5 and counts.get("duplicate") == 1 and counts.get("rejected") == 1 and sorted(r["event_type"] for r in rows) == ["submission.submitted", "submission.submitted", "submission.withdrawn"],
              {k: counts.get(k) for k in ("facts", "transmissions", "duplicate", "rejected")})
    c.observe("receipts", all(ctx.validate(r, "receipt")["result"] == "passed" for r in (first, rejected, duplicate)), "受理/拒收/重送回执 WP1 校验")
    return c.results
