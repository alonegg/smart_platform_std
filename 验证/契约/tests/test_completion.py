from collections import Counter
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys

import pytest

from check_trace import check_trace
from validate import ROOT, load, validate


EVENTS = [e["event_type"] for e in load(ROOT / "vocab/event_types.json")["values"]]


def errors(result):
    return {e["rule_id"] for c in result["checks"] if c["result"] == "failed" for e in c["errors"]}


def sample(target):
    return load(ROOT / f"fixtures/valid/{target}/{target}-minimal.json")["instance"]


@pytest.mark.parametrize("event", EVENTS)
def test_complete_event_contract(event):
    definition = load(ROOT / f"events/{event}.json")
    fixtures = [load(p) for p in (ROOT / "fixtures").glob("*/event/*.json")]
    counts = Counter(f["fixture"]["expect"] for f in fixtures if f["instance"].get("event_type") == event)
    assert counts["valid"] >= 1 and counts["invalid"] >= 2
    for key in ["meaning", "preconditions", "time_semantics", "withdrawal_semantics", "statistics_effect", "relationships", "source_members", "examples"]:
        assert definition[key]
    fixture = load(ROOT / f"fixtures/valid/event/event-{event}.json")
    result = validate(fixture)
    assert result["result"] == "passed", result
    assert next(c for c in result["checks"] if c["check"] == "event-definition")["result"] == "passed"
    assert validate({"event_type": event}, "event")["result"] == "failed"


@pytest.mark.parametrize("event", ["grade.confirmed", "grade.corrected", "grade.archived"])
@pytest.mark.parametrize("actor", ["ai_service", "rule_engine", "learner"])
def test_ai_confirmation_correction_archive_boundary(event, actor):
    obj = load(ROOT / f"fixtures/valid/event/event-{event}.json")["instance"]
    obj["actor_type"] = actor
    assert validate(obj)["result"] == "failed"


def test_unknown_event_is_failure_not_skipped():
    result = validate({"event_type": "unregistered.event"})
    assert "R-EVENT-DEF-001" in errors(result)
    assert not any(c["check"] == "event-definition" and c["result"] == "skipped" for c in result["checks"])


@pytest.mark.parametrize("stage", ["stored", "exchange"])
def test_confirmation_rejects_client_credentials_in_received_views(stage):
    obj = load(ROOT / "fixtures/valid/event/event-grade.confirmed.json")["instance"]
    obj.update(event_id="synthetic-event", received_at="2026-01-01T00:00:01Z", payload_hash="a" * 64,
               auth_context={"client_id": "https://example.edu/app/1",
                             "grant_ref": {"object_type": "AccessGrant", "object_id": "https://example.edu/grant/1", "version_id": "v1"},
                             "credential_digest": "a" * 64, "access_mode": "client_credentials"})
    assert "R-AI-003" in errors(validate(obj, "event", stage))


@pytest.mark.parametrize("target", ["manifest", "receipt", "export-receipt"])
def test_exchange_targets(target):
    obj = sample(target)
    assert validate(obj)["result"] == "passed"
    assert validate({}, target)["result"] == "failed"
    counts = Counter(load(p)["fixture"]["expect"] for p in (ROOT / "fixtures").glob(f"*/{target}/*.json"))
    assert counts["valid"] >= 1 and counts["invalid"] >= 2


def test_manifest_conditions_and_file_inventory():
    obj = sample("manifest")
    obj["package_type"] = "archive"
    assert {"R-MAN-002", "R-MAN-003", "R-MAN-005"} <= errors(validate(obj))
    obj["export_receipt_id"] = "synthetic-receipt"
    obj["portability_level"] = "independently_restorable"
    obj["content_inclusions"]["state_records"] = "all"
    assert validate(obj)["result"] == "passed"
    entry = {"path": "objects/Resource/1/v1.json", "sha256": "a" * 64, "byte_length": 0, "media_type": "application/json"}
    obj["files"] = [entry, entry]
    assert "R-MAN-006" in errors(validate(obj))
    obj["files"] = [{**entry, "path": "../outside"}]
    assert validate(obj)["result"] == "failed"


def test_receipt_durability_and_duplicate():
    obj = sample("receipt")
    obj["completed_stages"].append("school_registered")
    assert "R-RCP-005" in errors(validate(obj))
    obj = sample("receipt")
    obj["status"] = "duplicate"
    assert "R-RCP-003" in errors(validate(obj))
    obj.update(original_receipt_id="original", original_status="accepted", current_status="accepted")
    assert validate(obj)["result"] == "passed"
    obj["status"] = "rejected"
    assert "R-RCP-004" in errors(validate(obj))


def test_export_receipt_authorizations():
    obj = sample("export-receipt")
    obj["authorization_refs"][0]["version_id"] = "v2"
    assert "R-EXR-002" in errors(validate(obj))


def test_trace():
    result = check_trace()
    assert result["result"] == "passed", result


@pytest.mark.parametrize("corruption", ["scope", "file", "clause", "element", "empty", "scope-reason"])
def test_trace_rejects_corruption(tmp_path, corruption):
    root = tmp_path / "contracts"
    shutil.copytree(ROOT, root, ignore=shutil.ignore_patterns("__pycache__", ".pytest_cache"))
    if corruption == "scope":
        path = root / "scope.json"
        obj = load(path)
        obj["element_ids"].pop()
        path.write_text(json.dumps(obj))
    elif corruption in ["file", "scope-reason"]:
        path = root / "追溯表.csv"
        text = path.read_text()
        if corruption == "file":
            text = text.replace("验证/契约/schema/common.schema.json", "验证/契约/schema/missing.schema.json")
        else:
            text = text.replace("首批仅引用该依赖类型，不实现其独立对象Schema。", "")
        path.write_text(text)
    else:
        path = root / "fixtures/valid/Person/Person-minimal.json"
        obj = load(path)
        obj["fixture"]["clauses" if corruption == "clause" else "elements"] = ["99.99"] if corruption == "clause" else [] if corruption == "empty" else ["OBJ-999"]
        path.write_text(json.dumps(obj))
    assert check_trace(root=root)["result"] == "failed"


def test_rerun_keeps_git_status_and_files_unchanged():
    repo = ROOT.parents[1]
    status = lambda: subprocess.check_output(["git", "status", "--porcelain=v1", "--untracked-files=all"], cwd=repo)
    hashes = lambda: {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
                      for p in ROOT.rglob("*") if p.is_file() and not {"__pycache__", ".pytest_cache"} & set(p.parts)}
    before, contents = status(), hashes()
    for _ in range(2):
        result = subprocess.run([sys.executable, str(ROOT / "tools/check_trace.py")], capture_output=True, text=True)
        assert result.returncode == 0, result.stdout + result.stderr
        result = subprocess.run([sys.executable, str(ROOT / "tools/validate.py"), str(ROOT / "fixtures/valid/manifest/manifest-minimal.json")], capture_output=True, text=True)
        assert result.returncode == 0, result.stdout + result.stderr
    assert hashes() == contents
    assert status() == before
