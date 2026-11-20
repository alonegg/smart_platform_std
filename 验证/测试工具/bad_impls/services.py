"""仅供合成反例；7.6/7.5/9.2/11.5；禁止用于真实数据或生产服务。"""
import copy
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "参考公共服务"))
from service import Service, operation, payload_hash, timestamp, wire, Denied


class DuplicateNotDeduped(Service):
    """7.6；OBJ-029、FLD-EVT-023；duplicate 回执却再次保存事实。"""

    def _ingest(self, c, event):
        receipt = super()._ingest(c, event)
        if receipt["status"] == "duplicate":
            original = self._get("event", wire([c["instance"], event["source_event_id"]]))
            extra = copy.deepcopy(original)
            extra["event"].update(event_id=self._id(), received_at=self._now())
            extra["receipt"] = receipt
            self._put("event", self._id(), extra, True)
        return receipt


class ConflictOverwrite(Service):
    """7.6.2；OBJ-029、FLD-EVT-020/023；冲突按新输入覆盖事实。"""

    def _ingest(self, c, event):
        key = wire([c["instance"], event.get("source_event_id")])
        row = self.db.execute("SELECT body FROM records WHERE kind='event' AND id=?", (key,)).fetchone()
        previous = json.loads(row[0]) if row else None
        if previous:
            self._validate(event, "event", "input")
            definition = json.loads((Path(__file__).resolve().parents[2] / "契约/events" / (event["event_type"] + ".json")).read_text())
            options = {"serializer": self.hash_serializer} if self.hash_serializer else {}
            digest = payload_hash(event, definition["hash_envelope_members"], **options)
            if digest != previous["event"]["payload_hash"]:
                self.db.execute("DELETE FROM records WHERE kind='event' AND id=?", (key,))
                try:
                    return super()._ingest(c, event)
                except Exception:
                    self._put("event", key, previous)
                    raise
        return super()._ingest(c, event)


class ServiceConfirmsGrade(Service):
    """7.5.2、9.2.4、9.5；OBJ-034/044、EVT-019；混淆服务与人员确认。"""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.manual_scopes.discard("grade.confirm")

    def _validate(self, obj, target, stage="input"):
        if target == "AccessGrant" and obj.get("access_mode") == "client_credentials" and "grade.confirm" in obj.get("scopes", []):
            obj = copy.deepcopy(obj)
            obj["scopes"] = [s for s in obj["scopes"] if s != "grade.confirm"] or ["grade.propose"]
        return super()._validate(obj, target, stage)

    def _teacher(self, c, offering_ref):
        if c.get("access_mode") == "client_credentials":
            return
        return super()._teacher(c, offering_ref)

    def _confirm(self, c, decision, apply):
        if c.get("access_mode") == "client_credentials":
            c = {**c, "sub": decision.get("decided_by")}
        return super()._confirm(c, decision, apply)


class RevocationIneffective(Service):
    """8.6.6、9.2；OBJ-044、EVT-003；忽略已撤销状态，保留其他凭证检查。"""

    def _grant(self, grant_ref):
        obj = self._get("grant", wire(grant_ref))["object"]
        if not timestamp(obj["valid_from"]) <= self.clock() < timestamp(obj["valid_until"]):
            raise Denied("grant expired or not yet effective")
        self._active(obj["application_ref"]["object_id"])
        return obj


class UnapprovedMethodAllowed(Service):
    """10.13.3、10.13.6；OBJ-040/041、FLD-MTH-012；登记冒充当前准入。"""

    def _method_use(self, method_ref, purpose, population, consequence, at):
        result = super()._method_use(method_ref, purpose, population, consequence, at)
        if not result["allow"]:
            self._get("method", wire(method_ref))
            return {"status": "accepted", "allow": True, "reason": "deliberate defect: registration treated as admission"}
        return result


class ReceiverFieldsWritable(Service):
    """5.3.3、7.2.3/4；FLD-EVT-001/021/022；客户端覆盖接收端权威字段。"""

    def _ingest(self, c, event):
        supplied = {k: copy.deepcopy(event[k]) for k in ("event_id", "received_at", "auth_context") if k in event}
        cleaned = {k: v for k, v in event.items() if k not in supplied}
        receipt = super()._ingest(c, cleaned)
        if supplied and receipt["status"] == "accepted":
            key = wire([c["instance"], event["source_event_id"]])
            stored = self._get("event", key)
            stored["event"].update(supplied)
            self._put("event", key, stored)
        return receipt


class ProposalInFormalView(Service):
    """7.5、9.5；OBJ-034、EVT-018；提议混入正式视图。"""

    @operation("grades.read")
    def grade_view(self, c, instance, *, formal=True):
        result = Service.grade_view.__wrapped__(self, c, instance, formal=formal)
        if formal:
            history = Service.grade_view.__wrapped__(self, c, instance, formal=False)
            result["decisions"].extend(r for r in history["decisions"] if r["state"] == "proposed")
        return result


class CrossInstancePseudonym(Service):
    """11.5.3；OBJ-001、OBJ-042；解析端漏查假名实例域。"""

    @operation("identity.read")
    def resolve_pseudonym(self, c, pseudonym):
        record = self._get("pseudonym", pseudonym)
        return {"status": "accepted", "learner_ref": record["learner_ref"]}
