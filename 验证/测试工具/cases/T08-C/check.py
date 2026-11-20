"""7.5.2、9.2.4；OBJ-010/034、EVT-019；人员确认资格。"""
import copy
from conformance.checks import Checks
from conformance.context import ref


def run(ctx):
    c = Checks(ctx, "T08-C")
    ctx.teaching_assignment(c.grant)
    p = c.propose()
    confirmed = c.confirm(p)
    rows = c.grades()
    c.observe("trace", len(rows) == 1 and rows[0].get("confirmed_by") == {"teacher": c.grant["subject_ref"], "client_id": c.grant["client_id"]}, "confirmed_by 人员/client_id 与委托授权一致=" + str(len(rows) == 1 and rows[0].get("confirmed_by") == {"teacher": c.grant["subject_ref"], "client_id": c.grant["client_id"]}))
    p2 = c.propose("proposal2")
    candidate = c.decision("candidate", p2)
    other = copy.deepcopy(c.grant)
    other.update(object_id=ctx.identifier("unauthorized-grant"), subject_ref={"object_type": "Person", "object_id": ctx.identifier("unauthorized")})
    ctx.accepted("issue_grant", grant=other)
    candidate["decided_by"] = other["subject_ref"]
    c.status("unauthorized", ctx.target.call("confirm_grade", ctx.token(other), decision=candidate), "rejected")
    _, service = ctx.setup("client_credentials", "service")
    c.status("service", ctx.target.call("confirm_grade", ctx.token(service), decision=candidate), "rejected")
    # 5.2.7：独立人员安排，避免有效安排遮蔽过期安排。
    ctx.teaching_assignment(other, expired=True)
    c.status("expired", ctx.target.call("confirm_grade", ctx.token(other), decision=candidate), "rejected")
    c.status("proposal-archive", c.archive(p2, suffix="proposal-receipt"), "rejected")
    return c.results
