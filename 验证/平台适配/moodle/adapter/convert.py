"""Moodle 6.0dev native backup, logstore and table projection."""
from collections import Counter
from hashlib import sha1
from xml.etree import ElementTree as ET

from wp4b.common import Projection, archive, by, digest, member_source, row_source, utc


def backups(p):
    for path in sorted(p.samples.glob("*.mbz")):
        files = archive(path)
        course = ET.fromstring(files["course/course.xml"])
        course_id = course.attrib["id"]
        backup = ET.fromstring(files["moodle_backup.xml"]).find("information")
        modules = []
        for name, content in sorted(files.items()):
            if name.startswith("activities/") and name.endswith("/module.xml"):
                node = ET.fromstring(content)
                activity_file = f"{name.rsplit('/', 1)[0]}/{node.findtext('modulename')}.xml"
                definition = ET.fromstring(files[activity_file])
                modules.append({"module_id": node.attrib["id"], "section_id": node.findtext("sectionid"),
                                "kind": node.findtext("modulename"), "member": activity_file,
                                "definition_id": definition.attrib.get("id"),
                                "context_id": definition.attrib.get("contextid"),
                                "module_blob": p.retain(content)})
        resources = []
        for f in ET.fromstring(files["files.xml"]).findall("file"):
            name = f.findtext("filename")
            if name == ".":
                continue
            native_hash = f.findtext("contenthash")
            member = f"files/{native_hash[:2]}/{native_hash}"
            content = files[member]
            if sha1(content).hexdigest() != native_hash or len(content) != int(f.findtext("filesize")):
                raise ValueError(f"MBZ file pool mismatch: {member}")
            resource = p.asset("files", f.attrib["id"], content,
                               [member_source(path.name, k) for k in ("files.xml", member)],
                               title=name, media_type=f.findtext("mimetype"),
                               created_at=utc(f.findtext("timecreated")))
            resources.append({"resource_id": resource["instance"]["object_id"],
                              "context_id": f.findtext("contextid"), "blob": p.retain(content)})
        p.note("course_snapshot", [member_source(path.name, "course/course.xml"),
                                   member_source(path.name, "moodle_backup.xml")],
               ["OBJ-005", "OBJ-006", "OBJ-013", "OBJ-014", "FLD-MAN-005", "FLD-MAN-009"],
               snapshot_sha256=digest(path.read_bytes()), course_code=course.findtext("idnumber"),
               native_backup_task=backup.find("details/detail").attrib["backup_id"],
               offering=p.ref("Offering", "course", course_id), modules=modules, resources=resources)


def rosters(p):
    for row in p.rows("user"):
        if row["username"] != "guest":
            p.add("Person", p.object("Person", "user", row["id"]),
                  [row_source("user", row["id"])], ["OBJ-001"])
    for row in p.rows("course"):
        if row["format"] == "site":
            continue
        p.add("Offering", p.object("Offering", "course", row["id"], created_at=utc(row["timecreated"])),
              [row_source("course", row["id"])], ["OBJ-006"])
    enrol_methods = by(p.rows("enrol"), "id")
    roles = by(p.rows("role"), "id")
    contexts = by(p.rows("context"), "id")
    students = {(contexts[r["contextid"]]["instanceid"], r["userid"]) for r in p.rows("role_assignments")
                if roles[r["roleid"]]["shortname"] == "student" and contexts[r["contextid"]]["contextlevel"] == "50"}
    result = {}
    for row in p.rows("user_enrolments"):
        method = enrol_methods[row["enrolid"]]
        course, user = method["courseid"], row["userid"]
        if (course, user) not in students:
            continue
        if (course, user) in result:
            raise ValueError("ambiguous Moodle enrolment")
        p.add("Enrollment", p.object("Enrollment", "user_enrolments", row["id"],
                                     offering_ref=p.ref("Offering", "course", course),
                                     learner_ref=p.ref("Person", "user", user), created_at=utc(row["timecreated"])),
              [row_source("user_enrolments", row["id"]), row_source("enrol", method["id"]), "role_assignments.json"],
              ["OBJ-007"])
        result[course, user] = row
    return result


