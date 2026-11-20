"""9.2、5.2.7；OBJ-010/042/044；真实时钟与用例独立合成标识。"""
import json
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from . import CONTRACT, validate


def ref(obj):
    return {k: obj[k] for k in ("object_type", "object_id", "version_id") if k in obj}


class Context:
    validate = staticmethod(validate)

    def __init__(self, target, case_id):
        self.target = target
        self.admin_token = target.admin_token
        self.prefix = "https://example.edu/" + case_id.lower() + "/" + uuid4().hex

    def identifier(self, name):
        return self.prefix + "/" + name

    @staticmethod
    def fixture(name, filename=None):
        path = CONTRACT / "fixtures/valid" / name / (filename or name + "-minimal.json")
        return json.loads(path.read_text())["instance"]

    @staticmethod
    def time(offset=0):
        return (datetime.now(timezone.utc) + timedelta(seconds=offset)).isoformat().replace("+00:00", "Z")

    def accepted(self, method, token=None, /, **kwargs):
        result = self.target.call(method, token or self.admin_token, **kwargs)
        if result.get("status") != "accepted":
            raise ValueError("setup operation rejected: " + method)
        return result

    def setup(self, mode="delegated", suffix="main", scopes=None):
        app = self.fixture("ApplicationInstance")
        app.update(object_id=self.identifier(suffix + "/app"), source_instance=self.identifier(suffix + "/app"), client_id=self.identifier(suffix + "/client"))
        self.accepted("register_application", application=app)
        grant = self.fixture("AccessGrant")
        grant.update(object_id=self.identifier(suffix + "/grant"), application_ref=ref(app), client_id=app["client_id"], access_mode=mode,
                     scopes=["events.write", "events.read", "grants.read", "grade.propose", "grades.read", "identity.read", "methods.read", "ai.output"] + ([] if mode == "client_credentials" else ["grade.confirm"]),
                     valid_from=self.time(-60), valid_until=self.time(3600),
                     scope_refs=[{"object_type": "Offering", "object_id": self.identifier(suffix + "/offering")}])
        if mode == "delegated":
            grant["subject_ref"] = {"object_type": "Person", "object_id": self.identifier(suffix + "/teacher")}
        if scopes is not None:
            grant["scopes"] = list(scopes)
        self.accepted("issue_grant", grant=grant)
        return app, grant

    def token(self, grant, **kwargs):
        return self.accepted("issue_token", grant_ref=ref(grant), **kwargs)["token"]

    def teaching_assignment(self, grant, expired=False):
        assignment = self.fixture("TeachingAssignment")
        assignment.update(object_id=self.identifier("assignment/" + uuid4().hex), person_ref=grant["subject_ref"], offering_refs=grant["scope_refs"], starts_at=self.time(-3600), ends_at=self.time(-60 if expired else 3600))
        self.accepted("register_teaching_assignment", assignment=assignment)
        return assignment

    def event(self, app, grant, source="event"):
        event = self.fixture("event", "event-submission.submitted.json")
        event.update(source_instance=app["object_id"], source_event_id=self.identifier(source), scope_refs=grant["scope_refs"], offering_id=grant["scope_refs"][0]["object_id"], occurred_at=self.time(-30), source_recorded_at=self.time(-20))
        return event
