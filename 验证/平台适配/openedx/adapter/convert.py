"""Open edX native OLX, tracking, ERB and table projection."""
from collections import Counter, defaultdict
from datetime import datetime
import json
from uuid import UUID
from xml.etree import ElementTree as ET

from wp4b.common import Projection, archive, by, digest, member_source, row_source


def olx(p):
    courses = set()
    for path in sorted(p.samples.glob("*.tar.gz")):
        files = archive(path)
        root_name, = (n for n in files if n.endswith("/course.xml"))
        root = ET.fromstring(files[root_name])
        org, code, run = (root.attrib[k] for k in ("org", "course", "url_name"))
        prefix = root_name.rsplit("/", 1)[0]
        course_file = f"{prefix}/course/{run}.xml"
        native_course, native_run = f"{org}+{code}", f"course-v1:{org}+{code}+{run}"
        src = [member_source(path.name, root_name), member_source(path.name, course_file)]
        if native_course not in courses:
            courses.add(native_course)
            p.add("Course", p.object("Course", "course_key", native_course, course_code=code),
                  src, ["OBJ-004"], gaps={"/organization_ref": "OLX 机构代码不是校级登记引用"})
        p.add("Offering", p.object("Offering", "course_run", native_run), src, ["OBJ-006"])
        relations = []

        def blocks(name, node, parent=None):
            local_key = node.attrib.get("url_name", name.rsplit("/", 1)[-1].removesuffix(".xml"))
            block_id = f"block-v1:{org}+{code}+{run}+type@{node.tag}+block@{local_key}"
            relations.append({"id": block_id, "parent": parent, "member": name, "kind": node.tag,
                              "definition_blob": p.retain(files[name])})
            if node.tag in {"video", "problem", "openassessment"}:
                p.add("LearningActivity", p.object("LearningActivity", "block", block_id),
                      [member_source(path.name, name)], ["OBJ-014"],
                      gaps={"/course_version_ref": "OLX 不含与评分记录版本关联的可验证发布标识"})
                return
            for child in node:
                if child.tag not in {"chapter", "sequential", "vertical", "video", "problem", "openassessment"}:
                    continue
                child_file = f"{prefix}/{child.tag}/{child.attrib['url_name']}.xml"
                if child_file not in files and len(child) == 0:
                    raise ValueError(f"unresolved OLX reference: {child_file}")
                if child_file in files:
                    blocks(child_file, ET.fromstring(files[child_file]), block_id)
                else:
                    blocks(name, child, block_id)

        blocks(course_file, ET.fromstring(files[course_file]))
        resources = []
        metadata_name = f"{prefix}/policies/assets.json"
        for _, meta in sorted(json.loads(files[metadata_name]).items()):
            member = f"{prefix}/static/{meta['import_path']}"
            resource = p.asset("asset_key", meta["filename"], files[member],
                               [member_source(path.name, k) for k in (metadata_name, member)],
                               title=meta["displayname"], media_type=meta["contentType"])
            resources.append({"resource_id": resource["instance"]["object_id"],
                              "blob": p.retain(files[member])})
        p.note("course_snapshot", src + [path.name], ["OBJ-005", "OBJ-006", "OBJ-013", "OBJ-014", "FLD-MAN-009"],
               snapshot_sha256=digest(path.read_bytes()), offering=p.ref("Offering", "course_run", native_run),
               course=p.ref("Course", "course_key", native_course), modules=relations, resources=resources)


def rosters(p):
    for row in p.rows("auth_user"):
        p.add("Person", p.object("Person", "auth_user", row["id"]),
              [row_source("auth_user", row["id"])], ["OBJ-001"])
    staff = {(r["course_id"], r["user_id"]) for r in p.rows("student_courseaccessrole")}
    result = {}
    for row in p.rows("student_courseenrollment"):
        course, user = row["course_id"], row["user_id"]
        if (course, user) in staff:
            continue
        if (course, user) in result:
            raise ValueError("ambiguous Open edX enrolment")
        p.add("Enrollment", p.object("Enrollment", "student_courseenrollment", row["id"],
                                     offering_ref=p.ref("Offering", "course_run", course),
                                     learner_ref=p.ref("Person", "auth_user", user)),
              [row_source("student_courseenrollment", row["id"]), "student_courseaccessrole.json"], ["OBJ-007"])
        result[course, user] = row
    for row in p.rows("student_courseenrollment_history"):
        p.note("enrolment_history", [row_source("student_courseenrollment_history", row["history_id"], "history_id")],
               ["OBJ-007", "EVT-002"], native_enrolment_id=row["id"], history_id=row["history_id"],
               active=bool(row["is_active"]), mode=row["mode"], source_time=row["history_date"],
               offering=p.ref("Offering", "course_run", row["course_id"]))
    return result


