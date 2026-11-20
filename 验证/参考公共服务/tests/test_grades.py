"""7.5、9.2.4、9.5；OBJ-034、EVT-018..021；T08-P/C/A/R。"""
import copy
from helpers import ServiceCase, fixture, ref


class GradeTests(ServiceCase):
    def test_T08_P_reject_mutation_and_missing_object(self):
        """7.5.2、9.5；OBJ-034；AI 提议可保存但不得正式确认。"""
        p = self.proposal()
        self.assertEqual(self.s.grade_view(self.token(), self.instance)["decisions"], [])
        self.assertEqual(len(self.s.grade_view(self.token(), self.instance, formal=False)["decisions"]), 1)
        self.denied(self.s.propose_grade(self.token(), p, self.offering))
        self.denied(self.s.propose_grade(self.token(), {**p, "decision_status": "confirmed"}, self.offering))
        self.denied(self.s.propose_grade(self.token(), {}, self.offering))
        event = self.event("grade.proposed", object_ref=ref(p))
        self.ok(self.s.accept_event(self.token(), event))
        bad = self.event("grade.proposed", source_event_id="bad", object_ref={"object_type": "GradeDecision", "object_id": "https://example.edu/missing"})
        self.denied(self.s.accept_event(self.token(), bad))

    def test_T08_C_reject_teacher_and_service_boundaries(self):
        """7.5.2、9.2.4；OBJ-010/034；人员、scope、授课有效性。"""
        p = self.proposal()
        c = self.confirmation(p, mode="user_session")
        row = self.s.grade_view(self.token(), self.instance)["decisions"][0]
        self.assertEqual(row["confirmed_by"]["teacher"], self.grant["subject_ref"])
        self.assertEqual(row["confirmed_by"]["client_id"], self.grant["client_id"])
        self.denied(self.s.confirm_grade(self.token(), c))
        p2 = self.proposal("p2")
        candidate = copy.deepcopy(c)
        candidate.update(object_id="https://example.edu/gradedecision/c2", handles_proposal_ref=ref(p2))
        self.denied(self.s.confirm_grade(self.token(scope=["grade.propose"]), candidate))
        g = copy.deepcopy(self.grant)
        g.update(object_id="https://example.edu/accessgrant/other-teacher", subject_ref={"object_type": "Person", "object_id": "https://example.edu/person/unauthorized"})
        self.ok(self.s.issue_grant(self.admin, g))
        candidate["decided_by"] = g["subject_ref"]
        self.denied(self.s.confirm_grade(self.token(g), candidate))
        service = fixture("AccessGrant")
        service.update(object_id="https://example.edu/accessgrant/service", scopes=["events.write", "grade.propose"])
        self.ok(self.s.issue_grant(self.admin, service))
        self.denied(self.s.confirm_grade(self.token(service), candidate))
        self.denied(self.s.accept_event(self.token(service), self.event("grade.confirmed", object_ref=ref(c))))
        self.ok(self.s.accept_event(self.token(), self.event("grade.confirmed", object_ref=ref(c))))
        self.s.db.execute("DELETE FROM records WHERE kind='teaching'")
        expired = copy.deepcopy(self.teacher)
        expired["ends_at"] = "2026-01-01T11:00:00Z"
        self.ok(self.s.register_teaching_assignment(self.admin, expired))
        candidate["decided_by"] = self.grant["subject_ref"]
        self.denied(self.s.confirm_grade(self.token(), candidate))

    def test_T08_A_reject_unconfirmed_or_wrong_receipt(self):
        """7.5.4、8.7；OBJ-034；拒收/隔离不归档，精确接受才完成。"""
        p = self.proposal()
        self.denied(self.s.registrar_receipt(self.admin, ref(p), "accepted", "unconfirmed"))
        c = self.confirmation(p)
        for status in ("rejected", "quarantined"):
            self.ok(self.s.registrar_receipt(self.admin, ref(c), status, "https://example.edu/receipt/" + status))
            self.assertEqual(self.s.grade_view(self.token(), self.instance)["decisions"][0]["state"], "confirmed")
        self.denied(self.s.registrar_receipt(self.admin, {**ref(c), "version_id": "wrong"}, "accepted", "wrong-version"))
        self.ok(self.s.registrar_receipt(self.admin, ref(c), "accepted", "accepted-1"))
        self.assertEqual(self.s.grade_view(self.token(), self.instance)["decisions"][0]["state"], "archived")
        self.denied(self.s.registrar_receipt(self.token(), ref(c), "accepted", "not-registrar"))

    def test_T08_R_reject_overwrite_and_old_receipt_replay(self):
        """7.5.5；OBJ-034；更正保留原决定，不被旧回执推进/回退。"""
        p = self.proposal()
        c = self.confirmation(p)
        self.denied(self.s.propose_grade(self.token(), {**p, "object_id": p["object_id"] + "bad"}, self.offering, supersedes=ref(c), basis="synthetic correction"))
        self.ok(self.s.registrar_receipt(self.admin, ref(c), "accepted", "r1"))
        corrected = self.proposal("new-p", supersedes=ref(c), basis="synthetic corrected rubric v2")
        c2 = self.confirmation(corrected, "new-c")
        self.ok(self.s.registrar_receipt(self.admin, ref(c), "accepted", "late-old"))
        view = self.s.grade_view(self.token(), self.instance)["decisions"]
        self.assertEqual([r["object"]["object_id"] for r in view], [c2["object_id"]])
        self.assertEqual(view[0]["state"], "confirmed")
        self.ok(self.s.registrar_receipt(self.admin, ref(c2), "accepted", "new-accepted"))
        self.denied(self.s.registrar_receipt(self.admin, ref(c), "accepted", "r1"))
        self.assertEqual(len(self.s.grade_view(self.token(), self.instance, formal=False)["decisions"]), 4)
        self.denied(self.s.propose_grade(self.token(), c, self.offering))

    def test_T08_P_reject_invalid_group_snapshot(self):
        """7.1.2、7.5；OBJ-031/034；成员决定分别保存共同提交快照。"""
        submission = fixture("Submission")
        submission["group_ref"] = {"object_type": "LearnerGroup", "object_id": "https://example.edu/group/1"}
        members = [self.grant["subject_ref"], {"object_type": "Person", "object_id": "https://example.edu/person/2"}]
        submission["member_refs"] = members
        self.proposal("member1", submission=submission, learner_ref=members[0])
        self.proposal("member2", submission=submission, learner_ref=members[1])
        submission["member_refs"] = []
        rows = self.s.grade_view(self.token(), self.instance, formal=False)["decisions"]
        self.assertEqual(rows[0]["submission"]["member_refs"], members)
        self.assertEqual(rows[0]["submission"], rows[1]["submission"])
        self.assertNotEqual(rows[0]["learner_ref"], rows[1]["learner_ref"])
        self.denied(self.s.propose_grade(self.token(), fixture("GradeDecision"), self.offering, submission=submission))

    def test_T08_P_positive_proposal_not_formal(self):
        """7.5、9.5；OBJ-034；AI 提议保留引用版本且不进入正式视图。"""
        method = ref(fixture("MethodRegistration"))
        source = ref(fixture("Resource"))
        p = self.proposal(method_ref=method, source_refs=[source])
        self.assertEqual(self.s.grade_view(self.token(), self.instance)["decisions"], [])
        row = self.s.grade_view(self.token(), self.instance, formal=False)["decisions"][0]
        self.assertEqual(row["object"], p)
        self.assertEqual(row["method_ref"], method)
        self.assertEqual(row["source_refs"], [source])

    def test_T08_C_positive_personnel_confirmation(self):
        """7.5.2、9.2.4；OBJ-034；委托确认追溯人员与客户端。"""
        confirmed = self.confirmation(self.proposal())
        row = self.s.grade_view(self.token(), self.instance)["decisions"][0]
        self.assertEqual(row["object"], confirmed)
        self.assertEqual(row["confirmed_by"], {"teacher": self.grant["subject_ref"], "client_id": self.grant["client_id"]})

    def test_T08_A_positive_exact_acceptance_archives(self):
        """7.5.4；OBJ-034；具体确认决定的 accepted 接收推进归档。"""
        confirmed = self.confirmation(self.proposal())
        self.ok(self.s.registrar_receipt(self.admin, ref(confirmed), "accepted", "synthetic-r1"))
        row = self.s.grade_view(self.token(), self.instance)["decisions"][0]
        self.assertEqual(row["state"], "archived")
        self.assertEqual(row["registrar_status"], "accepted")

    def test_T08_R_positive_append_keeps_predecessor(self):
        """7.5.5；OBJ-034；更正追加，原决定保留可查。"""
        original = self.confirmation(self.proposal())
        self.ok(self.s.registrar_receipt(self.admin, ref(original), "accepted", "old-r"))
        corrected = self.confirmation(self.proposal("new-p", supersedes=ref(original), basis="synthetic correction"), "new-c")
        self.ok(self.s.registrar_receipt(self.admin, ref(corrected), "accepted", "new-r"))
        self.assertEqual(self.s.grade_view(self.token(), self.instance)["decisions"][0]["object"], corrected)
        self.assertEqual(len(self.s.grade_view(self.token(), self.instance, formal=False)["decisions"]), 4)
