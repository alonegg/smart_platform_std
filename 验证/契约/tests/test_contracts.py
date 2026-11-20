from collections import Counter
import hashlib
import json
from pathlib import Path
import subprocess
import sys

from jsonschema import Draft202012Validator
import pytest

from payload_hash import payload_hash
from validate import ROOT, SCHEMAS, load, schema_errors, semantic_rules, validate


FIXTURES = sorted((ROOT / "fixtures").rglob("*.json"))


@pytest.mark.parametrize("path", FIXTURES, ids=lambda p: str(p.relative_to(ROOT)))
def test_fixture(path):
    fixture = load(path)
    meta = fixture["fixture"]
    result = validate(fixture)
    expected = "passed" if meta["expect"] == "valid" else "failed"
    assert result["result"] == expected, result
    assert meta["clauses"]
    if expected == "failed":
        assert meta["violates"]
        rules = {e["rule_id"] for c in result["checks"] for e in c["errors"]}
        assert set(meta["expected_rule_ids"]) <= rules, result


@pytest.mark.parametrize("path", sorted(SCHEMAS))
def test_schema(path):
    Draft202012Validator.check_schema(SCHEMAS[path])


def test_fixture_coverage():
    counts = Counter()
    for path in FIXTURES:
        f = load(path)
        target = f["fixture"]["target"]
        if target == "event":
            target = f["instance"]["event_type"]
        counts[target, f["fixture"]["expect"]] += 1
    for target in ["Person", "Segment", "GradeDecision", "ObjectRef", "IndependentRef",
                   "EmbeddedRef", "RecordRef", "NonVersionedRef", "submission.submitted",
                   "grade.confirmed", "grade.proposed"]:
        assert counts[target, "valid"] >= 1
        assert counts[target, "invalid"] >= 2


def test_vocab_matches_current_standard():
    standard = (ROOT.parents[1] / "标准/评审稿/智慧教学-数据模型标准.md").read_text()
    table = standard.split("表 5-1 核心对象总览", 1)[1].split("5.1.9", 1)[0]
    rows = [line.split("|")[1:-1] for line in table.splitlines() if line.startswith("| ")][1:]
    actual = load(ROOT / "vocab/object_types.json")["values"]
    assert len(actual) == 46
    assert {x["object_type"]: x["versioning"] for x in actual} == {r[0].strip(): r[3].strip() for r in rows}
    table = standard.split("表 7-2 最小事件词表", 1)[1].split("7.3.2", 1)[0]
    rows = [line.split("|")[1:-1] for line in table.splitlines() if line.startswith("| ")][1:]
    events = load(ROOT / "vocab/event_types.json")["values"]
    assert len(events) == 24
    assert {e["event_type"]: e["event_class"] for e in events} == {r[1].strip(): r[2].strip() for r in rows}
    for e in events:
        assert e["status"] == ("optional_by_capability" if e["event_type"].startswith("discussion.") else "first_phase")


def test_event_definitions():
    events = {e["event_type"]: e for e in load(ROOT / "vocab/event_types.json")["values"]}
    paths = sorted((ROOT / "events").glob("*.json"))
    assert len(paths) == 24
    assert {p.stem for p in paths} == set(events)
    for path in paths:
        definition = load(path)
        assert definition["event_class"] == events[path.stem]["event_class"]
        Draft202012Validator.check_schema(definition["payload_schema"])
        assert definition["payload_schema"]["additionalProperties"] is False
        assert definition["payload_schema"]["x-assumption"]
        assert definition["ai_may_emit"] == ("ai_service" in definition["allowed_actor_types"])


VECTORS = load(ROOT / "vectors/payload_hash.json")["vectors"]


@pytest.mark.parametrize("vector", VECTORS, ids=lambda v: v["name"])
def test_hash_vector(vector):
    assert payload_hash(json.loads(vector["event_json"]), vector["hash_envelope_members"]) == vector["sha256"]
    assert hashlib.sha256(vector["canonical"].encode()).hexdigest() == vector["sha256"]


def test_hash_distinctions():
    vectors = {v["name"]: v["sha256"] for v in VECTORS}
    assert vectors["integer"] != vectors["float"]
    assert vectors["NFC"] != vectors["NFD"]
    assert vectors["null"] != vectors["empty-missing"]
    assert vectors["with-envelope"] != vectors["without-envelope"]
    assert vectors["empty-missing"] == vectors["without-envelope"] == vectors["receiver-excluded"]


def test_hash_serializer_is_replaceable():
    data = {"payload": {"synthetic": True}}
    alternative = payload_hash(data, [], serializer=lambda body: b"controlled-synthetic-bytes")
    assert alternative == hashlib.sha256(b"controlled-synthetic-bytes").hexdigest()
    assert alternative != payload_hash(data, [])


@pytest.mark.parametrize("value", [None, [], "", 0, {}])
def test_empty_or_unknown(value):
    assert validate(value)["result"] == "failed"