def submissions(p):
    items = by(p.rows("submissions_studentitem"), "id")
    submissions = {}
    for row in p.rows("submissions_submission"):
        native = str(UUID(row["uuid"]))
        item = items[row["student_item_id"]]
        sources = [row_source("submissions_submission", row["id"]), row_source("submissions_studentitem", item["id"])]
        artifact = p.ref("ProcessArtifact", "submissions_submission", native)
        submissions[native] = artifact, sources, item
        p.add("ProcessArtifact", p.object("ProcessArtifact", "submissions_submission", native), sources, ["OBJ-030"])
        p.add("Submission", p.object("Submission", "submissions_submission", native, artifact_refs=[artifact]),
              sources, ["OBJ-031"], gaps={"/attempt_ref": "重置前后原生 attempt_number 重复，未确认独立尝试身份"})
        answer = json.loads(row["raw_answer"])
        p.note("submission_text", sources, ["OBJ-031", "OBJ-030", "OBJ-009"], artifact=artifact,
               blob=p.retain(row["raw_answer"].encode()), texts=[part["text"] for part in answer["parts"]],
               native_attempt_number=row["attempt_number"], native_status=row["status"], block_id=item["item_id"])
    return submissions


def answer_history(p):
    modules = by(p.rows("courseware_studentmodule"), "id")
    matches = defaultdict(list)
    for row in p.rows("courseware_studentmodulehistory"):
        state = json.loads(row["state"])
        module = modules[row["student_module_id"]]
        key = (module["course_id"], module["student_id"], module["module_id"], state["attempts"])
        matches[key].append((row, state))
        p.note("answer_history", [row_source("courseware_studentmodulehistory", row["id"])],
               ["OBJ-009", "OBJ-030", "EVT-011"], native_module_id=row["student_module_id"],
               version=row["version"], answers=state["student_answers"], attempt_count=state["attempts"])
    return matches


def response_key(tracking):
    ev, ctx = tracking["event"], tracking["context"]
    return (ctx.get("course_id"), ctx.get("user_id"), ev.get("problem_id"), ev.get("attempts"))


def match_answer(row, history, multiplicity):
    key = response_key(row)
    candidates = history.get(key, [])
    if multiplicity[key] != 1 or len(candidates) != 1:
        return None
    historic, state = candidates[0]
    logged_at = datetime.fromisoformat(row["time"]).replace(microsecond=0)
    if (logged_at != datetime.fromisoformat(state["last_submission_time"])
            or row["event"]["answers"] != state["student_answers"]):
        return None
    return historic


def tracking(p, enrolments, submissions):
    rows = p.jsonl("tracking")
    history = answer_history(p)
    multiplicity = Counter(response_key(r) for r in rows if r["event_type"] == "problem_check")
    for index, row in enumerate(rows, 1):
        name = row["event_type"]
        ctx = row["context"]
        course, user = ctx.get("course_id"), ctx.get("user_id")
        source = f"tracking.jsonl#line={index}"
        ev = row["event"]
        if isinstance(ev, str):
            try:
                ev = json.loads(ev)
            except json.JSONDecodeError:
                ev = {}
        fields = {"occurred_at": row["time"]}
        if course:
            fields.update(p.offering("course_run", course))
        if (course, user) in enrolments and name != "edx.course.enrollment.activated":
            fields.update(actor_ref=p.ref("Person", "auth_user", user), actor_type="learner", entry_mode="self",
                          enrollment_id=p.key("student_courseenrollment", enrolments[course, user]["id"]))
        if name == "problem_check":
            answers = ev["answers"]
            answer = next(iter(answers.values())) if len(answers) == 1 else None
            fields["payload"] = {"response_value": answer} if isinstance(answer, str) and len(answer) <= 256 else {}
            marks = {"/payload": "FLD-EVT-020"} if fields["payload"] else {}
            historic = match_answer(row, history, multiplicity)
            if historic is None:
                p.add("event", p.event("response.recorded", **fields), [source], ["OBJ-029", "EVT-011"],
                      fields=marks, gaps={"/source_event_id": "tracking 行号不是可重放事实键",
                                          "/attempt_ref": "无可唯一关联的原生历史尝试",
                                          "/object_ref": "无可唯一关联的持久作答作品"})
                continue
            table = "courseware_studentmodulehistory"
            native = historic["id"]
            sources = [source, row_source(table, native), row_source("courseware_studentmodule", historic["student_module_id"])]
            attempt = p.ref("TaskAttempt", table, native)
            artifact = p.ref("ProcessArtifact", "capa_answer_history", native)
            p.add("TaskAttempt", p.object("TaskAttempt", table, native, attempt_number=ev["attempts"]),
                  sources, ["OBJ-009"])
            p.add("ProcessArtifact", p.object("ProcessArtifact", "capa_answer_history", native, attempt_ref=attempt),
                  sources, ["OBJ-030"])
            if (course, user) in enrolments:
                sources.append(row_source("student_courseenrollment", enrolments[course, user]["id"]))
            p.add("event", p.event("response.recorded", **fields, object_ref=artifact,
                                  attempt_ref=attempt, artifact_refs=[artifact]), sources, ["OBJ-029", "EVT-011"],
                  fields={**marks, "/attempt_ref": "FLD-EVT-015", "/artifact_refs": "FLD-EVT-016"},
                  gaps={"/source_event_id": "历史记录主键只能定位作答，非 tracking 源事件键"})
        elif name == "openassessmentblock.create_submission":
            native = str(UUID(ev["submission_uuid"]))
            artifact, sources, item = submissions[native]
            if item["course_id"] != course:
                raise ValueError("ORA submission/course mismatch")
            fields.update(occurred_at=ev["submitted_at"], payload={}, artifact_refs=[artifact],
                          object_ref=p.ref("Submission", "submissions_submission", native))
            p.add("event", p.event("submission.submitted", **fields),
                  [source, *sources], ["OBJ-029", "EVT-013"],
                  gaps={"/source_event_id": "ORA 提交 UUID 不是 tracking 源事件键",
                        "/attempt_ref": "ORA 重置并不保留独立尝试身份",
                        "/source_recorded_at": "仅有提交时间及行创建时间，未记录可靠持久化时间"})
        elif name in {"play_video", "pause_video", "stop_video"}:
            p.note("video_signal", [source], ["EVT-005", "OBJ-021"], action=name,
                   at=row["time"], block_id=ev["id"], position_seconds=ev["currentTime"],
                   duration_seconds=ev.get("duration"))
    p.note("tracking_inventory", ["tracking.jsonl"], ["OBJ-029"], native_types=dict(Counter(r["event_type"] for r in rows)))


