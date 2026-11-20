"""10.13.3/10.13.6、9.5.6；FLD-MTH-001..014；用途准入。"""
from conformance.checks import Checks
from conformance.context import ref


def run(ctx):
    c = Checks(ctx, "T10")
    method, approval = ctx.fixture("MethodRegistration"), ctx.fixture("MethodApproval")
    method["object_id"] = ctx.identifier("method")
    approval.update(object_id=ctx.identifier("approval"), method_ref=ref(method), approved_at=ctx.time(-60), valid_from=ctx.time(-60), valid_until=ctx.time(3600))
    c.status("register", c.admin("register_method", method=method), "accepted")
    args = dict(method_ref=ref(method), use_purpose="课内教学", population="合成群体", consequence_level="formative_support")
    before = c.call("check_method_use", **args)
    c.observe("unapproved", before.get("allow") is False, {"allow": before.get("allow")})
    c.status("approve", c.admin("approve_method", approval=approval), "accepted")
    allowed = c.call("check_method_use", **args)
    c.observe("allow", allowed.get("allow") is True, {"allow": allowed.get("allow")})
    for name, changes in (("purpose", {"use_purpose": "模型训练"}), ("population", {"population": "其他群体"})):
        denied = c.call("check_method_use", **{**args, **changes})
        c.observe(name, denied.get("allow") is False, {"allow": denied.get("allow")})
    c.status("suspend", c.admin("set_method_status", approval_ref=ref(approval), status="suspended"), "accepted")
    denied = c.call("check_method_use", **args)
    history = c.call("method_history", method_ref=ref(method))["history"]
    c.observe("history", denied.get("allow") is False and len(history) == 2 and [h["approval_status"] for h in history] == ["approved", "suspended"], {"allow": denied.get("allow"), "history_statuses": [h["approval_status"] for h in history]})
    ordinary = c.call("admit_ai_output", use_purpose="课内教学")
    c.observe("ordinary", ordinary.get("allow") is True, {"allow": ordinary.get("allow")})
    c.status("no-method", c.call("admit_ai_output", use_purpose="课内教学", mastery_inference=True), "rejected")
    c.status("outside-purpose", c.call("admit_ai_output", use_purpose="模型训练"), "rejected")
    return c.results
