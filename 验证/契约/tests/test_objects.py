from collections import Counter
from copy import deepcopy
import json
import subprocess
import sys

from jsonschema import Draft202012Validator
import pytest

from validate import ROOT, SCHEMAS, load, schema_errors, validate, walk


TARGETS = """Organization AcademicSession Course CourseVersion Offering Enrollment
EnrollmentRound TeachingAssignment ApplicationInstance AccessGrant Resource RightsRecord
LearningActivity AssessmentPlan AssessmentAdjustment TaskAttempt Submission ProcessArtifact
Feedback PeerReview CognitiveState EvidenceLink MethodRegistration MethodApproval""".split()


def sample(target):
    return load(ROOT / f"fixtures/valid/{target}/{target}-minimal.json")["instance"]


def rules(result):
    return {e["rule_id"] for c in result["checks"] if c["result"] == "failed" for e in c["errors"]}


@pytest.mark.parametrize("target", TARGETS)
def test_object_coverage_and_empty_input(target):
    counts = Counter(load(p)["fixture"]["expect"] for p in (ROOT / "fixtures").glob(f"*/{target}/*.json"))
    assert counts["valid"] >= 1 and counts["invalid"] >= 2
    assert validate(sample(target))["result"] == "passed"
    assert validate({}, target)["result"] == "failed"
    obj = sample(target)
    obj["unregistered_core_member"] = "合成字段"
    assert validate(obj)["result"] == "failed"


@pytest.mark.parametrize("target,prefix,count", [("Resource", "RES", 17), ("RightsRecord", "RGT", 9),
                                               ("CognitiveState", "COG", 16)])
def test_table_elements(target, prefix, count):
    properties = SCHEMAS[f"schema/objects/{target}.schema.json"]["allOf"][1]["properties"]
    elements = {e for field in properties.values() if isinstance(field, dict) for e in field.get("x-elements", [])}
    assert elements == {f"FLD-{prefix}-{i:03}" for i in range(1, count + 1)}


def test_method_table_and_mapping_assumption():
    elements = set()
    for target in ["MethodRegistration", "MethodApproval"]:
        schema = SCHEMAS[f"schema/objects/{target}.schema.json"]
        assert "H-24" in schema["x-assumption"]
        elements.update(e for node, _ in walk(schema) for e in node.get("x-elements", []) if e.startswith("FLD-MTH-"))
    assert elements == {f"FLD-MTH-{i:03}" for i in range(1, 15)}
    text = (ROOT / "临时假设.md").read_text()
    for i in range(1, 15):
        assert f"FLD-MTH-{i:03}" in text


def test_resource_rights_projection_boundaries():
    resource, rights = sample("Resource"), sample("RightsRecord")
    before = deepcopy((resource, rights))
    result = validate(resource)
    assert next(c for c in result["checks"] if c["check"] == "rights-projection")["result"] == "skipped"
    assert validate(resource, related_objects=[rights])["result"] == "passed"
    other_version = deepcopy(rights)
    other_version["version_id"] = "v2"
    other_version["contributors"][0]["contribution"] = "另一合成版本"
    result = validate(resource, related_objects=[other_version])
    assert result["result"] == "passed"
    assert next(c for c in result["checks"] if c["check"] == "rights-projection")["result"] == "skipped"
    assert "R-RELATED-001" in rules(validate(resource, related_objects=[{}]))
    assert "R-RELATED-001" in rules(validate(resource, related_objects=[None]))
    invalid_license = deepcopy(rights)
    invalid_license["license"]["identifier"] = "not-a-license"
    assert "R-RELATED-001" in rules(validate(resource, related_objects=[invalid_license]))
    assert (resource, rights) == before


@pytest.mark.parametrize("identifier,valid", [("MIT", True), ("Apache-2.0", True),
    ("school:example.edu:SYNTHETIC-1", True), ("school:", False), ("not-a-license", False),
    ("MIT OR Apache-2.0", False), ("LicenseRef-unregistered", False), ("", False)])
def test_license_identifiers(identifier, valid):
    obj = sample("RightsRecord")
    obj["license"]["identifier"] = identifier
    assert (validate(obj)["result"] == "passed") is valid
    if not valid:
        assert "R-LICENSE-001" in rules(validate(obj))


