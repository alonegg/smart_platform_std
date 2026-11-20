"""7.5、9.5；OBJ-034、EVT-018；服务仅能提议。"""
import copy
from conformance.checks import Checks
from conformance.context import ref


def run(ctx):
    c = Checks(ctx, "T08-P", "client_credentials")
    method, source = ref(ctx.fixture("MethodRegistration")), ref(ctx.fixture("Resource"))
    p = c.propose(method_ref=method, source_refs=[source])
    history, formal = c.grades(False), c.grades()
    c.observe("proposal-view", not formal and len(history) == 1 and history[0].get("method_ref") == method and history[0].get("source_refs") == [source], {"formal_count": len(formal), "history_count": len(history), "references_preserved": len(history) == 1 and history[0].get("method_ref") == method and history[0].get("source_refs") == [source]})
    confirm = ctx.fixture("GradeDecision")
    confirm.update(object_id=ctx.identifier("confirm"), decision_status="confirmed", decider_type="staff", decided_by={"object_type": "Person", "object_id": ctx.identifier("teacher")}, handles_proposal_ref=ref(p))
    confirm.pop("proposer_type")
    c.status("service-confirm", c.call("confirm_grade", decision=confirm), "rejected")
    grant = copy.deepcopy(c.grant)
    grant.update(object_id=ctx.identifier("illegal-grant"), scopes=["grade.confirm"])
    c.status("confirm-grant", c.admin("issue_grant", grant=grant), "rejected")
    c.status("confirmed-proposal", c.call("propose_grade", decision=confirm, offering_ref=c.grant["scope_refs"][0]), "rejected")
    c.status("overwrite", c.call("propose_grade", decision=p, offering_ref=c.grant["scope_refs"][0]), "rejected")
    submission = ctx.fixture("Submission")
    members = [{"object_type": "Person", "object_id": ctx.identifier("member1")}, {"object_type": "Person", "object_id": ctx.identifier("member2")}]
    submission.update(object_id=ctx.identifier("group-submission"), group_ref={"object_type": "LearnerGroup", "object_id": ctx.identifier("group")}, member_refs=members)
    c.propose("member1", submission=submission, learner_ref=members[0])
    c.propose("member2", submission=submission, learner_ref=members[1])
    rows = [r for r in c.grades(False) if r.get("submission")]
    c.observe("snapshot", len(rows) == 2 and all(r["submission"]["member_refs"] == members for r in rows) and {r["learner_ref"]["object_id"] for r in rows} == {m["object_id"] for m in members}, "两位成员分别提议并保持相同成员快照=" + str(len(rows) == 2 and all(r["submission"]["member_refs"] == members for r in rows)))
    c.status("missing-member", c.call("propose_grade", decision=c.decision("no-member"), offering_ref=c.grant["scope_refs"][0], submission=submission), "rejected")
    return c.results
