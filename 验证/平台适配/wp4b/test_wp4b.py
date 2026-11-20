"""WP4b boundary checks (4.4.5); local diagnostics are not independent applications."""
from collections import Counter
import csv
import json
from pathlib import Path
from zipfile import ZipFile

import pytest

from run import PROFILE, PROJECTIONS, read_packet, run
from openedx.adapter.convert import match_answer, response_key
from wp4b.common import CONTRACT, ROOT, digest, wp1_validate
from wp4b.loss import MATRIX


@pytest.fixture(scope="module")
def output(tmp_path_factory):
    path = tmp_path_factory.mktemp("wp4b")
    run(path)
    return path


def load(path):
    return json.loads(path.read_bytes())


def get_notes(files, kind):
    return [n["facts"] for n in json.loads(files["native-evidence.json"]) if n["kind"] == kind]


@pytest.mark.parametrize("platform", PROJECTIONS)
def test_wp1_gate(output, platform):
    """WP1 5.1.3, 5.3, 7.2.3: OBJ-001, OBJ-029, FLD-EVT-001..023."""
    base = output / platform
    passed = load(base / "candidate-passed.json")
    blocked = load(base / "candidate-blocked.json")
    assert len(passed) == (3 if platform == "moodle" else 0)
    assert len(blocked) == (41 if platform == "moodle" else 44)
    assert all("event_type" in r and wp1_validate(r, "event")["result"] == "passed" for r in passed)
    for row in blocked:
        assert row["missing_fields"] or row["gaps"]
        assert row["instance"] not in passed
        assert wp1_validate(row["instance"], row["target"])["result"] == row["validation"]["result"]
        assert not {"received_at", "event_id", "auth_context", "rights_ref", "classification_ref",
                    "access_policy_ref"}.intersection(row["instance"])
    for row in (r for r in blocked if r["target"] == "Person"):
        assert set(row["missing_fields"]) >= {"/created_by", "/rights_ref", "/access_policy_ref", "/classification_ref"}


def test_t01_local_identifiers_separate_runs_attempts_and_versions(output):
    """12.3/T01, 5.1.3, 5.2.2, 5.2.6: OBJ-004..009, OBJ-031."""
    identities = {}
    for platform in PROJECTIONS:
        blocked = load(output / platform / "candidate-blocked.json")
        identities[platform] = {r["instance"]["object_id"] for r in blocked if r["target"] == "Offering"}
        assert len(identities[platform]) == 2
        assert not any(r["target"] == "EnrollmentRound" for r in blocked)
        submissions = [r["instance"] for r in blocked if r["target"] == "Submission"]
        assert len({r["object_id"] for r in submissions}) == len(submissions)
        if platform == "moodle":
            attempts = [r["instance"] for r in blocked
                        if r["target"] == "TaskAttempt" and "assign_submission:" in r["instance"]["object_id"]]
            assert sorted(r["attempt_number"] for r in attempts) == [1, 1, 2]
        else:
            attempts = [r["instance"] for r in blocked if r["target"] == "TaskAttempt"]
            assert len({r["object_id"] for r in attempts}) == 5
            assert Counter(r["attempt_number"] for r in attempts) == {1: 2, 2: 3}
            assert all("activity_ref" not in r and "enrollment_round_ref" not in r for r in attempts)
            assert len(submissions) == 2
            assert all("attempt_ref" not in r for r in submissions)
            assert all("course_version_ref" not in r["instance"] for r in blocked if r["target"] in {"Offering", "LearningActivity"})
    assert identities["openedx"].isdisjoint(identities["moodle"])
    native = load(ROOT / "openedx/samples/grades_persistentcoursegrade.json")
    evidence = read_packet(output / "openedx/diagnostic.zip")
    pointers = get_notes(evidence, "native_grade_version_pointer")
    assert [r["course_version"]["version_id"] for r in pointers] == [r["course_version"] for r in native]
    assert all(wp1_validate(r["course_version"], "ObjectRef")["result"] == "passed" for r in pointers)


