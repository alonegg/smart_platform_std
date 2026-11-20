"""7.5.5；OBJ-034、EVT-021；更正追加不覆盖。"""
from conformance.checks import Checks
from conformance.context import ref


def run(ctx):
    c = Checks(ctx, "T08-R")
    ctx.teaching_assignment(c.grant)
    original = c.confirm(c.propose())
    c.status("unarchived", c.call("propose_grade", decision=c.decision("unarchived"), offering_ref=c.grant["scope_refs"][0], supersedes=ref(original), basis="synthetic correction"), "rejected")
    c.status("archive", c.archive(original), "accepted")
    c.status("no-basis", c.call("propose_grade", decision=c.decision("no-basis"), offering_ref=c.grant["scope_refs"][0], supersedes=ref(original)), "rejected")
    corrected = c.confirm(c.propose("correction", supersedes=ref(original), basis="synthetic correction"), "corrected")
    formal, history = c.grades(), c.grades(False)
    c.observe("history", len(formal) == 1 and formal[0]["object"] == corrected and len(history) == 4 and any(r["object"] == original for r in history), {"formal": len(formal), "history": len(history), "original_preserved": any(r["object"] == original for r in history)})
    c.status("overwrite", c.call("propose_grade", decision=original, offering_ref=c.grant["scope_refs"][0]), "rejected")
    return c.results
