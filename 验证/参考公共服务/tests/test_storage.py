"""7.6/8.7/11.10；OBJ-029/044；文件存储及空/错误输入边界。"""
from pathlib import Path
import tempfile
from helpers import ROOT, Service, ServiceCase


class StorageTests(ServiceCase):
    def test_T07_reject_file_reopen_replay(self):
        """8.7.3、7.6.2；OBJ-029；提交后重开可查，不覆盖事实。"""
        with tempfile.TemporaryDirectory(dir=ROOT) as directory:
            path = str(Path(directory) / "synthetic.sqlite")
            service = Service(path, admin_token=self.admin, secret=b"synthetic-secret", clock=lambda: self.now)
            self.ok(service.register_application(self.admin, self.app))
            self.ok(service.issue_grant(self.admin, self.grant))
            token = self.ok(service.issue_token(self.admin, {"object_type": "AccessGrant", "object_id": self.grant["object_id"], "version_id": "v1"}))["token"]
            receipt = self.ok(service.accept_event(token, self.event()))
            service.db.close()
            service = Service(path, admin_token=self.admin, secret=b"synthetic-secret", clock=lambda: self.now)
            try:
                self.assertEqual(service.get_receipt(token, receipt["receipt_id"]), receipt)
                self.assertEqual(len(service.query_events(token, self.instance)["events"]), 1)
                self.denied(service.accept_event(token, self.event()), service)
                self.assertTrue(service.verify(self.admin)["valid"])
            finally:
                service.db.close()

    def test_T25_reject_empty_malformed_and_rejected_receipt(self):
        """7.2.3、7.6.2；OBJ-029；空和错误输入产生可查拒收。"""
        self.assertEqual(self.s.query_events(self.token(), self.instance)["events"], [])
        for event in ({}, None, [], "not an envelope"):
            r = self.denied(self.s.accept_event(self.token(), event))
            self.assertEqual(self.s.get_receipt(self.token(), r["receipt_id"]), r)
            self.assertEqual(r["durability"], "none")
        self.denied(self.s.accept_event(None, self.event()))
        self.denied(self.s.get_receipt(self.token(), "missing"))
