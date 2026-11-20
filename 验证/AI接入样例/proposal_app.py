"""7.5、8.6、9.4、9.5；OBJ-031/034/042/044、OBJ-026、EVT-018。"""

from copy import deepcopy
from dataclasses import dataclass, field
from datetime import datetime, timezone
from http.client import HTTPConnection, HTTPSConnection
import json
from pathlib import Path
import sqlite3
import sys
from typing import Protocol
from urllib.parse import urlsplit
from uuid import uuid4

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "契约" / "tools"))
from validate import validate


VERSION = "0.1.0-candidate"
PROFILES = tuple((name, VERSION) for name in ("P-COM", "P-AI", "P-GRD"))
P_GRD_STAGES = ("T08-P",)
PURPOSE = "课内教学"
SCORE_EXTENSION = "https://example.edu/wp5/synthetic-score"
METHOD_ID = "https://example.edu/wp5/first-line-rule"


class Rejected(RuntimeError):
    pass


def check(value, target, stage="input"):
    result = validate(value, target, stage)
    if result["result"] != "passed":
        raise ValueError(f"{target} failed WP1 validation")


def accepted(response):
    if response.get("status") != "accepted":
        raise Rejected(response.get("reason", "request not accepted"))
    return response


def object_ref(obj):
    return {key: obj[key] for key in ("object_type", "object_id", "version_id") if key in obj}


class PublicService:
    def __init__(self, base_url):
        url = urlsplit(base_url)
        if url.scheme not in {"http", "https"} or not url.hostname or url.username or url.password:
            raise ValueError("a trusted HTTP(S) service origin is required")
        if url.path not in ("", "/") or url.query or url.fragment:
            raise ValueError("configure the service origin without a path or query")
        self.host, self.port = url.hostname, url.port
        self.connection = HTTPSConnection if url.scheme == "https" else HTTPConnection

    def request(self, token, path, body=None):
        conn = self.connection(self.host, self.port, timeout=5)
        try:
            headers = {"Authorization": f"Bearer {token}"}
            if body is not None:
                headers["Content-Type"] = "application/json"
                body = json.dumps(body, ensure_ascii=False, allow_nan=False).encode("utf-8")
            conn.request("GET" if body is None else "POST", path, body, headers)
            response = conn.getresponse()
            data = json.loads(response.read())
            if response.status != 200 and data.get("status") != "rejected":
                raise Rejected(f"unexpected HTTP status {response.status}")
            return data
        finally:
            conn.close()


class Audit:
    def __init__(self, db: sqlite3.Connection):
        self.db = db
        db.execute("""CREATE TABLE IF NOT EXISTS access_log (
            seq INTEGER PRIMARY KEY, at TEXT NOT NULL, task_id TEXT NOT NULL,
            grant_ref TEXT NOT NULL, target_ref TEXT NOT NULL,
            operation TEXT NOT NULL, result TEXT NOT NULL, reason TEXT NOT NULL
        )""")

    def record(self, task_id, grant_ref, target_ref, operation, result, reason=""):
        with self.db:
            self.db.execute(
                "INSERT INTO access_log(at,task_id,grant_ref,target_ref,operation,result,reason)"
                " VALUES(?,?,?,?,?,?,?)",
                (datetime.now(timezone.utc).isoformat(), task_id, json.dumps(grant_ref),
                 json.dumps(target_ref), operation, result, reason),
            )


@dataclass(frozen=True)
class Credentials:
    grant_ref: dict
    read: str = field(repr=False)
    propose: str = field(repr=False)
    event: str = field(repr=False)


@dataclass(frozen=True)
class Task:
    task_id: str
    offering_ref: dict
    enrollment_id: str
    learner_ref: dict
    submission_ref: dict
    rubric_ref: dict
    assessment_plan_ref: dict


@dataclass(frozen=True)
class Work:
    submission: dict
    text: str


@dataclass(frozen=True)
class Rubric:
    ref: dict
    expected_first_line: str
    points: int


class SyntheticContent:
    """受控合成夹具；内容源不属于 WP2 HTTP 服务。"""

    def __init__(self, service, application_ref, audit, works, rubrics):
        self.service = service
        self.application_ref = application_ref
        self.audit = audit
        self._works = tuple(works)
        self._rubrics = tuple(rubrics)

    def _read(self, task, credentials, target, operation, scope, lookup):
        reason = "grant validation failed"
        try:
            grant = accepted(self.service.request(credentials.read, "/grants/validate", {
                "grant_ref": credentials.grant_ref,
            }))["grant"]
            check(grant, "AccessGrant")
            check(target, "ObjectRef")
            reason = "outside task grant or purpose"
            if (object_ref(grant) != credentials.grant_ref
                    or grant["application_ref"] != self.application_ref
                    or grant["access_mode"] != "client_credentials"
                    or scope not in grant["scopes"] or PURPOSE not in grant["use_purposes"]
                    or any(ref not in grant["scope_refs"] for ref in (task.offering_ref, target))):
                raise Rejected(reason)
            reason = "authorized synthetic content missing"
            item = lookup()
            if item is None:
                raise Rejected(reason)
        except Exception:
            self.audit.record(task.task_id, credentials.grant_ref, target, operation, "rejected", reason)
            raise
        self.audit.record(task.task_id, credentials.grant_ref, target, operation, "accepted")
        return deepcopy(item)

    def submission(self, task, credentials):
        return self._read(task, credentials, task.submission_ref, "read_submission",
                          "submissions.read", lambda: next(
                              (work for work in self._works if object_ref(work.submission) == task.submission_ref),
                              None,
                          ))

    def rubric(self, task, credentials):
        return self._read(task, credentials, task.rubric_ref, "read_rubric", "rubrics.read",
                          lambda: next((rubric for rubric in self._rubrics if rubric.ref == task.rubric_ref), None))