def learner(p, course, user, enrolments):
    fields = p.offering("course", course)
    if (course, user) in enrolments:
        fields.update(actor_ref=p.ref("Person", "user", user), actor_type="learner", entry_mode="self",
                      enrollment_id=p.key("user_enrolments", enrolments[course, user]["id"]))
    return fields


def responses(p, enrolments, attempts):
    questions = by(p.rows("question_attempts"), "id")
    steps = by(p.rows("question_attempt_steps"), "id")
    quizzes = by(p.rows("quiz"), "id")
    usages = by(list(attempts.values()), "uniqueid")
    for row in p.rows("question_attempt_step_data"):
        if row["name"] != "answer":
            continue
        step = steps[row["attemptstepid"]]
        question = questions[step["questionattemptid"]]
        attempt = usages[question["questionusageid"]]
        at = utc(step["timecreated"])
        course = quizzes[attempt["quiz"]]["course"]
        attempt_ref = p.ref("TaskAttempt", "quiz_attempts", attempt["id"])
        artifact = p.ref("ProcessArtifact", "question_attempt_step_data", row["id"])
        sources = [row_source("question_attempt_step_data", row["id"]), row_source("question_attempt_steps", step["id"]),
                   row_source("question_attempts", question["id"]), row_source("quiz_attempts", attempt["id"])]
        p.add("ProcessArtifact", p.object("ProcessArtifact", "question_attempt_step_data", row["id"],
                                         attempt_ref=attempt_ref, created_at=at),
              sources, ["OBJ-030"])
        p.note("response_value", sources, ["OBJ-030", "FLD-EVT-020"],
               artifact=artifact, question_id=question["questionid"], answer=row["value"])
        user = step["userid"]
        fields = (learner(p, course, user, enrolments) if user == attempt["userid"] and attempt["preview"] == "0"
                  else p.offering("course", course))
        if "enrollment_id" in fields:
            sources.extend([row_source("user_enrolments", enrolments[course, user]["id"]), "role_assignments.json"])
        # Moodle stores the responding user on the persistent answer step, not on a grade notification.
        instance = p.event("response.recorded", p.key("question_attempt_step_data", row["id"]), **fields,
                           object_ref=artifact, attempt_ref=attempt_ref, artifact_refs=[artifact],
                           occurred_at=at, payload={"response_value": row["value"]} if len(row["value"]) <= 256 else {})
        p.add("event", instance, sources, ["OBJ-029", "EVT-011"], fields={
            "/attempt_ref": "FLD-EVT-015", "/artifact_refs": "FLD-EVT-016", "/payload": "FLD-EVT-020"})


def submissions(p):
    text = by(p.rows("assignsubmission_onlinetext"), "submission")
    for row in p.rows("assign_submission"):
        native = row["id"]
        row_evidence = row_source("assign_submission", native)
        # The per-user shadow rows of a team submission have no content and are not separate works.
        if row["status"] != "submitted" or native not in text:
            p.note("assignment_row_without_exported_work", [row_evidence], ["OBJ-031"],
                   id=native, status=row["status"], attempt_number=int(row["attemptnumber"]))
            continue
        src = text[native]
        sources = [row_evidence, row_source("assignsubmission_onlinetext", src["id"])]
        artifact = p.ref("ProcessArtifact", "assignsubmission_onlinetext", src["id"])
        attempt = p.ref("TaskAttempt", "assign_submission", native)
        p.add("TaskAttempt", p.object("TaskAttempt", "assign_submission", native,
                                     attempt_number=int(row["attemptnumber"]) + 1),
              sources, ["OBJ-009"], gaps={"/enrollment_round_ref": "作业重开不等于新的修读轮次"})
        p.add("ProcessArtifact", p.object("ProcessArtifact", "assignsubmission_onlinetext", src["id"], attempt_ref=attempt),
              sources, ["OBJ-030"])
        fields = {"group_ref": p.ref("LearnerGroup", "groups", row["groupid"])} if row["groupid"] != "0" else {}
        gaps = {"/member_refs": "只有当前成员，未保存提交时点成员"} if fields else {}
        p.add("Submission", p.object("Submission", "assign_submission", native,
                                    attempt_ref=attempt, artifact_refs=[artifact], **fields),
              sources, ["OBJ-031"], gaps=gaps)
        p.note("submission_text", sources, ["OBJ-031", "OBJ-030"],
               artifact=artifact, blob=p.retain(src["onlinetext"].encode()),
               native_attempt_number=int(row["attemptnumber"]), group_id=row["groupid"])
    return text


