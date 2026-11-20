"""8.6/9.2/11.5/11.10；OBJ-001/042/044；T11 及授权审计。"""
import copy
from helpers import ServiceCase, fixture, ref


class IdentityTests(ServiceCase):
    def test_T11_reject_token_boundaries(self):
        """11.5；OBJ-044；过期、受众、scope、签名、轮换及 jti。"""
        self.ok(self.s.accept_event(self.token(), self.event()))
        self.denied(self.s.accept_event(self.token(ttl=-1), self.event(source_event_id="expired")))
        self.denied(self.s.accept_event(self.token(audience="https://example.edu/wrong"), self.event()))
        self.denied(self.s.accept_event(self.token(scope=["events.read"]), self.event()))
        self.denied(self.s.issue_token(self.admin, ref(self.grant), scope=["superuser"]))
        token = self.token()
        self.ok(self.s.accept_event(token, self.event(source_event_id="replay")))
        self.denied(self.s.accept_event(token, self.event(source_event_id="replay")))
        self.denied(self.s.accept_event(token[:-1] + ("a" if token[-1] != "a" else "b"), self.event()))
        old = self.token()
        self.ok(self.s.rotate_key(self.admin, self.instance))
        self.denied(self.s.query_events(old, self.instance))
        self.ok(self.s.query_events(self.token(), self.instance))

    def test_T11_reject_pseudonym_isolation_exit(self):
        """11.5.2/11.5.3；OBJ-001/042；稳定但跨实例不可链接解析。"""
        learner = self.grant["subject_ref"]
        value = self.ok(self.s.pseudonym(self.token(), learner))["pseudonym"]
        self.assertEqual(value, self.s.pseudonym(self.token(), learner)["pseudonym"])
        self.assertEqual(self.s.resolve_pseudonym(self.token(), value)["learner_ref"], learner)
        app, g = self.second_app()
        other = self.s.pseudonym(self.token(g), learner)["pseudonym"]
        self.assertNotEqual(value, other)
        self.denied(self.s.resolve_pseudonym(self.token(g), value))
        self.denied(self.s.resolve_pseudonym(self.token(), "missing"))
        old = self.token()
        self.ok(self.s.set_application_status(self.admin, self.instance, "revoked"))
        self.denied(self.s.resolve_pseudonym(old, value))
        self.denied(self.s.issue_token(self.admin, ref(self.grant)))

    def test_T11_reject_directory_and_revocation_notifications(self):
        """8.6.6、8.7.4；OBJ-042/044、EVT-003；状态退出传播。"""
        app, g = self.second_app()
        self.ok(self.s.subscribe(self.admin, app["object_id"], ref(self.grant)))
        token = self.token()
        self.ok(self.s.revoke_grant(self.admin, ref(self.grant)))
        self.denied(self.s.query_events(token, self.instance))
        notices = self.s.notifications(self.token(g), app["object_id"])["notifications"]
        self.assertEqual(len(notices), 1)
        self.assertTrue(notices[0]["within_limit"])
        self.assertEqual(notices[0]["offering_refs"], [self.offering])
        events = self.s.query_events(self.admin, self.instance)["events"]
        self.assertEqual(events[0]["event_type"], "permission.revoked")
        self.assertEqual(events[0]["actor_type"], "system")
        old = self.token(g)
        self.ok(self.s.set_application_status(self.admin, app["object_id"], "suspended"))
        self.denied(self.s.accept_event(old, self.event()))
        self.denied(self.s.issue_token(self.admin, ref(g)))
        self.denied(self.s.register_application("bad-admin", self.app))

    def test_access_grant_issue_refuse_revoke(self):
        """8.6.4/8.6.6、9.2.4；OBJ-044；派生字段不可写。"""
        g = fixture("AccessGrant")
        g["object_id"] += "-service"
        self.ok(self.s.issue_grant(self.admin, g))
        self.ok(self.s.validate_grant(self.admin, ref(g)))
        bad = copy.deepcopy(g)
        bad["object_id"] += "-bad"
        bad["scopes"] = ["grade.confirm"]
        self.denied(self.s.issue_grant(self.admin, bad))
        for field in ("revocation_status", "revoked_at", "expired"):
            self.denied(self.s.issue_grant(self.admin, {**g, field: True}))
        self.ok(self.s.revoke_grant(self.admin, ref(g)))
        self.denied(self.s.validate_grant(self.admin, ref(g)))
        self.denied(self.s.revoke_grant(self.admin, ref(g)))
        self.denied(self.s.issue_grant(self.admin, {**g, "application_ref": {"object_type": "ApplicationInstance", "object_id": "https://example.edu/unregistered"}}))

    def test_audit_chain_tamper(self):
        """11.10；OBJ-044；正常链及被修改记录检测。"""
        self.denied(self.s.query_events("bad", self.instance))
        self.assertTrue(self.s.verify(self.admin)["valid"])
        entries = self.s.audit_log(self.admin)["entries"]
        self.assertTrue(any('"result":"rejected"' in e["body"] for e in entries))
        self.s.db.execute("UPDATE audit SET body='{}' WHERE seq=1")
        self.s.db.commit()
        self.assertFalse(self.s.verify(self.admin)["valid"])
        self.denied(self.s.audit_log(self.token()))

    def test_T11_positive_tokens_and_instance_pseudonyms(self):
        """11.5；OBJ-001/042/044；有效凭证与实例内稳定假名。"""
        self.ok(self.s.query_events(self.token(), self.instance))
        learner = self.grant["subject_ref"]
        value = self.ok(self.s.pseudonym(self.token(), learner))["pseudonym"]
        self.assertEqual(self.s.pseudonym(self.token(), learner)["pseudonym"], value)
        self.assertEqual(self.s.resolve_pseudonym(self.token(), value)["learner_ref"], learner)
