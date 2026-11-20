"""9.2、8.6.6、11.5、9.8.5；OBJ-042/044、EVT-003；授权边界。"""
from conformance.checks import Checks
from conformance.context import ref


def run(ctx):
    c = Checks(ctx, "T11")
    event = c.event()
    for name, options in (("expired", {"ttl": 0}), ("audience", {"audience": "https://example.edu/wrong"}), ("scope", {"scope": ["events.read"]})):
        c.status(name, ctx.target.call("accept_event", ctx.token(c.grant, **options), event=event), "rejected")
    c.status("over-scope", c.admin("issue_token", grant_ref=ref(c.grant), scope=["superuser"]), "rejected")
    token = ctx.token(c.grant)
    c.status("first-write", ctx.target.call("accept_event", token, event=event), "accepted")
    c.status("jti", ctx.target.call("accept_event", token, event=c.event("replay")), "rejected")
    old = ctx.token(c.grant)
    c.status("rotate", c.admin("rotate_key", instance=c.app["object_id"]), "accepted")
    c.status("old-key", ctx.target.call("query_events", old, instance=c.app["object_id"]), "rejected")
    foreign = {"object_type": "Offering", "object_id": ctx.identifier("other-offering")}
    for name, changes in (("scope-refs", {"scope_refs": [foreign], "offering_id": foreign["object_id"]}), ("offering", {"offering_id": foreign["object_id"]})):
        e = c.event(name)
        e.update(changes)
        c.status(name, c.call("accept_event", event=e), "rejected")
    learner = c.grant["subject_ref"]
    value = c.call("pseudonym", learner_ref=learner)["pseudonym"]
    other_app, other_grant = ctx.setup(suffix="other")
    other_value = ctx.target.call("pseudonym", ctx.token(other_grant), learner_ref=learner)["pseudonym"]
    resolved = c.call("resolve_pseudonym", pseudonym=value)
    c.observe("pseudonyms", value != other_value and resolved.get("learner_ref") == learner, "跨实例假名不同且本实例解析正确=" + str(value != other_value and resolved.get("learner_ref") == learner))
    c.status("cross-instance", ctx.target.call("resolve_pseudonym", ctx.token(other_grant), pseudonym=value), "rejected")
    c.status("subscribe", c.admin("subscribe", instance=other_app["object_id"], grant_ref=ref(c.grant)), "accepted")
    old = ctx.token(c.grant)
    c.status("revoke", c.admin("revoke_grant", grant_ref=ref(c.grant)), "accepted")
    c.status("revoked-token", ctx.target.call("query_events", old, instance=c.app["object_id"]), "rejected")
    notices = ctx.target.call("notifications", ctx.token(other_grant), instance=other_app["object_id"])["notifications"]
    matching = [n for n in notices if n.get("grant_ref") == ref(c.grant)]
    c.observe("notification", bool(matching) and all(n.get("within_limit") is True and n.get("offering_refs") == c.grant["scope_refs"] for n in matching), {"matching_notices": len(matching), "within_limit": [n.get("within_limit") for n in matching]})
    old = ctx.token(other_grant)
    c.status("suspend", c.admin("set_application_status", instance=other_app["object_id"], status="suspended"), "accepted")
    c.status("suspended-token", c.admin("issue_token", grant_ref=ref(other_grant)), "rejected")
    c.status("suspended-write", ctx.target.call("accept_event", old, event=ctx.event(other_app, other_grant)), "rejected")
    c.status("exit", c.admin("set_application_status", instance=other_app["object_id"], status="revoked"), "accepted")
    c.status("exit-resolve", ctx.target.call("resolve_pseudonym", old, pseudonym=other_value), "rejected")
    return c.results
