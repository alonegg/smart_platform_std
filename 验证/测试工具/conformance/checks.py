"""7.5/7.6/9.2；OBJ-029/034/044；合成观察辅助，不将业务拒绝转成通过。"""
import json
from .context import ref


class Checks:
    def __init__(self, ctx, case_id, mode="delegated", scopes=None):
        self.ctx, self.case_id = ctx, case_id
        self.app, self.grant = ctx.setup(mode, scopes=scopes)
        self.results = []

    def call(self, method, /, **kwargs):
        return self.ctx.target.call(method, self.ctx.token(self.grant), **kwargs)

    def admin(self, method, /, **kwargs):
        return self.ctx.target.call(method, self.ctx.admin_token, **kwargs)

    def observe(self, name, ok, actual):
        self.results.append(dict(id=self.case_id + "-" + name, status="passed" if ok else "failed",
                                 actual=json.dumps(actual, ensure_ascii=False, sort_keys=True) if not isinstance(actual, str) else actual,
                                 detail="合成请求观察，不记录凭证"))

    def status(self, name, response, expected):
        self.observe(name, response.get("status") == expected, "status=" + str(response.get("status")))
        return response

    def event(self, source="event"):
        return self.ctx.event(self.app, self.grant, source)

    def events(self):
        return self.call("query_events", instance=self.app["object_id"])["events"]

    def decision(self, name, proposal=None):
        d = self.ctx.fixture("GradeDecision")
        d["object_id"] = self.ctx.identifier(name)
        if proposal:
            d.update(decision_status="confirmed", decider_type="staff", decided_by=self.grant["subject_ref"], handles_proposal_ref=ref(proposal))
            d.pop("proposer_type")
        return d

    def propose(self, name="proposal", **kwargs):
        d = self.decision(name)
        self.status(name, self.call("propose_grade", decision=d, offering_ref=self.grant["scope_refs"][0], **kwargs), "accepted")
        return d

    def confirm(self, proposal, name="confirmed"):
        d = self.decision(name, proposal)
        self.status(name, self.call("confirm_grade", decision=d), "accepted")
        return d

    def archive(self, decision, status="accepted", suffix="receipt"):
        return self.admin("registrar_receipt", decision_ref=ref(decision), status=status, receipt_id=self.ctx.identifier(suffix))

    def grades(self, formal=True):
        return self.call("grade_view", instance=self.app["object_id"], formal=formal)["decisions"]