@dataclass(frozen=True)
class ScoringResult:
    points: int
    tool_requests: tuple[str, ...] = ()


class Scorer(Protocol):
    @property
    def method_ref(self) -> dict: ...

    def score(self, text: str, rubric: Rubric) -> ScoringResult: ...


class FirstLineScorer:
    @property
    def method_ref(self):
        return {"object_type": "MethodRegistration", "object_id": METHOD_ID, "version_id": "v1"}

    def score(self, text, rubric):
        return ScoringResult(rubric.points if text.partition("\n")[0].strip() == rubric.expected_first_line else 0)


class ProposalApp:
    def __init__(self, service, content, scorer: Scorer, application, record_controls):
        check(application, "ApplicationInstance")
        self.service, self.content, self.scorer = service, content, scorer
        self.actor = object_ref(application)
        self.source = application["source_system"]
        self.record_controls = {key: deepcopy(record_controls[key])
                                for key in ("rights_ref", "access_policy_ref", "classification_ref")}

    def propose(self, task: Task, credentials: Credentials, *, request_text: str = ""):
        """结构化任务由可信配置提供；自由文本不是操作、权限或评分输入。"""
        if request_text:
            self.content.audit.record(task.task_id, credentials.grant_ref, task.submission_ref,
                                      "free_text", "ignored", "not part of the task contract")
        work = self.content.submission(task, credentials)
        rubric = self.content.rubric(task, credentials)
        check(work.submission, "Submission")
        method_ref = deepcopy(self.scorer.method_ref)
        check(method_ref, "IndependentRef")
        if method_ref["object_type"] != "MethodRegistration":
            raise ValueError("scorer must name a concrete MethodRegistration version")
        result = self.scorer.score(work.text, rubric)
        if result.tool_requests:
            self.content.audit.record(task.task_id, credentials.grant_ref, task.submission_ref,
                                      "model_tool", "rejected", "no model tools allowed")
            raise Rejected("no model tools allowed")
        if type(result.points) is not int or not 0 <= result.points <= rubric.points:
            raise Rejected("invalid proposed points")

        run = uuid4().hex
        at = datetime.now(timezone.utc).isoformat()
        decision = {
            **self.record_controls,
            "object_type": "GradeDecision",
            "object_id": f"{self.actor['object_id']}/proposals/{run}",
            "schema_version": VERSION,
            "source_system": self.source,
            "source_id": run,
            "created_at": at,
            "created_by": self.actor,
            "decision_status": "proposed",
            "grain": "component",
            "proposer_type": "ai_service",
            "assessment_plan_ref": task.assessment_plan_ref,
            "extensions": {SCORE_EXTENSION: {"points": result.points, "max_points": rubric.points}},
        }
        event = {
            "event_type": "grade.proposed",
            "event_type_version": VERSION,
            "schema_version": VERSION,
            "event_class": "staff_event",
            "profile_id": "P-GRD",
            "profile_version": VERSION,
            "source_system": self.source,
            "source_instance": self.actor["object_id"],
            "source_event_id": run,
            "actor_ref": self.actor,
            "actor_type": "ai_service",
            "entry_mode": "self",
            "scope_type": "offering",
            "scope_refs": [task.offering_ref],
            "offering_id": task.offering_ref["object_id"],
            "enrollment_id": task.enrollment_id,
            "subject_refs": [task.learner_ref],
            "object_ref": object_ref(decision),
            "occurred_at": at,
            "payload": {"proposer_type": "ai_service"},
        }
        check(decision, "GradeDecision")
        check(event, "event")
        response = accepted(self.service.request(credentials.propose, "/grades/proposals", {
            "decision": decision, "offering_ref": task.offering_ref,
            "submission": work.submission, "learner_ref": task.learner_ref,
            "method_ref": method_ref, "source_refs": [
                object_ref(work.submission), *work.submission["artifact_refs"], rubric.ref, task.assessment_plan_ref,
            ],
        }))
        receipt = self.service.request(credentials.event, "/events", event)
        check(receipt, "receipt")
        return response["decision"], receipt