def logs(p, enrolments, attempts, texts):
    assignments = by(p.rows("assign_submission"), "id")
    rows = p.rows("logstore_standard_log")
    for row in rows:
        name = row["eventname"].rsplit("\\", 1)[-1]
        course, user, native = row["courseid"], row["userid"], row["objectid"]
        source = row_source("logstore_standard_log", row["id"])
        common = {"occurred_at": utc(row["timecreated"]), "payload": {}}
        event_id = p.key("logstore_standard_log", row["id"])
        owned = learner(p, course, user, enrolments) if not row["realuserid"] else p.offering("course", course)
        if name == "attempt_started" and native in attempts:
            p.add("event", p.event("activity.started", event_id, **common, **owned,
                                  attempt_ref=p.ref("TaskAttempt", "quiz_attempts", native)),
                  [source, row_source("quiz_attempts", native)], ["OBJ-029", "EVT-006"],
                  gaps={"/object_ref": "日志仅指向模块，没有发生时活动版本"})
        elif name == "assessable_submitted" and row["component"] == "mod_assign" and native in texts:
            sub = assignments[native]
            actor = owned if sub["userid"] == user else p.offering("course", course)
            gaps = {"/source_recorded_at": "日志发生时间、行修改时间并非可靠持久化凭证"}
            if sub["groupid"] != "0":
                common["group_ref"] = p.ref("LearnerGroup", "groups", sub["groupid"])
                gaps["/member_refs"] = "提交时组成员快照缺失"
            p.add("event", p.event("submission.submitted", event_id, **common, **actor,
                                  object_ref=p.ref("Submission", "assign_submission", native),
                                  artifact_refs=[p.ref("ProcessArtifact", "assignsubmission_onlinetext", texts[native]["id"])],
                                  attempt_ref=p.ref("TaskAttempt", "assign_submission", native)),
                  [source, row_source("assign_submission", native), row_source("assignsubmission_onlinetext", texts[native]["id"])],
                  ["OBJ-029", "EVT-013"], gaps=gaps)
        elif name == "course_module_viewed" and row["component"] == "mod_resource":
            p.add("event", p.event("resource.opened", event_id, **common, **owned), [source],
                  ["OBJ-029", "EVT-004"], gaps={"/object_ref": "没有事件发生时资源版本",
                                              "/payload/capability_ref": "采集能力没有登记"})
        elif name in {"user_enrolment_created", "user_enrolment_updated"}:
            p.note("enrolment_log", [source], ["OBJ-007", "EVT-002"], action=name, native_enrolment_id=native,
                   offering=p.ref("Offering", "course", course), at=common["occurred_at"])
    p.note("logstore_inventory", ["logstore_standard_log.json"], ["OBJ-029"],
           native_types=dict(Counter(r["eventname"] for r in rows)))


def convert(samples, profile_id, profile_version):
    p = Projection("moodle", samples, profile_id, profile_version)
    backups(p)
    enrolments = rosters(p)
    attempts = by(p.rows("quiz_attempts"), "id")
    for row in attempts.values():
        p.add("TaskAttempt", p.object("TaskAttempt", "quiz_attempts", row["id"],
                                     attempt_number=int(row["attempt"]), created_at=utc(row["timestart"])),
              [row_source("quiz_attempts", row["id"])], ["OBJ-009"])
    responses(p, enrolments, attempts)
    logs(p, enrolments, attempts, submissions(p))
    items = by(p.rows("grade_items"), "id")
    for row in p.rows("grade_grades_history"):
        sources = [row_source("grade_grades_history", row["id"])]
        item = items.get(row["itemid"])
        if item:
            sources.append(row_source("grade_items", item["id"]))
        p.note("native_grade_history", sources, ["OBJ-034", "EVT-020"], history_id=row["id"],
               native_grade_id=row["oldid"], native_item_id=row["itemid"], grade=row["finalgrade"],
               raw_grade=row["rawgrade"], at=utc(row["timemodified"]), action=row["action"],
               learner=p.ref("Person", "user", row["userid"]), native_source=row["source"],
               course_id=item["courseid"] if item else None, native_grader_id=row["loggeduser"])
    return p