@pytest.mark.parametrize("platform", PROJECTIONS)
def test_t02_offline_course_bytes_relations_and_nonconforming_manifest(output, platform):
    """12.3/T02, 8.2.4-8.2.9, 6.2.1: OBJ-005/013/020, FLD-RES-012/013, FLD-MAN-006/009/016."""
    out = output / platform
    files = read_packet(out / "diagnostic.zip")
    snapshots = get_notes(files, "course_snapshot")
    assert len(snapshots) == 2
    assert len({s["snapshot_sha256"] for s in snapshots}) == 2
    refs = [s["offering"]["object_id"] for s in snapshots]
    assert len(set(refs)) == (1 if platform == "moodle" else 2)
    resources = {r["instance"]["object_id"]: r["instance"] for r in json.loads(files["candidate-blocked.json"])
                 if r["target"] == "Resource"}
    for snapshot in snapshots:
        assert snapshot["modules"] and snapshot["resources"]
        if platform == "openedx":
            nodes = {r["id"] for r in snapshot["modules"]}
            assert len(nodes) == len(snapshot["modules"])
            assert all(r["parent"] in nodes or r["parent"] is None for r in snapshot["modules"])
            assert all(files[mod["definition_blob"]] for mod in snapshot["modules"])
        else:
            assert len({r["module_id"] for r in snapshot["modules"]}) == len(snapshot["modules"])
            assert all(r["context_id"] in {m["context_id"] for m in snapshot["modules"]} for r in snapshot["resources"])
            assert all(files[mod["module_blob"]] for mod in snapshot["modules"])
        for asset in snapshot["resources"]:
            contents = files[asset["blob"]]
            row = resources[asset["resource_id"]]
            assert (digest(contents), len(contents)) == (row["content_hash"], row["byte_length"])
            assert "storage_ref" not in row
    attempt = load(out / "manifest-attempt.json")
    assert attempt["validation"]["result"] == "failed"
    assert "export_scope" not in attempt["candidate"] and "rights_summary" not in attempt["candidate"]
    assert {e["path"] for e in attempt["candidate"]["files"]} == set(files)
    assert "manifest.json" not in files


def test_t02_reader_rejects_modified_archive(output, tmp_path):
    """8.2.5/8.2.8, FLD-MAN-009: detect altered member even with valid ZIP CRC."""
    path = tmp_path / "tampered.zip"
    with ZipFile(output / "openedx/diagnostic.zip") as src, ZipFile(path, "w") as dst:
        for name in src.namelist():
            dst.writestr(name, b"[]" if name == "native-evidence.json" else src.read(name))
    with pytest.raises(ValueError, match="inventory mismatch"):
        read_packet(path)


def test_t14_read_historical_data_from_archive_only(output, tmp_path):
    """12.3/T14, 12.10, 7.1.1, 7.3.4: OBJ-030/031/034, EVT-013/020."""
    for platform in PROJECTIONS:
        detached = tmp_path / f"{platform}.zip"
        detached.write_bytes((output / platform / "diagnostic.zip").read_bytes())
        files = read_packet(detached)
        works = get_notes(files, "submission_text")
        assert len(works) == (3 if platform == "moodle" else 2)
        assert len({r["blob"] for r in works}) == 2
        assert all("合成" in files[r["blob"]].decode() or
                   "合成" in json.loads(files[r["blob"]])["parts"][0]["text"] for r in works)
        history = get_notes(files, "native_grade_history")
        if platform == "moodle":
            by_item = [float(r["grade"]) for r in history if r["grade"] and r["native_item_id"] == "9"
                       and r["learner"]["object_id"].endswith(":15")]
            assert {60, 70, 85} <= set(by_item)
        else:
            assert [r["grade"] for r in history] == [2, 3.5]
        assert not any(r.get("event_type") in {"grade.corrected", "grade.confirmed"}
                       for r in json.loads(files["candidate-passed.json"]))


def test_event_provenance_and_no_protocol_duplication(output):
    """7.2/7.4, 7.7: OBJ-029, EVT-005/011/013 and FLD-EVT-005/014/019."""
    openedx = load(output / "openedx/native-evidence.json")
    protocol = [r for r in openedx if r["kind"] == "erb_projection"]
    assert Counter(r["sources"][0].split("#")[0] for r in protocol) == {"xapi.jsonl": 76, "caliper.jsonl": 37}
    assert sum(r["kind"] == "video_signal" for r in openedx) == 9
    responses = [r for r in load(output / "openedx/candidate-blocked.json")
                 if r["instance"].get("event_type") == "response.recorded"]
    assert len(responses) == 6
    assert all("/source_event_id" in r["missing_fields"] for r in responses)
    matched = [r for r in responses if "attempt_ref" in r["instance"]]
    assert len(matched) == 5
    for r in matched:
        assert "artifact_refs" in r["instance"]
        assert {s.split("#")[0] for s in r["sources"]} >= {
            "tracking.jsonl", "courseware_studentmodule.json", "courseware_studentmodulehistory.json"}
    events = load(output / "moodle/validation-passed.json")
    assert len({e["instance"]["source_event_id"] for e in events}) == 3
    assert all(e["instance"]["payload"] == {"response_value": "2"} for e in events)
    assert all(any(s.startswith("question_attempt_step_data.json#") for s in e["sources"]) for e in events)
    for platform in PROJECTIONS:
        blocked = load(output / platform / "candidate-blocked.json")
        submitted = [r for r in blocked if r["instance"].get("event_type") == "submission.submitted"]
        assert len(submitted) == (2 if platform == "openedx" else 3)
        assert all("/source_recorded_at" in r["missing_fields"] for r in submitted)
        for r in submitted:
            if "group_ref" in r["instance"]:
                assert "member_refs" not in r["instance"] and "/member_refs" in r["missing_fields"]


