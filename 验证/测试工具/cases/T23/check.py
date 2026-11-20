"""9.5、表12-1；OBJ-034/044；最坏情况服从注入的合成代理。"""
import json
from pathlib import Path
from conformance.checks import Checks
from conformance.context import ref


def run(ctx):
    c = Checks(ctx, "T23", "client_credentials", scopes=["grade.propose", "events.write", "ai.output"])
    attacks = json.loads((Path(__file__).parent / "inputs/attacks.json").read_text())
    proposal = c.decision("proposal")
    confirm = {**proposal, "object_id": ctx.identifier("confirmation"), "decision_status": "confirmed", "decider_type": "staff", "decided_by": {"object_type": "Person", "object_id": ctx.identifier("teacher")}, "handles_proposal_ref": ref(proposal)}
    confirm.pop("proposer_type")
    approval = ctx.fixture("MethodApproval")
    calls = [
        ("confirm_grade", {"decision": confirm}),
        ("accept_event", {"kind": "grade.confirmed"}),
        ("accept_event", {"kind": "grade.archived"}),
        ("issue_grant", {"grant": c.grant}),
        ("issue_token", {"grant_ref": ref(c.grant)}),
        ("register_application", {"application": c.app}),
        ("revoke_grant", {"grant_ref": ref(c.grant)}),
        ("set_method_status", {"approval_ref": ref(approval), "status": "approved"}),
        ("registrar_receipt", {"decision_ref": ref(confirm), "status": "accepted", "receipt_id": ctx.identifier("forged-receipt")}),
        ("audit_log", {}),
    ]
    for attack in attacks:
        for index, (method, kwargs) in enumerate(calls):
            arguments = dict(kwargs)
            if method == "accept_event":
                kind = arguments.pop("kind")
                e = ctx.fixture("event", "event-" + kind + ".json")
                e.update(source_instance=c.app["object_id"], source_event_id=ctx.identifier(attack["id"] + "/" + str(index)), scope_refs=c.grant["scope_refs"], offering_id=c.grant["scope_refs"][0]["object_id"], object_ref=ref(confirm))
                arguments["event"] = e
            # 9.5：脚本故意完全服从输入指令，安全边界必须由服务强制。
            before = c.admin("audit_log")["entries"]
            response = c.call(method, **arguments)
            entries = c.admin("audit_log")["entries"]
            previous = max((r["seq"] for r in before), default=0)
            audit = [json.loads(r["body"]) for r in entries if r["seq"] > previous]
            rejected = any(r.get("operation") == method and r.get("result") == "rejected" for r in audit)
            c.observe(attack["id"] + "-" + str(index), response.get("status") == "rejected" and rejected,
                      {"call": method, "status": response.get("status"), "rejected_audit_present": rejected})
    c.status("proposal", c.call("propose_grade", decision=proposal, offering_ref=c.grant["scope_refs"][0]), "accepted")
    formal = c.admin("grade_view", instance=c.app["object_id"])["decisions"]
    history = c.admin("grade_view", instance=c.app["object_id"], formal=False)["decisions"]
    c.observe("formal", formal == [] and len(history) == 1 and history[0]["state"] == "proposed", {"formal_count": len(formal), "history_count": len(history), "only_proposed": len(history) == 1 and history[0]["state"] == "proposed"})
    return c.results
