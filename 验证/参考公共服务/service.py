"""合成参考公共服务；7.2/7.5/7.6/8.7/9.2/10.13/11.5/11.10。

要素：OBJ-010、OBJ-029、OBJ-034、OBJ-042、OBJ-044、FLD-MTH-001..014。
完整服务子集追溯（字段结构调用 WP1，不表示所有业务关系均已解析）：
OBJ-001 OBJ-031 OBJ-040 OBJ-041
FLD-EVT-001 FLD-EVT-002 FLD-EVT-003 FLD-EVT-004 FLD-EVT-005
FLD-EVT-006 FLD-EVT-007 FLD-EVT-008 FLD-EVT-009 FLD-EVT-010
FLD-EVT-011 FLD-EVT-012 FLD-EVT-013 FLD-EVT-014 FLD-EVT-015
FLD-EVT-016 FLD-EVT-017 FLD-EVT-018 FLD-EVT-019 FLD-EVT-020
FLD-EVT-021 FLD-EVT-022 FLD-EVT-023
FLD-MTH-001 FLD-MTH-002 FLD-MTH-003 FLD-MTH-004 FLD-MTH-005
FLD-MTH-006 FLD-MTH-007 FLD-MTH-008 FLD-MTH-009 FLD-MTH-010
FLD-MTH-011 FLD-MTH-012 FLD-MTH-013 FLD-MTH-014
EVT-003 EVT-013 EVT-018 EVT-019 EVT-020 EVT-021
仅库接口；不是 OAuth 服务器、真实教务对端或符合性认证。
"""
import base64
import copy
from datetime import datetime, timezone
import functools
import hashlib
import hmac
import json
from pathlib import Path
import secrets
import sqlite3
import sys
import threading
import uuid

CONTRACT = Path(__file__).resolve().parents[1] / "契约"
sys.path.insert(0, str(CONTRACT / "tools"))
from validate import validate
from payload_hash import payload_hash