def protocols(p):
    def observe(source, event_id, actor, verb, object_id, at, elements):
        p.note("erb_projection", [source], ["OBJ-029", *elements], external_id=event_id, external_actor=actor,
               external_verb=verb, external_object=object_id, occurred_at=at)

    for index, row in enumerate(p.jsonl("xapi"), 1):
        verb = row["verb"]["id"]
        action = verb.rsplit("/", 1)[-1]
        elements = (["EVT-002"] if action in {"registered", "unregistered"} else
                    ["EVT-005"] if action in {"played", "paused", "terminated"} and "video" in row["object"]["id"] else [])
        observe(f"xapi.jsonl#line={index}", row["id"], row["actor"]["account"], verb, row["object"]["id"],
                row["timestamp"], elements)
    for index, envelope in enumerate(p.jsonl("caliper"), 1):
        for position, row in enumerate(envelope["data"]):
            elements = (["EVT-005"] if row["type"] == "MediaEvent" else
                        ["EVT-002"] if row["action"] in {"Activated", "Deactivated"} else [])
            observe(f"caliper.jsonl#line={index}/data/{position}", row["id"], row["actor"]["id"], row["action"],
                    row["object"]["id"], row["eventTime"], elements)


def grades(p):
    subsections = by(p.rows("grades_persistentsubsectiongrade"), "id")
    for row in p.rows("grades_historicalpersistentsubsectiongradeoverride"):
        grade = subsections[row["grade_id"]]
        p.note("native_grade_history",
               [row_source("grades_historicalpersistentsubsectiongradeoverride", row["history_id"], "history_id"),
                row_source("grades_persistentsubsectiongrade", grade["id"])], ["OBJ-034", "EVT-020"],
               history_id=row["history_id"], native_grade_id=row["grade_id"], grade=row["earned_graded_override"],
               possible=row["possible_graded_override"], source_time=row["history_date"],
               source_reason=row["override_reason"], native_grader_id=row["history_user_id"],
               learner=p.ref("Person", "auth_user", grade["user_id"]), course_id=grade["course_id"])
    seen = set()
    for row in p.rows("grades_persistentcoursegrade"):
        run, token = row["course_id"], row["course_version"]
        if not token:
            continue
        org, code, _ = run.split(":", 1)[1].split("+")
        ref = p.ref("CourseVersion", "modulestore", run, token)
        source = row_source("grades_persistentcoursegrade", row["id"])
        if (run, token) not in seen:
            seen.add((run, token))
            p.add("CourseVersion", p.object("CourseVersion", "modulestore", run, version_id=token,
                                            course_ref=p.ref("Course", "course_key", f"{org}+{code}")),
                  [source], ["OBJ-005"], gaps={"/course_profile": "历史成绩的原生版本指针没有可确认的版本内容"})
        p.note("native_grade_version_pointer", [source], ["OBJ-005", "OBJ-034"], course_version=ref,
               grade=row["percent_grade"], grade_id=row["id"])


def convert(samples, profile_id, profile_version):
    p = Projection("openedx", samples, profile_id, profile_version)
    olx(p)
    enrolments = rosters(p)
    tracking(p, enrolments, submissions(p))
    protocols(p)
    grades(p)
    return p