def test_embedded_record_reference_preserves_embedded_ref():
    owner = {"object_type": "CognitiveState", "object_id": "https://example.edu/cognitivestate/1"}
    ref = {"object_type": "EvidenceLink", "object_id": "https://example.edu/evidencelink/1", "owner_ref": owner}
    assert validate(ref, "EmbeddedInRecordRef")["result"] == "passed"
    assert validate(ref, "ObjectRef")["result"] == "passed"
    assert validate(ref, "EmbeddedRef")["result"] == "failed"
    obj = deepcopy(ref)
    del obj["owner_ref"]["object_type"]
    assert validate(obj, "EmbeddedInRecordRef")["result"] == "failed"
    obj = deepcopy(ref)
    obj["owner_ref"]["version_id"] = "v1"
    assert validate(obj, "EmbeddedInRecordRef")["result"] == "failed"


def test_hint_priority_and_original_reason():
    schema = {"type": "object", "x-rule-id": "R-TEST-001", "x-hint": "父层提示",
              "properties": {"name": {"type": "string", "minLength": 1, "x-hint": "填写非空合成名称"}}}
    instance = {"name": ""}
    errors = schema_errors(instance, schema)
    assert errors[0]["hint"] == "填写非空合成名称"
    assert errors[0]["reason"] == next(Draft202012Validator(schema).iter_errors(instance)).message
    assert errors[0]["rule_id"] == "R-TEST-001"
    obj = sample("CognitiveState")
    obj["value"] = 0
    errors = schema_errors(obj, SCHEMAS["schema/objects/CognitiveState.schema.json"])
    assert any(e["rule_id"] == "R-COG-002" and "显式" in e["hint"] for e in errors)


def test_cognitive_null_reasons_and_embedded_owner():
    obj = sample("CognitiveState")
    obj["missing_reasons"] = [r for r in obj["missing_reasons"] if r["pointer"] != "/uncertainty"]
    assert "R-COG-008" in rules(validate(obj))
    obj = load(ROOT / "fixtures/valid/CognitiveState/CognitiveState-estimated.json")["instance"]
    obj["evidence_links"][0]["owner_ref"]["object_id"] += "-other"
    obj["evidence_links"][0]["owner_ref"].pop("version_id", None)
    assert "R-EVIDENCELINK-002" in rules(validate(obj))


def test_source_identity_and_observation_method():
    obj = sample("ApplicationInstance")
    obj["source_instance"] = "https://example.edu/applicationinstance/other"
    assert "R-APPLICATIONINSTANCE-002" in rules(validate(obj))
    obj = sample("CognitiveState")
    obj["origin_type"] = "observation"
    del obj["method_ref"]
    assert "R-COG-009" in rules(validate(obj))
    obj["missing_reasons"].append({"pointer": "/method_ref", "reason": "not_applicable", "rule_id": "10.3.3"})
    assert validate(obj)["result"] == "passed"


@pytest.mark.parametrize("target", ["AccessGrant", "TeachingAssignment", "MethodApproval"])
def test_time_range(target):
    obj = sample(target)
    end = "ends_at" if target == "TeachingAssignment" else "valid_until"
    obj[end] = "2025-01-01T00:00:00Z"
    assert "R-TIME-002" in rules(validate(obj))


def test_related_cli():
    command = [sys.executable, str(ROOT / "tools/validate.py"),
               str(ROOT / "fixtures/invalid/Resource/Resource-contributors-mismatch.json")]
    result = subprocess.run(command, capture_output=True, text=True)
    assert result.returncode == 1, result.stderr
    assert "R-RESOURCE-004" in rules(json.loads(result.stdout))
    command = [sys.executable, str(ROOT / "tools/validate.py"),
               str(ROOT / "fixtures/valid/Resource/Resource-minimal.json"), "--related",
               str(ROOT / "fixtures/valid/RightsRecord/RightsRecord-minimal.json")]
    result = subprocess.run(command, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    assert "rights-projection" not in {c["check"] for c in json.loads(result.stdout)["checks"]}
