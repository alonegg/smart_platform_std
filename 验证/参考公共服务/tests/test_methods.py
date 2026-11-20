"""10.13.3/10.13.6、9.8.5；FLD-MTH-001..014；T10。"""
from helpers import ServiceCase, fixture, ref


class MethodTests(ServiceCase):
    def test_T10_reject_runtime_outside_approval(self):
        """10.13；FLD-MTH-008..014；用途、人群、后果与有效期逐项阻断。"""
        method = fixture("MethodRegistration")
        approval = fixture("MethodApproval")
        args = (ref(method), "课内教学", "合成群体", "formative_support")
        self.assertFalse(self.s.check_method_use(self.token(), *args)["allow"])
        self.ok(self.s.register_method(self.admin, method))
        self.ok(self.s.approve_method(self.admin, approval))
        self.assertTrue(self.s.check_method_use(self.token(), *args)["allow"])
        for changed in [(args[0], "模型训练", args[2], args[3]), (args[0], args[1], "其他群体", args[3]), (args[0], args[1], args[2], "high_stakes")]:
            self.assertFalse(self.s.check_method_use(self.token(), *changed)["allow"])
        self.assertFalse(self.s.check_method_use(self.token(), *args, at="2027-01-01T00:00:00Z")["allow"])
        self.assertFalse(self.s.check_method_use(self.token(), *args, at="2025-01-01T00:00:00Z")["allow"])
        self.ok(self.s.set_method_status(self.admin, ref(approval), "suspended"))
        self.assertFalse(self.s.check_method_use(self.token(), *args)["allow"])
        self.ok(self.s.set_method_status(self.admin, ref(approval), "approved"))
        self.assertTrue(self.s.check_method_use(self.token(), *args)["allow"])
        self.ok(self.s.set_method_status(self.admin, ref(approval), "revoked"))
        self.assertFalse(self.s.check_method_use(self.token(), *args)["allow"])
        self.assertEqual(len(self.s.method_history(self.token(), ref(method))["history"]), 4)
        self.denied(self.s.set_method_status(self.admin, ref(approval), "expired"))
        self.denied(self.s.approve_method(self.admin, {**approval, "approval_status": "expired"}))
        self.denied(self.s.register_method(self.admin, {}))

    def test_T10_reject_ai_output_without_approval(self):
        """9.5、10.13；FLD-MTH-010/011；普通帮助与掌握推断分离。"""
        self.assertTrue(self.s.admit_ai_output(self.token(), "课内教学")["allow"])
        self.denied(self.s.admit_ai_output(self.token(), "模型训练"))
        self.denied(self.s.admit_ai_output(self.token(), "课内教学", mastery_inference=True))
        method = fixture("MethodRegistration")
        approval = fixture("MethodApproval")
        self.ok(self.s.register_method(self.admin, method))
        self.ok(self.s.approve_method(self.admin, approval))
        self.assertTrue(self.s.admit_ai_output(self.token(), "课内教学", mastery_inference=True, method_ref=ref(method), population="合成群体")["allow"])
        self.ok(self.s.set_method_status(self.admin, ref(approval), "suspended"))
        self.assertFalse(self.s.admit_ai_output(self.token(), "课内教学", mastery_inference=True, method_ref=ref(method), population="合成群体")["allow"])

    def test_T10_positive_current_approval_and_history(self):
        """10.13.3/10.13.6；FLD-MTH-008/012/013；当前批准和历史可查。"""
        method = fixture("MethodRegistration")
        self.ok(self.s.register_method(self.admin, method))
        self.ok(self.s.approve_method(self.admin, fixture("MethodApproval")))
        self.assertTrue(self.s.check_method_use(self.token(), ref(method), "课内教学", "合成群体", "formative_support")["allow"])
        self.assertEqual(len(self.s.method_history(self.token(), ref(method))["history"]), 1)
        self.assertTrue(self.s.admit_ai_output(self.token(), "课内教学")["allow"])