def test_rule_extraction_and_pointer():
    schema = {"type": "object", "x-rule-id": "R-TEST-001", "properties": {
        "a/b~": {"type": "integer", "x-rule-id": "R-TEST-002"}}}
    assert schema_errors({"a/b~": "bad"}, schema)[0]["rule_id"] == "R-TEST-002"
    assert schema_errors({"a/b~": "bad"}, schema)[0]["pointer"] == "/a~1b~0"
    assert schema_errors(1, {"type": "string"})[0]["rule_id"] == "SCHEMA-type"


@pytest.mark.parametrize("name,valid,invalid", [
    ("ProfileDecl", {}, {"profile_id": "p"}),
    ("MissingReasons", [], [{"pointer": "/value", "reason": "not_applicable"}]),
    ("ExternalId", {"source_system": "s", "source_id": "1", "mapping_status": "pending"},
     {"source_system": "s", "source_id": "1", "mapping_status": "unknown"}),
    ("Extensions", {}, {"unregistered": 1}),
    ("Timestamp", "2026-01-01T08:00:00+08:00", "2026-01-01T08:00:00"),
    ("ByteLength", 0, -1),
    ("Sha256", "a" * 64, "A" * 64),
])
def test_common_definitions(name, valid, invalid):
    common = SCHEMAS["schema/common.schema.json"]
    schema = {"$ref": common["$id"] + "#/$defs/" + name}
    assert not schema_errors(valid, schema)
    assert schema_errors(invalid, schema)


def test_delegated_auth_context():
    context = load(ROOT / "fixtures/valid/event/event-grade.confirmed-stored.json")["instance"]["auth_context"]
    schema = {"$ref": SCHEMAS["schema/common.schema.json"]["$id"] + "#/$defs/AuthContext"}
    assert not schema_errors(context, schema)
    context["access_mode"] = "delegated"
    assert {e["rule_id"] for e in schema_errors(context, schema)} == {"R-AUTH-001"}
    context["on_behalf_of_ref"] = {"object_type": "Person", "object_id": "p"}
    context["delegation_grant_ref"] = {"object_type": "AccessGrant", "object_id": "g", "version_id": "v1"}
    assert not schema_errors(context, schema)


def test_record_reference_without_explicit_type():
    instance = load(ROOT / "fixtures/valid/GradeDecision/GradeDecision-minimal.json")["instance"]
    instance.update(decision_status="confirmed", proposer_type="staff", decider_type="staff",
                    decided_by={"object_id": "p"}, handles_proposal_ref={"object_id": "proposal-1"})
    assert validate(instance)["result"] == "passed"
    instance["handles_proposal_ref"]["version_id"] = "wrong"
    result = validate(instance)
    assert result["result"] == "failed"
    assert any(e["rule_id"] == "R-REF-004" for c in result["checks"] for e in c["errors"])


def test_cli_auto_detect_and_determinism():
    path = ROOT / "fixtures/valid/Person/Person-minimal.json"
    instance = load(path)["instance"]
    assert validate(instance)["result"] == "passed"
    assert validate(instance) == validate(instance)
    command = [sys.executable, str(ROOT / "tools/validate.py"), str(path)]
    result = subprocess.run(command, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)["result"] == "passed"
    result = subprocess.run(command[:-1] + [str(ROOT / "fixtures/invalid/event/event-T25-client-auth-context.json")], capture_output=True, text=True)
    assert result.returncode == 1
    parsed = json.loads(result.stdout)
    assert parsed["result"] == "failed"
    assert parsed["checks"][0]["errors"][0]["pointer"] == "/auth_context"


def test_cli_bad_json(tmp_path):
    path = tmp_path / "bad.json"
    path.write_text("{")
    result = subprocess.run([sys.executable, str(ROOT / "tools/validate.py"), str(path)], capture_output=True, text=True)
    assert result.returncode == 1
    assert json.loads(result.stdout)["checks"][0]["errors"][0]["rule_id"] == "R-INPUT-001"


def test_local_only_and_skipped_evidence():
    result = validate(load(ROOT / "fixtures/valid/event/event-submission.submitted.json"))
    assert result["result"] == "passed"
    skipped = [c for c in result["checks"] if c["result"] == "skipped"]
    assert any("需解析服务（WP2）" in e["reason"] for c in skipped for e in c["errors"])
    result = validate({"package_id": "p", "package_type": "teaching"})
    assert result["result"] == "failed"
    assert any(e["rule_id"] == "R-MAN-001" for c in result["checks"] for e in c["errors"])


def test_no_mutation():
    before = {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in ROOT.rglob("*.json")}
    for path in FIXTURES:
        fixture = load(path)
        original = json.dumps(fixture, sort_keys=True)
        validate(fixture)
        assert json.dumps(fixture, sort_keys=True) == original
    assert before == {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in ROOT.rglob("*.json")}