def test_openedx_answer_attribution_rejects_ambiguous_or_mismatched_rows():
    """7.1.1, 7.3.4 c): an ambiguous join must not manufacture works/attempt references."""
    row = {"event": {"problem_id": "p", "attempts": 1, "answers": {"q": "a"}},
           "context": {"course_id": "c", "user_id": 1}, "time": "2026-01-01T00:00:00.123Z"}
    key = response_key(row)
    historic = {"id": 1}
    matching = (historic, {"last_submission_time": "2026-01-01T00:00:00Z", "student_answers": {"q": "a"}})
    assert match_answer(row, {key: [matching]}, {key: 1}) is historic
    assert match_answer(row, {key: [matching]}, {key: 2}) is None
    assert match_answer(row, {key: [matching, matching]}, {key: 1}) is None
    mismatch = (historic, {**matching[1], "student_answers": {"q": "b"}})
    assert match_answer(row, {key: [mismatch]}, {key: 1}) is None


def test_loss_trace_covers_scope_and_matches_matrix(output):
    """4.4.5, 8.2.5 (FLD-MAN-014): trace every matrix element and clause."""
    with MATRIX.open(encoding="utf-8-sig", newline="") as matrix:
        static = {r["要素编号"]: r for r in csv.DictReader(matrix)}
    with (output / "loss.csv").open(encoding="utf-8", newline="") as report:
        rows = list(csv.DictReader(report))
    scope = set(load(CONTRACT / "scope.json")["element_ids"])
    assert len(rows) == len(static) * len(PROJECTIONS)
    assert {(r["platform"], r["element_id"]) for r in rows} == {(p, s) for p in PROJECTIONS for s in static}
    assert {r["status"] for r in rows} == {"已转换", "需公共服务补齐", "需平台扩展", "无法取得"}
    for row in rows:
        element = row["element_id"]
        target = "Moodle" if row["platform"] == "moodle" else "OpenEdX"
        assert row["clause"] == static[element]["标准条款"]
        assert row["wp1_scope"] == ("首批" if element in scope else "首批外参考")
        assert row["static_coverage"] == static[element][target + "覆盖度"]
        assert row["reason"] and all((ROOT / s).is_file() for s in row["output"].split(";"))
        assert all((ROOT / s).is_file() for s in row["sources"].split(";") if s)
        assert all((output / s).is_file() for s in row["runtime_output"].split(";"))
    for filename in ("loss.csv", "differences.csv"):
        assert (output / filename).read_bytes() == (Path(__file__).parent / filename).read_bytes()


@pytest.mark.parametrize("platform", PROJECTIONS)
def test_inputs_and_outputs_reproducible(output, tmp_path, platform):
    """5.1/8.2, OBJ-006, FLD-MAN-009: deterministic repro; block input drift."""
    path = ROOT / platform / "samples"
    before = {f.name: digest(f.read_bytes()) for f in path.iterdir() if f.is_file()}
    run(tmp_path)
    assert (tmp_path / platform / "diagnostic.zip").read_bytes() == (output / platform / "diagnostic.zip").read_bytes()
    assert before == {f.name: digest(f.read_bytes()) for f in path.iterdir() if f.is_file()}
    dest = tmp_path / "sources"
    dest.mkdir()
    for name in before:
        (dest / name).write_bytes((path / name).read_bytes())
    changed = dest / "platform.json"
    changed.write_bytes(changed.read_bytes() + b" ")
    with pytest.raises(ValueError, match="sample inventory mismatch"):
        PROJECTIONS[platform](dest, *PROFILE)
