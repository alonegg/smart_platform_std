"""7.2/7.6/8.7/8.8；OBJ-029、EVT-013；T05/T06/T07/T25。"""
import copy
import hashlib
from helpers import ServiceCase, ref, validate


class EventTests(ServiceCase):
    def test_T05_reject_conflict_and_repair(self):
        """7.6.2；OBJ-029；同摘要重试、冲突隔离、拒收后完整重验。"""
        e = self.event()
        a = self.ok(self.s.accept_event(self.token(), e))
        d = self.s.accept_event(self.token(), e)
        self.assertEqual(d["status"], "duplicate")
        self.assertEqual(d["original_receipt_id"], a["receipt_id"])
        changed = copy.deepcopy(e)
        changed["occurred_at"] = "2026-01-01T01:00:00Z"
        self.conflicted(self.s.accept_event(self.token(), changed))
        self.assertEqual(len(self.s.conflicts(self.token(), self.instance)["conflicts"]), 1)
        self.assertEqual(self.s.query_events(self.token(), self.instance)["events"][0]["occurred_at"], e["occurred_at"])
        bad = self.event(source_event_id="repair")
        bad.pop("payload")
        self.denied(self.s.accept_event(self.token(), bad))
        bad["payload"] = {}
        self.ok(self.s.accept_event(self.token(), bad))
        self.assertEqual(len(self.s.query_events(self.token(), self.instance)["events"]), 2)

    def test_T06_positive_append_late(self):
        """7.2.8；OBJ-029；发生/接收排序独立且历史不覆盖。"""
        e = self.event(source_event_id="later", occurred_at="2026-01-01T01:00:00Z", source_sequence=2)
        self.ok(self.s.accept_event(self.token(), e))
        self.now += 30
        self.ok(self.s.accept_event(self.token(), self.event(source_event_id="earlier", source_sequence=1)))
        by_time = self.s.query_events(self.token(), self.instance)["events"]
        by_receive = self.s.query_events(self.token(), self.instance, "received_at")["events"]
        self.assertEqual([e["source_sequence"] for e in by_time], [1, 2])
        self.assertEqual([e["source_sequence"] for e in by_receive], [2, 1])
        self.assertLess(by_time[0]["occurred_at"], by_time[0]["received_at"])

    def test_T06_reject_invalid_order(self):
        """7.2.8；OBJ-029；不支持的排序明确拒绝且有审计。"""
        self.denied(self.s.query_events(self.token(), self.instance, "unregistered"))

    def test_T07_reject_receipt_scope_and_reconcile(self):
        """8.7.3、8.8；OBJ-029；各阶段与持久化、传输分计。"""
        self.assertEqual(self.s.reconcile(self.token(), self.instance)["facts"], 0)
        e = self.event()
        a = self.ok(self.s.accept_event(self.token(), e))
        self.assertEqual(a["durability"], "evidence_store")
        self.assertEqual(a["completed_stages"], ["school_received", "school_registered"])
        self.assertEqual(a["pending_stages"], ["source_persisted"])
        self.assertEqual(validate(a, "receipt", "input")["result"], "passed")
        self.s.accept_event(self.token(), e)
        self.conflicted(self.s.accept_event(self.token(), {**e, "occurred_at": "2026-01-01T02:00:00Z"}))
        self.denied(self.s.accept_event(self.token(), {}))
        counts = self.s.reconcile(self.token(), self.instance)
        self.assertEqual({k: counts[k] for k in ("facts", "transmissions", "duplicate", "conflict", "rejected")}, {"facts": 1, "transmissions": 4, "duplicate": 1, "conflict": 1, "rejected": 1})
        self.assertEqual(self.s.get_receipt(self.token(), a["receipt_id"]), a)
        app, g = self.second_app()
        self.denied(self.s.get_receipt(self.token(g), a["receipt_id"]))
        self.denied(self.s.reconcile(self.token(g), self.instance))

    def test_T25_reject_receiver_fields_and_trace(self):
        """5.3.3、7.2.3、11.10；OBJ-029/044；凭证摘要可追溯。"""
        e = self.event()
        for field in ("event_id", "received_at", "auth_context"):
            self.denied(self.s.accept_event(self.token(), {**e, field: "forged"}))
        self.denied(self.s.accept_event(self.token(), {**e, "payload_hash": "0" * 64}))
        token = self.token()
        self.ok(self.s.accept_event(token, e))
        stored = self.s.query_events(self.token(), self.instance)["events"][0]
        self.assertEqual(validate(stored, "event", "stored")["result"], "passed")
        auth = stored["auth_context"]
        self.assertEqual(auth["credential_digest"], hashlib.sha256(token.encode()).hexdigest())
        self.assertEqual(auth["grant_ref"], ref(self.grant))
        self.assertEqual(auth["on_behalf_of_ref"], self.grant["subject_ref"])
        self.ok(self.s.validate_grant(self.token(), auth["grant_ref"]))
        self.denied(self.s.accept_event(self.token(), {**e, "source_instance": "https://example.edu/other"}))

    def test_T05_positive_same_digest_duplicate(self):
        """7.6.2；OBJ-029；同事实只登记一次，关联原回执。"""
        event = self.event()
        first = self.ok(self.s.accept_event(self.token(), event))
        duplicate = self.s.accept_event(self.token(), event)
        self.assertEqual(duplicate["status"], "duplicate")
        self.assertEqual(duplicate["original_receipt_id"], first["receipt_id"])
        self.assertEqual(self.s.reconcile(self.token(), self.instance)["facts"], 1)

    def test_T07_positive_receipt_stages_and_empty_reconcile(self):
        """8.7、8.8；OBJ-029；空集合和证据库阶段如实报告。"""
        self.assertEqual(self.s.reconcile(self.token(), self.instance)["transmissions"], 0)
        receipt = self.ok(self.s.accept_event(self.token(), self.event()))
        self.assertEqual(self.s.get_receipt(self.token(), receipt["receipt_id"]), receipt)
        self.assertEqual(receipt["completed_stages"], ["school_received", "school_registered"])
        self.assertEqual(receipt["pending_stages"], ["source_persisted"])
        self.assertEqual(receipt["durability"], "evidence_store")

    def test_T25_positive_stored_credential_trace(self):
        """5.3.3、7.2.3；OBJ-029/044；授权和凭证摘要可追溯。"""
        token = self.token()
        self.ok(self.s.accept_event(token, self.event()))
        event = self.s.query_events(self.token(), self.instance)["events"][0]
        self.assertEqual(validate(event, "event", "stored")["result"], "passed")
        self.assertEqual(event["auth_context"]["credential_digest"], hashlib.sha256(token.encode()).hexdigest())
        self.ok(self.s.validate_grant(self.token(), event["auth_context"]["grant_ref"]))
