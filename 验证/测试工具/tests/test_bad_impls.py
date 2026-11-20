import copy
import json
import subprocess
import sys
from threading import Thread

import pytest

from bad_impls import REGISTRY
from bad_impls.serve import make_server
from conformance import ROOT
from conformance.context import Context, ref
from conformance.runner import run
from conformance.targets import HTTP, open_target

PROFILES = ["P-COM", "P-SUB", "P-GRD", "P-AI", "P-DIA"]
CASES = ["T01", "T05", "T06", "T07", "T08-P", "T08-C", "T08-A", "T08-R", "T09", "T10", "T11", "T23", "T25"]
EXPECTED = {
    "dup-not-deduped": ("T05", "T05-02"),
    "conflict-overwrite": ("T05", "T05-03"),
    "service-confirms-grade": ("T08-P", "T08-P-confirm-grant"),
    "revocation-ineffective": ("T11", "T11-revoked-token"),
    "unapproved-method-allowed": ("T10", "T10-unapproved"),
    "receiver-fields-writable": ("T25", "T25-auth_context"),
    "proposal-in-formal-view": ("T08-P", "T08-P-proposal-view"),
    "cross-instance-pseudonym": ("T11", "T11-cross-instance"),
}


def execute(target, name):
    return run(target, name, "public-service", PROFILES, cases=CASES)


def assert_normal_failure(result, name):
    assert result["overall"] == "failed"
    case_id, observation_id = EXPECTED[name]
    row = next(c for c in result["cases"] if c["case_id"] == case_id)
    observation = next(o for o in row["observations"] if o["id"] == observation_id)
    assert row["status"] == "failed", row
    assert observation["status"] == "failed", observation
    assert observation["actual"] and "执行异常" not in observation["actual"]
    assert observation["detail"] != "未记录响应或凭证"
    for case in result["cases"]:
        if case["case_id"] in CASES:
            assert "被测异常或无法解析" not in case["reason"], case
            assert all("执行异常" not in o["actual"] for o in case["observations"]), case
    assert result["summary"]["cases"]["passed"] > 0


@pytest.mark.parametrize("name", sorted(EXPECTED))
def test_bad_implementations(name):
    assert set(REGISTRY) == set(EXPECTED)
    target = open_target("inproc:bad:" + name)
    try:
        result = execute(target, name)
        assert_normal_failure(result, name)
        assert target.admin_token not in json.dumps(result)
        assert len([c for c in result["cases"] if c["case_id"] in CASES]) == 13
    finally:
        target.close()


def test_reference_all_first_batch():
    target = open_target("inproc:reference")
    try:
        result = execute(target, "inproc:reference")
        rows = [c for c in result["cases"] if c["case_id"] in CASES]
        assert len(rows) == 13 and all(c["status"] == "passed" for c in rows), rows
        assert result["summary"]["cases"]["failed"] == 0
    finally:
        target.close()


def test_http_bad_implementation():
    name = "conflict-overwrite"
    server = make_server(name, port=0)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        target = HTTP(f"http://127.0.0.1:{server.server_port}", server.service.admin_token)
        assert_normal_failure(execute(target, name), name)
    finally:
        server.shutdown()
        server.server_close()
        thread.join()
        server.service.db.close()


def test_service_credential_actually_confirms():
    target = open_target("inproc:bad:service-confirms-grade")
    try:
        ctx = Context(target, "service-boundary")
        app, grant = ctx.setup("client_credentials")
        grant = copy.deepcopy(grant)
        grant.update(object_id=ctx.identifier("confirm-grant"), scopes=["grade.propose", "grade.confirm", "grades.read"])
        assert target.call("issue_grant", target.admin_token, grant=grant)["status"] == "accepted"
        proposal = ctx.fixture("GradeDecision")
        proposal["object_id"] = ctx.identifier("proposal")
        assert target.call("propose_grade", ctx.token(grant), decision=proposal, offering_ref=grant["scope_refs"][0])["status"] == "accepted"
        confirmation = ctx.fixture("GradeDecision")
        confirmation.update(object_id=ctx.identifier("confirmed"), decision_status="confirmed", decider_type="staff", decided_by={"object_type": "Person", "object_id": ctx.identifier("forged-teacher")}, handles_proposal_ref=ref(proposal))
        confirmation.pop("proposer_type")
        result = target.call("confirm_grade", ctx.token(grant), decision=confirmation)
        assert result["status"] == "accepted", result
        assert result["decision"]["state"] == "confirmed"
    finally:
        target.close()


def test_receiver_fields_actually_persisted():
    target = open_target("inproc:bad:receiver-fields-writable")
    try:
        ctx = Context(target, "receiver-fields")
        app, grant = ctx.setup()
        event = ctx.event(app, grant)
        supplied = dict(event_id=ctx.identifier("forged"), received_at=ctx.time(-3600), auth_context={"client_id": "forged"})
        event.update(supplied)
        assert target.call("accept_event", ctx.token(grant), event=event)["status"] == "accepted"
        rows = target.call("query_events", ctx.token(grant), instance=app["object_id"])["events"]
        assert len(rows) == 1 and all(rows[0][k] == v for k, v in supplied.items())
    finally:
        target.close()


def test_bad_http_cli_help():
    result = subprocess.run([sys.executable, str(ROOT / "bad_impls/serve.py"), "--help"], text=True, capture_output=True)
    assert result.returncode == 0, result.stderr
    assert all(name in result.stdout for name in EXPECTED)