def wire(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"), allow_nan=False)


def timestamp(value):
    if not isinstance(value, str):
        raise ValueError("timestamp must be a string")
    return datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp()


def ref(obj):
    result = {"object_type": obj["object_type"], "object_id": obj["object_id"]}
    if "version_id" in obj:
        result["version_id"] = obj["version_id"]
    return result


class Denied(ValueError):
    pass


def operation(scope, write=False, admin=False):
    def decorate(fn):
        @functools.wraps(fn)
        def run(self, token, *args, **kwargs):
            claims = {}
            try:
                with self.db:
                    claims = self._auth(token, scope, write, admin)
                    result = fn(self, claims, *args, **kwargs)
                    self._audit(fn.__name__, claims, result.get("status", "accepted"), result.get("reason", ""))
                return result
            except (Denied, ValueError, KeyError, TypeError, OverflowError) as exc:
                with self.db:
                    if write and claims.get("jti"):
                        self.db.execute("INSERT OR IGNORE INTO used_jti VALUES(?)", (claims["jti"],))
                    self._audit(fn.__name__, claims, "rejected", str(exc))
                    if fn.__name__ == "accept_event":
                        return self._receipt("rejected", str(exc), claims.get("instance", ""))
                return {"status": "rejected", "reason": str(exc)}
        @functools.wraps(fn)
        def locked(self, token, *args, **kwargs):
            with self.lock:
                return run(self, token, *args, **kwargs)
        return locked
    return decorate


class Service:
    """7.6、8.7、11.10；OBJ-029/044；所有业务结果均追加审计。"""

    def __init__(self, database=":memory:", *, admin_token=None, secret=None,
                 audience="https://example.edu/api", clock=None,
                 max_revocation_delay=0, manual_scopes=("grade.confirm", "course.publish"),
                 received_stages=("school_received", "school_registered"),
                 confirmation_roles=("lead_instructor",), identifier_policy=None,
                 population_match=None, registrar_statuses=("accepted", "rejected", "quarantined"),
                 receiver_field_policy="reject", hash_serializer=None):
        if receiver_field_policy != "reject":
            raise ValueError("current WP1 input contract supports reject only")
        self.lock = threading.RLock()
        self.db = sqlite3.connect(database, check_same_thread=False)
        self.db.row_factory = sqlite3.Row
        self.admin_token = admin_token or secrets.token_urlsafe(32)
        self.secret = secret or secrets.token_bytes(32)
        self.audience = audience
        self.clock = clock or (lambda: datetime.now(timezone.utc).timestamp())
        self.max_revocation_delay = max_revocation_delay
        self.manual_scopes = set(manual_scopes)
        self.hash_serializer = hash_serializer
        self.receiver_field_policy = receiver_field_policy
        self.received_stages = list(received_stages)
        self.confirmation_roles = confirmation_roles
        self.identifier_policy = identifier_policy or (lambda s: isinstance(s, str) and 0 < len(s) <= 512)
        self.population_match = population_match or (lambda p, allowed: p in allowed)
        self.registrar_statuses = registrar_statuses
        self.db.executescript('''
            CREATE TABLE IF NOT EXISTS records(kind TEXT, id TEXT, body TEXT NOT NULL,
                PRIMARY KEY(kind,id));
            CREATE TABLE IF NOT EXISTS journal(seq INTEGER PRIMARY KEY AUTOINCREMENT,
                kind TEXT, owner TEXT, body TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS audit(seq INTEGER PRIMARY KEY AUTOINCREMENT,
                body TEXT NOT NULL, prev_hash TEXT NOT NULL, hash TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS used_jti(jti TEXT PRIMARY KEY);
        ''')

    def _now(self):
        return datetime.fromtimestamp(self.clock(), timezone.utc).isoformat().replace("+00:00", "Z")

    def _id(self):
        return "urn:uuid:" + str(uuid.uuid4())

    def _get(self, kind, key):
        if not isinstance(key, str):
            raise Denied("record identifier must be a string")
        row = self.db.execute("SELECT body FROM records WHERE kind=? AND id=?", (kind, key)).fetchone()
        if not row:
            raise Denied("not found: " + kind)
        return json.loads(row[0])

    def _put(self, kind, key, body, immutable=False):
        if immutable and self.db.execute("SELECT 1 FROM records WHERE kind=? AND id=?", (kind, key)).fetchone():
            raise Denied("immutable record already exists")
        self.db.execute("INSERT OR REPLACE INTO records VALUES(?,?,?)", (kind, key, wire(body)))

    def _all(self, kind):
        return [json.loads(r[0]) for r in self.db.execute("SELECT body FROM records WHERE kind=? ORDER BY rowid", (kind,))]

    def _append(self, kind, owner, body):
        self.db.execute("INSERT INTO journal(kind,owner,body) VALUES(?,?,?)", (kind, owner, wire(body)))

    def _journal(self, kind, owner=None):
        query = "SELECT body FROM journal WHERE kind=?"
        params = [kind]
        if owner is not None:
            query += " AND owner=?"
            params.append(owner)
        return [json.loads(r[0]) for r in self.db.execute(query + " ORDER BY seq", params)]

    def _audit(self, operation, claims, result, reason, related=None):
        row = self.db.execute("SELECT hash FROM audit ORDER BY seq DESC LIMIT 1").fetchone()
        prev = row[0] if row else "0" * 64
        body = wire({"time": self._now(), "operation": operation,
                     "subject": claims.get("sub"), "client_id": claims.get("client_id"),
                     "result": result, "reason": reason, "related": related or claims.get("grant_ref")})
        digest = hashlib.sha256((prev + body).encode()).hexdigest()
        self.db.execute("INSERT INTO audit(body,prev_hash,hash) VALUES(?,?,?)", (body, prev, digest))

    def _validate(self, obj, target, stage="input"):
        outcome = validate(obj, target, stage)
        if outcome["result"] != "passed":
            raise Denied("contract: " + wire(outcome))
        if isinstance(obj, dict):
            for key in ("object_id", "source_event_id", "source_instance"):
                if key in obj and not self.identifier_policy(obj[key]):
                    raise Denied("identifier policy denied " + key)

    def _active(self, instance):
        app = self._get("app", instance)
        if app["status"] != "active":
            raise Denied("application not active")
        return app

    def _grant(self, grant_ref):
        g = self._get("grant", wire(grant_ref))
        obj = g["object"]
        if g["revoked"] or not timestamp(obj["valid_from"]) <= self.clock() < timestamp(obj["valid_until"]):
            raise Denied("grant revoked, expired or not yet effective")
        self._active(obj["application_ref"]["object_id"])
        return obj

    def _auth(self, token, scope, write=False, admin=False):
        if not isinstance(token, str):
            raise Denied("bearer token must be a string")
        if isinstance(token, str) and hmac.compare_digest(token, self.admin_token):
            return {"client_id": "administrator", "admin": True}
        if admin:
            raise Denied("administrator required")
        try:
            body, signature = token.split(".")
            c = json.loads(base64.urlsafe_b64decode(body + "=" * (-len(body) % 4)))
            app = self._active(c["instance"])
            key = app["key"].encode()
            expected = hmac.new(key, body.encode(), hashlib.sha256).hexdigest()
            if not hmac.compare_digest(expected, signature) or c["kid"] != app["kid"]:
                raise Denied("signature or kid invalid")
            if c["exp"] <= self.clock() or c["aud"] != self.audience:
                raise Denied("expired token or wrong audience")
            g = self._grant(c["grant_ref"])
            if c["client_id"] != g["client_id"] or c["instance"] != g["application_ref"]["object_id"]:
                raise Denied("token grant binding invalid")
            if scope not in c["scope"] or not set(c["scope"]) <= set(g["scopes"]):
                raise Denied("scope denied")
            if c["access_mode"] not in (g["access_mode"], "user_session") or c.get("sub") != g.get("subject_ref"):
                raise Denied("subject or mode binding invalid")
            if write:
                if self.db.execute("SELECT 1 FROM used_jti WHERE jti=?", (c["jti"],)).fetchone():
                    raise Denied("jti replay")
                self.db.execute("INSERT INTO used_jti VALUES(?)", (c["jti"],))
            c["credential_digest"] = hashlib.sha256(token.encode()).hexdigest()
            return c
        except (ValueError, KeyError, TypeError) as e:
            raise Denied("invalid token") from e

    @operation("admin", admin=True)
    def register_application(self, c, application):
        """8.6、11.5；OBJ-042。"""
        self._validate(application, "ApplicationInstance")
        if application["source_instance"] != application["object_id"]:
            raise Denied("reference instance must match object id")
        self._put("app", application["object_id"], {"object": application, "status": "active", "kid": self._id(), "key": secrets.token_hex(32)}, True)
        return {"status": "accepted", "application": application}

    @operation("admin", admin=True)
    def set_application_status(self, c, instance, status):
        """8.6.6、11.5；OBJ-042/044。"""
        if status not in ("active", "suspended", "revoked"):
            raise Denied("unknown directory status")
        app = self._get("app", instance)
        if app["status"] == "revoked":
            raise Denied("revoked instance cannot rejoin")
        if status != "active":
            for g in self._all("grant"):
                if g["object"]["application_ref"]["object_id"] == instance and not g["revoked"]:
                    self._revoke(ref(g["object"]), "application " + status)
        app["status"] = status
        self._put("app", instance, app)
        return {"status": "accepted"}

    @operation("admin", admin=True)
    def rotate_key(self, c, instance):
        """11.5；OBJ-042；轮换立即淘汰旧 kid。"""
        app = self._active(instance)
        app.update(kid=self._id(), key=secrets.token_hex(32))
        self._put("app", instance, app)
        return {"status": "accepted", "kid": app["kid"]}

    @operation("admin", admin=True)
    def issue_grant(self, c, grant):
        """8.6.4—8.6.6、9.2.4；OBJ-044。"""
        self._validate(grant, "AccessGrant")
        app = self._active(grant["application_ref"]["object_id"])
        if app["object"]["client_id"] != grant["client_id"]:
            raise Denied("client mismatch")
        if grant["access_mode"] == "client_credentials" and self.manual_scopes.intersection(grant["scopes"]):
            raise Denied("human confirmation scope cannot be issued to service")
        self._put("grant", wire(ref(grant)), {"object": grant, "revoked": False}, True)
        return {"status": "accepted", "grant_ref": ref(grant)}

    @operation("admin", admin=True)
    def issue_token(self, c, grant_ref, *, scope=None, audience=None, ttl=300, access_mode=None):
        """9.2.4、11.5；OBJ-044；仅管理员模拟签发。"""
        self._validate(grant_ref, "ObjectRef")
        g = self._grant(grant_ref)
        scopes = g["scopes"] if scope is None else scope
        mode = access_mode or g["access_mode"]
        if not set(scopes) <= set(g["scopes"]) or mode not in (g["access_mode"], "user_session"):
            raise Denied("scope or mode escalation")
        if mode == "user_session" and g["access_mode"] != "delegated":
            raise Denied("user session needs personnel grant")
        app = self._active(g["application_ref"]["object_id"])
        claims = {"client_id": g["client_id"], "instance": g["application_ref"]["object_id"],
                  "access_mode": mode, "sub": g.get("subject_ref"), "grant_ref": grant_ref,
                  "aud": audience or g["audience"], "scope": scopes, "exp": self.clock() + ttl,
                  "jti": self._id(), "kid": app["kid"]}
        if mode == "delegated":
            claims["delegation_grant_ref"] = grant_ref
        body = base64.urlsafe_b64encode(wire(claims).encode()).decode().rstrip("=")
        sig = hmac.new(app["key"].encode(), body.encode(), hashlib.sha256).hexdigest()
        return {"status": "accepted", "token": body + "." + sig}

    @operation("grants.read")
    def validate_grant(self, c, grant_ref):
        """8.6.4；OBJ-044。"""
        self._validate(grant_ref, "ObjectRef")
        g = self._grant(grant_ref)
        self._own(c, g["application_ref"]["object_id"])
        return {"status": "accepted", "grant": g}

    def _own(self, c, instance):
        if not c.get("admin") and c.get("instance") != instance:
            raise Denied("cross-instance access")

    @operation("admin", admin=True)
    def subscribe(self, c, instance, grant_ref):
        """8.6.6；OBJ-042/044；登记撤权通知订阅。"""
        self._active(instance)
        self._validate(grant_ref, "ObjectRef")
        self._grant(grant_ref)
        self._append("subscription", wire(grant_ref), {"instance": instance})
        return {"status": "accepted"}

    @operation("admin", admin=True)
    def revoke_grant(self, c, grant_ref, basis="synthetic administrative revocation"):
        """8.6.6、8.7.4；OBJ-044、EVT-003。"""
        self._validate(grant_ref, "ObjectRef")
        return self._revoke(grant_ref, basis)

    def _revoke(self, grant_ref, basis):
        key = wire(grant_ref)
        g = self._get("grant", key)
        if g["revoked"]:
            raise Denied("already revoked")
        g.update(revoked=True, revoked_at=self._now(), basis=basis)
        self._put("grant", key, g)
        event = json.loads((CONTRACT / "fixtures/valid/event/event-permission.revoked.json").read_text())["instance"]
        instance = g["object"]["application_ref"]["object_id"]
        event.update(source_instance=instance, source_event_id=self._id(), occurred_at=self._now(),
                     object_ref=grant_ref, scope_refs=[grant_ref])
        event["payload"].update(revoked_grant_ref=grant_ref, impact_scope=g["object"]["scope_refs"], basis=basis, effective_at=self._now())
        receipt = self._ingest({"client_id": "school-system", "grant_ref": grant_ref,
                                "instance": instance, "access_mode": "client_credentials",
                                "credential_digest": hashlib.sha256(b"internal-system").hexdigest(), "system": True}, event)
        for subscriber in self._journal("subscription", key) + [{"instance": instance}]:
            self._append("notification", subscriber["instance"], {"grant_ref": grant_ref,
                         "receipt": receipt, "effective_at": self._now(), "delay_seconds": 0,
                         "within_limit": 0 <= self.max_revocation_delay,
                         "offering_refs": [r for r in g["object"]["scope_refs"] if r["object_type"] == "Offering"]})
        return {"status": "accepted", "event_receipt": receipt}

    def _receipt(self, status, reason="", owner="", original=None):
        r = {"receipt_id": self._id(), "status": status,
             "durability": "evidence_store" if status in ("accepted", "duplicate") else "none",
             "errors": [] if not reason else [{"code": status, "rule_id": "S-SERVICE", "pointer": "", "reason": reason, "hint": "修正输入或授权后重新验证"}],
             "completed_stages": self.received_stages if status in ("accepted", "duplicate") else [],
             "pending_stages": ["source_persisted"] if status in ("accepted", "duplicate") else ["source_persisted", "school_received", "school_registered"]}
        if original:
            r.update(original_receipt_id=original["receipt_id"], original_status=original["status"], current_status="accepted")
        self._validate(r, "receipt")
        self._put("receipt", r["receipt_id"], {"owner": owner, "receipt": r})
        self._append("transport", owner, r)
        return r

    @operation("events.write", write=True)
    def accept_event(self, c, event):
        """7.2.1/7.2.8/7.6/8.7；OBJ-029；T05/T06/T07/T25。"""
        return self._ingest(c, event)

    def _ingest(self, c, event):
        owner = c["instance"]
        if self.receiver_field_policy == "reject" and any(k in event for k in ("event_id", "received_at", "auth_context")):
            raise Denied("receiver-only fields supplied")
        self._validate(event, "event", "input")
        if owner != event["source_instance"]:
            raise Denied("source instance mismatch")
        definition = json.loads((CONTRACT / "events" / (event["event_type"] + ".json")).read_text())
        if not c.get("system") and not definition["ai_may_emit"] and (event["actor_type"] == "ai_service" or c["access_mode"] == "client_credentials"):
            raise Denied("event requires human or school system")
        if c.get("sub") and event["actor_type"] == "staff" and event["actor_ref"] != c["sub"]:
            raise Denied("actor does not match personnel credential")
        if not c.get("system"):
            g = self._grant(c["grant_ref"])
            allowed = {wire(r) for r in g["scope_refs"]}
            if any(wire(r) not in allowed for r in event.get("scope_refs", [])):
                raise Denied("event outside grant scope_refs")
            if event.get("offering_id") and not any(r.get("object_type") == "Offering" and r["object_id"] == event["offering_id"] for r in g["scope_refs"]):
                raise Denied("offering outside grant")
        options = {"serializer": self.hash_serializer} if self.hash_serializer else {}
        digest = payload_hash(event, definition["hash_envelope_members"], **options)
        if "payload_hash" in event and event["payload_hash"] != digest:
            raise Denied("payload hash mismatch")
        key = wire([owner, event["source_event_id"]])
        existing = self.db.execute("SELECT body FROM records WHERE kind='event' AND id=?", (key,)).fetchone()
        if existing:
            previous = json.loads(existing[0])
            if digest == previous["event"]["payload_hash"]:
                return self._receipt("duplicate", owner=owner, original=previous["receipt"])
            self._append("conflict", owner, {"original_event_id": previous["event"]["event_id"], "event": event})
            return self._receipt("conflict", "same source key with different digest; original retained", owner)
        self._grade_event(c, event, apply=False)
        stored = copy.deepcopy(event)
        auth = {k: c[k] for k in ("client_id", "grant_ref", "credential_digest", "access_mode")}
        if c.get("sub"):
            auth["on_behalf_of_ref"] = c["sub"]
        if "delegation_grant_ref" in c:
            auth["delegation_grant_ref"] = c["delegation_grant_ref"]
        stored.update(event_id=self._id(), received_at=self._now(), auth_context=auth, payload_hash=digest)
        self._validate(stored, "event", "stored")
        self._grade_event(c, event, apply=True)
        receipt = self._receipt("accepted", owner=owner)
        self._put("event", key, {"event": stored, "receipt": receipt}, True)
        self._audit("store_event", c, "accepted", "source_event_id changes are logged, not deduplicated", stored["event_id"])
        return receipt

    @operation("events.read")
    def get_receipt(self, c, receipt_id):
        """7.6.2 c；OBJ-029。"""
        r = self._get("receipt", receipt_id)
        self._own(c, r["owner"])
        return r["receipt"]

    @operation("events.read")
    def query_events(self, c, instance, order_by="occurred_at"):
        """7.2.8、7.6；OBJ-029；T06。"""
        self._own(c, instance)
        if order_by not in ("occurred_at", "received_at"):
            raise Denied("unsupported ordering")
        events = [r["event"] for r in self._all("event") if r["event"]["source_instance"] == instance]
        return {"status": "accepted", "events": sorted(events, key=lambda e: timestamp(e[order_by]))}

    @operation("events.read")
    def reconcile(self, c, instance):
        """8.8；OBJ-029；T07；事实与传输分计。"""
        self._own(c, instance)
        receipts = self._journal("transport", instance)
        return {"status": "accepted", "facts": sum(r["event"]["source_instance"] == instance for r in self._all("event")),
                "transmissions": len(receipts), **{s: sum(r["status"] == s for r in receipts) for s in ("duplicate", "conflict", "rejected")}}

    @operation("events.read")
    def conflicts(self, c, instance):
        """7.6.2；OBJ-029。"""
        self._own(c, instance)
        return {"status": "accepted", "conflicts": self._journal("conflict", instance)}

    @operation("grants.read")
    def notifications(self, c, instance):
        """8.7.4；OBJ-044。"""
        self._own(c, instance)
        return {"status": "accepted", "notifications": self._journal("notification", instance)}

    @operation("identity.read")
    def pseudonym(self, c, learner_ref):
        """11.5.2—11.5.3；OBJ-001/042；T11。"""
        self._validate(learner_ref, "ObjectRef")
        if learner_ref["object_type"] != "Person":
            raise Denied("learner must be Person")
        value = hmac.new(self.secret, wire([c["instance"], learner_ref]).encode(), hashlib.sha256).hexdigest()
        self._put("pseudonym", value, {"owner": c["instance"], "learner_ref": learner_ref})
        return {"status": "accepted", "pseudonym": value}

    @operation("identity.read")
    def resolve_pseudonym(self, c, pseudonym):
        """11.5.3；OBJ-001/042；T11。"""
        r = self._get("pseudonym", pseudonym)
        self._own(c, r["owner"])
        return {"status": "accepted", "learner_ref": r["learner_ref"]}

    @operation("admin", admin=True)
    def register_teaching_assignment(self, c, assignment):
        """5.2.7、9.2.4；OBJ-010。"""
        self._validate(assignment, "TeachingAssignment")
        self._put("teaching", assignment["object_id"], assignment, True)
        return {"status": "accepted"}

    def _teacher(self, c, offering_ref):
        if c.get("access_mode") not in ("delegated", "user_session") or not c.get("sub"):
            raise Denied("personnel credential required")
        if "grade.confirm" not in c["scope"]:
            raise Denied("confirmation scope required")
        if offering_ref not in self._grant(c["grant_ref"])["scope_refs"]:
            raise Denied("confirmation outside grant offering")
        if not any(a["person_ref"] == c["sub"] and offering_ref in a["offering_refs"] and
                   a["role"] in self.confirmation_roles and timestamp(a["starts_at"]) <= self.clock() < timestamp(a["ends_at"])
                   for a in self._all("teaching")):
            raise Denied("no current authorized teaching assignment")

    @operation("grade.propose", write=True)
    def propose_grade(self, c, decision, offering_ref, *, submission=None, learner_ref=None,
                      method_ref=None, source_refs=None, supersedes=None, basis=None):
        """7.5、9.5；OBJ-034；T08-P/R；附加关系按 S-06 保存。"""
        self._validate(decision, "GradeDecision")
        self._validate(offering_ref, "ObjectRef")
        if decision["decision_status"] != "proposed":
            raise Denied("proposal must remain proposed")
        if offering_ref not in self._grant(c["grant_ref"])["scope_refs"]:
            raise Denied("offering outside grant")
        if submission is not None:
            self._validate(submission, "Submission")
            if submission.get("group_ref") and (not learner_ref or learner_ref not in submission.get("member_refs", [])):
                raise Denied("group decision needs a member from submission snapshot")
        if learner_ref:
            self._validate(learner_ref, "ObjectRef")
            if learner_ref["object_type"] != "Person":
                raise Denied("learner must be Person")
        if method_ref:
            self._validate(method_ref, "IndependentRef")
        for source_ref in source_refs or []:
            self._validate(source_ref, "ObjectRef")
        if supersedes:
            self._validate(supersedes, "ObjectRef")
            old = self._get("grade", supersedes["object_id"])
            self._own(c, old["owner"])
            if ref(old["object"]) != supersedes or old["state"] != "archived" or not basis or old["offering_ref"] != offering_ref or old.get("learner_ref") != learner_ref:
                raise Denied("correction requires archived predecessor and basis")
        r = {"object": decision, "offering_ref": offering_ref, "owner": c["instance"],
             "state": "proposed", "supersedes": supersedes, "basis": basis, "submission": submission,
             "learner_ref": learner_ref, "method_ref": method_ref, "source_refs": source_refs or []}
        self._put("grade", decision["object_id"], r, True)
        return {"status": "accepted", "decision": r}

    @operation("grade.confirm", write=True)
    def confirm_grade(self, c, decision):
        """7.5.2、9.2.4；OBJ-034；T08-C；追加人工决定。"""
        return self._confirm(c, decision, True)

    def _confirm(self, c, decision, apply):
        self._validate(decision, "GradeDecision")
        if decision["decision_status"] != "confirmed":
            raise Denied("confirmation object required")
        proposal = self._get("grade", decision["handles_proposal_ref"]["object_id"])
        self._own(c, proposal["owner"])
        self._teacher(c, proposal["offering_ref"])
        if decision["decided_by"] != c["sub"] or proposal["state"] != "proposed":
            raise Denied("confirmer mismatch or already processed")
        r = {**proposal, "object": decision, "state": "confirmed", "confirmed_by": {"teacher": c["sub"], "client_id": c["client_id"]}}
        if apply:
            self._put("grade", decision["object_id"], r, True)
            proposal["state"] = "handled"
            self._put("grade", proposal["object"]["object_id"], proposal)
        return {"status": "accepted", "decision": r}

    @operation("admin", admin=True)
    def registrar_receipt(self, c, decision_ref, status, receipt_id):
        """7.5、8.7、E23a；OBJ-034；T08-A；仅受控模拟对端。"""
        self._validate(decision_ref, "ObjectRef")
        if status not in self.registrar_statuses:
            raise Denied("unknown registrar status")
        r = self._get("grade", decision_ref["object_id"])
        if decision_ref != ref(r["object"]) or r["state"] not in ("confirmed", "archived"):
            raise Denied("receipt must reference exact confirmed decision version")
        self._put("registrar", receipt_id, {"decision_ref": decision_ref, "status": status}, True)
        self._append("registrar", decision_ref["object_id"], {"receipt_id": receipt_id, "status": status})
        if status == "accepted":
            r["state"] = "archived"
            self._put("grade", decision_ref["object_id"], r)
        return {"status": "accepted", "registrar_status": "accepted" if r["state"] == "archived" else status}

    @operation("grades.read")
    def grade_view(self, c, instance, *, formal=True):
        """7.5.4；OBJ-034；T08-P/A/R；旧回执不覆盖更正。"""
        self._own(c, instance)
        rows = [r for r in self._all("grade") if r["owner"] == instance]
        if formal:
            rows = [r for r in rows if r["state"] in ("confirmed", "archived")]
            superseded = {r["supersedes"]["object_id"] for r in rows if r.get("supersedes")}
            rows = [r for r in rows if r["object"]["object_id"] not in superseded]
        for r in rows:
            receipts = self._journal("registrar", r["object"]["object_id"])
            r["registrar_status"] = "accepted" if r["state"] == "archived" else (receipts[-1]["status"] if receipts else "pending")
        return {"status": "accepted", "decisions": rows}

    def _grade_event(self, c, event, apply):
        kind = event["event_type"]
        if not kind.startswith("grade."):
            return
        r = self._get("grade", event["object_ref"]["object_id"])
        self._own(c, r["owner"])
        if event["object_ref"] != ref(r["object"]) or event.get("offering_id") != r["offering_ref"]["object_id"]:
            raise Denied("grade event object or offering mismatch")
        if kind == "grade.proposed" and r["state"] != "proposed":
            raise Denied("not a proposal")
        if kind == "grade.confirmed":
            self._teacher(c, r["offering_ref"])
            if r["state"] not in ("confirmed", "archived") or r["object"]["decided_by"] != c["sub"]:
                raise Denied("must reference a personnel-confirmed decision")
        if kind == "grade.archived" and (event["actor_type"] != "system" or "grade.archive" not in c.get("scope", []) or r["state"] != "archived"):
            raise Denied("archive requires school registrar acceptance")
        if kind == "grade.corrected":
            self._teacher(c, r["offering_ref"])
            if r["state"] not in ("confirmed", "archived") or not r.get("supersedes") or event["payload"]["supersedes"] != r["supersedes"]:
                raise Denied("correction predecessor mismatch")

    @operation("admin", admin=True)
    def register_method(self, c, method):
        """10.13.3；FLD-MTH-001..007；T10。"""
        self._validate(method, "MethodRegistration")
        self._put("method", wire(ref(method)), method, True)
        return {"status": "accepted"}

    @operation("admin", admin=True)
    def approve_method(self, c, approval):
        """10.13.6；FLD-MTH-008..014；T10。"""
        self._validate(approval, "MethodApproval")
        self._get("method", wire(approval["method_ref"]))
        self._put("approval", wire(ref(approval)), approval, True)
        self._append("method_history", wire(approval["method_ref"]), approval)
        return {"status": "accepted"}

    @operation("admin", admin=True)
    def set_method_status(self, c, approval_ref, status):
        """10.13.6；FLD-MTH-012；T10；保留批准历史。"""
        self._validate(approval_ref, "ObjectRef")
        r = self._get("approval", wire(approval_ref))
        if status not in ("approved", "suspended", "revoked") or r["approval_status"] == "revoked":
            raise Denied("invalid approval transition")
        r["approval_status"] = status
        self._validate(r, "MethodApproval")
        self._put("approval", wire(approval_ref), r)
        self._append("method_history", wire(r["method_ref"]), r)
        return {"status": "accepted"}

    def _method_use(self, method_ref, purpose, population, consequence, at):
        self._validate(method_ref, "ObjectRef")
        now = timestamp(at) if at else self.clock()
        for r in self._all("approval"):
            if r["method_ref"] == method_ref and r["approval_status"] == "approved" and purpose in r["use_purposes"] and self.population_match(population, r["applicability_scope"]["populations"]) and consequence == r["consequence_level"] and timestamp(r["valid_from"]) <= now < timestamp(r["valid_until"]):
                return {"status": "accepted", "allow": True, "reason": "current approval", "approval_ref": ref(r)}
        return {"status": "rejected", "allow": False, "reason": "no current approval within purpose, population, consequence and time"}

    @operation("methods.read")
    def check_method_use(self, c, method_ref, use_purpose, population, consequence_level, at=None):
        """10.13.3/10.13.6；FLD-MTH-008..014；T10。"""
        return self._method_use(method_ref, use_purpose, population, consequence_level, at)

    @operation("methods.read")
    def method_history(self, c, method_ref):
        """10.13.6；FLD-MTH-012/013。"""
        self._validate(method_ref, "ObjectRef")
        return {"status": "accepted", "history": self._journal("method_history", wire(method_ref))}

    @operation("ai.output", write=True)
    def admit_ai_output(self, c, use_purpose, *, mastery_inference=False, method_ref=None, population=None, consequence_level="formative_support"):
        """9.5、10.13；FLD-MTH-010/011；T10。"""
        g = self._grant(c["grant_ref"])
        if use_purpose not in g["use_purposes"]:
            raise Denied("purpose outside grant")
        if method_ref:
            return self._method_use(method_ref, use_purpose, population, consequence_level, None)
        if mastery_inference:
            raise Denied("mastery inference requires approved method")
        return {"status": "accepted", "allow": True, "reason": "ordinary assistance within registered purpose"}

    @operation("admin", admin=True)
    def audit_log(self, c):
        """11.10；OBJ-044；只读审计查询。"""
        return {"status": "accepted", "entries": [dict(r) for r in self.db.execute("SELECT * FROM audit ORDER BY seq")]}

    @operation("admin", admin=True)
    def verify(self, c):
        """11.10；OBJ-044；哈希链检测（非外部签名锚）。"""
        prev = "0" * 64
        for r in self.db.execute("SELECT * FROM audit ORDER BY seq"):
            digest = hashlib.sha256((prev + r["body"]).encode()).hexdigest()
            if r["prev_hash"] != prev or r["hash"] != digest:
                return {"status": "rejected", "valid": False, "reason": "audit chain tampered", "sequence": r["seq"]}
            prev = r["hash"]
        return {"status": "accepted", "valid": True}
