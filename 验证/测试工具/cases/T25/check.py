"""7.2.3、7.2.4、5.3.3；FLD-EVT-001/021/022；接收端字段权威性。"""
import hashlib
from conformance.checks import Checks
from conformance.context import ref


def run(ctx):
    c = Checks(ctx, "T25")
    for field, value in (("auth_context", {}), ("event_id", ctx.identifier("forged")), ("received_at", ctx.time(-60))):
        event = c.event(field)
        event[field] = value
        receipt = c.call("accept_event", event=event)
        queried = c.call("get_receipt", receipt_id=receipt["receipt_id"])
        c.observe(field, receipt.get("status") == "rejected" and queried == receipt and ctx.validate(receipt, "receipt")["result"] == "passed", {"status": receipt.get("status"), "query_matches": queried == receipt, "valid_receipt": ctx.validate(receipt, "receipt")["result"]})
    token = ctx.token(c.grant)
    c.status("accepted", ctx.target.call("accept_event", token, event=c.event("valid")), "accepted")
    rows = c.events()
    expected = dict(client_id=c.grant["client_id"], grant_ref=ref(c.grant), access_mode="delegated", credential_digest=hashlib.sha256(token.encode()).hexdigest(), on_behalf_of_ref=c.grant["subject_ref"])
    matches = len(rows) == 1 and all(rows[0].get("auth_context", {}).get(k) == v for k, v in expected.items())
    c.observe("auth", matches, "持久化身份必需字段与写入凭证一致=" + str(matches))
    valid = len(rows) == 1 and ctx.validate(rows[0], "event", "stored")["result"] == "passed"
    c.observe("stored", valid, "stored WP1=" + str(valid))
    return c.results
