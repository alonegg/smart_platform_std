"""合成 fixture helpers；7.2/7.5/9.2；OBJ-029/034/042/044。"""
import copy
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from service import Service, ref, timestamp, validate


def fixture(name, filename=None):
    path = ROOT.parent / "契约/fixtures/valid" / name / (filename or f"{name}-minimal.json")
    return json.loads(path.read_text())["instance"]


class ServiceCase(unittest.TestCase):
    """9.2、11.5；OBJ-042/044；每个写操作签发新的合成凭证。"""

    def setUp(self):
        self.now = timestamp("2026-01-01T12:00:00Z")
        self.s = Service(admin_token="synthetic-admin", secret=b"synthetic-secret", clock=lambda: self.now)
        self.addCleanup(self.s.db.close)
        self.admin = self.s.admin_token
        self.app = fixture("ApplicationInstance")
        self.ok(self.s.register_application(self.admin, self.app))
        self.instance = self.app["object_id"]
        self.grant = fixture("AccessGrant")
        self.grant.update(access_mode="delegated", subject_ref={"object_type": "Person", "object_id": "https://example.edu/person/1"})
        self.grant["scopes"] = ["events.write", "events.read", "grants.read", "identity.read", "grade.propose", "grade.confirm", "grades.read", "methods.read", "ai.output"]
        self.ok(self.s.issue_grant(self.admin, self.grant))
        self.offering = self.grant["scope_refs"][0]
        self.teacher = fixture("TeachingAssignment")
        self.ok(self.s.register_teaching_assignment(self.admin, self.teacher))

    def ok(self, result):
        self.assertEqual(result.get("status"), "accepted", result)
        return result

    def denied(self, result, service=None):
        self.assertEqual(result.get("status"), "rejected", result)
        self.assert_rejection_recorded(result, service)
        return result

    def conflicted(self, result):
        self.assertEqual(result.get("status"), "conflict", result)
        self.assert_rejection_recorded(result)
        return result

    def assert_rejection_recorded(self, result, service=None):
        service = service or self.s
        entries = service.audit_log(self.admin)["entries"]
        self.assertEqual(json.loads(entries[-1]["body"])["result"], result["status"])
        if "receipt_id" in result:
            self.assertEqual(service.get_receipt(self.admin, result["receipt_id"]), result)
            self.assertEqual(validate(result, "receipt", "input")["result"], "passed")

    def token(self, grant=None, **kwargs):
        return self.ok(self.s.issue_token(self.admin, ref(grant or self.grant), **kwargs))["token"]

    def event(self, kind="submission.submitted", **changes):
        e = fixture("event", f"event-{kind}.json")
        e["source_instance"] = self.instance
        e.update(changes)
        return e

    def second_app(self):
        app = copy.deepcopy(self.app)
        app.update(object_id="https://example.edu/applicationinstance/2", source_instance="https://example.edu/applicationinstance/2", client_id="https://example.edu/client/2")
        self.ok(self.s.register_application(self.admin, app))
        g = copy.deepcopy(self.grant)
        g.update(object_id="https://example.edu/accessgrant/2", application_ref=ref(app), client_id=app["client_id"])
        self.ok(self.s.issue_grant(self.admin, g))
        return app, g

    def proposal(self, suffix="p", **kwargs):
        p = fixture("GradeDecision")
        p["object_id"] = "https://example.edu/gradedecision/" + suffix
        self.ok(self.s.propose_grade(self.token(), p, self.offering, **kwargs))
        return p

    def confirmation(self, proposal, suffix="c", mode=None):
        c = fixture("GradeDecision")
        c.update(object_id="https://example.edu/gradedecision/" + suffix,
                 decision_status="confirmed", decider_type="staff", decided_by=self.grant["subject_ref"], handles_proposal_ref=ref(proposal))
        c.pop("proposer_type")
        self.ok(self.s.confirm_grade(self.token(access_mode=mode), c))
        return c
