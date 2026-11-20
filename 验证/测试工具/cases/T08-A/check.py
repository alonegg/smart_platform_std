"""7.5.4、8.7；OBJ-034、EVT-020；精确教务回执。"""
from conformance.checks import Checks
from conformance.context import ref


def run(ctx):
    c = Checks(ctx, "T08-A")
    ctx.teaching_assignment(c.grant)
    original = c.confirm(c.propose())
    for status in ("rejected", "quarantined"):
        response = c.archive(original, status, status)
        rows = c.grades()
        c.observe(status, response.get("status") == "accepted" and len(rows) == 1 and rows[0]["state"] == "confirmed" and rows[0]["registrar_status"] == status,
                  {"call_status": response.get("status"), "state": rows[0]["state"] if rows else None, "registrar_status": rows[0]["registrar_status"] if rows else None})
    c.status("version", c.admin("registrar_receipt", decision_ref={**ref(original), "version_id": "wrong"}, status="accepted", receipt_id=ctx.identifier("wrong-version")), "rejected")
    c.status("archive", c.archive(original), "accepted")
    rows = c.grades()
    c.observe("archived", len(rows) == 1 and rows[0]["state"] == "archived", "state=" + str(rows[0]["state"] if rows else None))
    corrected = c.confirm(c.propose("correction", supersedes=ref(original), basis="synthetic rubric correction"), "corrected")
    c.status("old-replay", c.archive(original, suffix="old-replay"), "accepted")
    rows = c.grades()
    c.observe("new-unadvanced", len(rows) == 1 and rows[0]["object"] == corrected and rows[0]["state"] == "confirmed", "旧决定回执不推进新更正=" + str(len(rows) == 1 and rows[0]["object"] == corrected and rows[0]["state"] == "confirmed"))
    return c.results
