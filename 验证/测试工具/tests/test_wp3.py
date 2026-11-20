import hashlib
import json
from pathlib import Path
import subprocess
import sys
from threading import Thread
from zipfile import ZipFile

import pytest

from conformance import CONTRACT, ROOT
from conformance.context import Context
from conformance.package import safe
from conformance.profiles import select
from conformance.report import markdown
from conformance.runner import exit_code, run
from conformance.targets import HTTP, open_target
from conformance.validate_cmd import validate_path

PACKAGES = Path(__file__).parent / "fixtures/packages"


def test_trace():
    result = subprocess.run([sys.executable, str(ROOT / "tools/check_trace.py")], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr


@pytest.mark.parametrize("name,expected", [("valid", "passed"), ("bad-digest", "failed"), ("missing-file", "failed"), ("undeclared-file", "failed")])
@pytest.mark.parametrize("zipped", [False, True])
def test_packages(name, expected, zipped, tmp_path):
    path = PACKAGES / name
    if zipped:
        archive = tmp_path / "package.zip"
        with ZipFile(archive, "w") as z:
            for p in path.iterdir():
                z.write(p, p.name)
        path = archive
    result = validate_path(path)
    assert result["result"] == expected, result
    if expected == "passed":
        assert {c["check"] for c in result["checks"] if c["result"] == "skipped"} >= {"dependency-resolution", "deterministic-packaging", "independent-recovery"}


@pytest.mark.parametrize("name", ["../a", "/a", "a\\b", "a/../b", "a b"])
def test_unsafe(name, tmp_path):
    assert not safe(name)
    path = tmp_path / "unsafe.zip"
    with ZipFile(path, "w") as z:
        z.writestr(name, "x")
    assert validate_path(path)["result"] == "failed"


def test_json_and_errors(tmp_path):
    assert validate_path(CONTRACT / "fixtures/valid/event/event-submission.submitted.json")["result"] == "passed"
    assert validate_path(CONTRACT / "fixtures/invalid/event/event-T25-client-auth-context.json")["result"] == "failed"
    for value in ("{", "[]", "null"):
        p = tmp_path / "input.json"
        p.write_text(value)
        assert validate_path(p)["result"] == "failed"
    assert validate_path(tmp_path / "missing.json")["result"] == "failed"
    bad = tmp_path / "bad.zip"
    bad.write_text("not zip")
    assert validate_path(bad)["result"] == "failed"
    assert validate_path(tmp_path)["result"] == "failed"


def test_object_mismatch(tmp_path):
    import shutil
    shutil.copytree(PACKAGES / "valid", tmp_path / "package")
    path = tmp_path / "package/manifest.json"
    manifest = json.loads(path.read_text())
    manifest["objects"][0]["object_ref"]["version_id"] = "v2"
    path.write_text(json.dumps(manifest))
    assert validate_path(path.parent)["result"] == "failed"


def execute(target, profiles=("P-SUB",), cases=None, **kwargs):
    return run(target, "synthetic", "public-service", profiles, cases=cases, **kwargs)


def case(result, name):
    return next(c for c in result["cases"] if c["case_id"] == name)


def test_selection_and_statuses():
    assert "T05" not in select(["P-COM"])
    assert {"T08-P", "T08-R"} <= select(["P-GRD"])
    assert "T08-P" in select(["P-GRD", "P-AI"], ["C"])
    assert "T08-R" not in select(["P-GRD"], ["C"])
    assert "T18" in select(["P-COM"], triggers=["T18"])
    target = open_target("inproc:reference")
    try:
        result = execute(target, cases=["T05"])
        assert case(result, "T05")["status"] == "passed", case(result, "T05")
        assert case(result, "T01")["reason"] == "--cases 未选"
        assert case(result, "T09")["status"] == "not_applicable"
        assert result["overall"] == "incomplete" and exit_code(result) == 2
        assert case(execute(target, cases=[]), "T05")["reason"] == "--cases 未选"
        assert case(execute(target), "T13")["reason"] == "首批未实现该用例"
        assert "跳过不计为通过" in markdown(result)
        assert "未覆盖子场景" in markdown(result)
    finally:
        target.close()


def test_reference_repeat_and_isolation():
    target = open_target("inproc:reference")
    try:
        for _ in range(2):
            c = case(execute(target), "T05")
            assert c["status"] == "passed", c
            assert len(c["observations"]) == 5
        assert Context(target, "T05").prefix != Context(target, "T05").prefix
        ctx = Context(target, "T08-C")
        _, grant = ctx.setup()
        ctx.teaching_assignment(grant)
        _, service_grant = ctx.setup("client_credentials", "service")
        assert ctx.token(service_grant)
    finally:
        target.close()


def test_http():
    target = open_target("inproc:reference")
    from server import ReferenceHTTPServer
    server = ReferenceHTTPServer(("127.0.0.1", 0), target.service)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        url = f"http://127.0.0.1:{server.server_port}"
        result = execute(HTTP(url, target.admin_token), profiles=ALL_PROFILES, cases=FIRST_BATCH)
        for name in FIRST_BATCH:
            c = case(result, name)
            assert c["status"] == "passed", c
        assert case(execute(HTTP(url)), "T05")["status"] == "skipped"
        response = HTTP(url).call("get_receipt", "invalid", receipt_id="https://example.edu/missing/receipt")
        assert response["status"] == "rejected"
        assert HTTP(url).call("issue_token", "invalid", unexpected=True)["status"] == "rejected"
    finally:
        server.shutdown()
        server.server_close()
        thread.join()
        target.close()


def test_errors_and_overall():
    class Broken:
        admin_token = "synthetic-only"

        def call(self, *args, **kwargs):
            raise ValueError("malformed response")

    result = execute(Broken())
    assert result["overall"] == "failed" and exit_code(result) == 1
    assert case(result, "T05")["status"] == "failed"
    assert exit_code(execute(Broken(), profiles=[])) == 0
    for profiles, stages, triggers in [(["unknown"], ["P"], []), (["P-COM"], ["X"], []), (["P-COM"], [], ["T99"])]:
        with pytest.raises(ValueError):
            select(profiles, stages, triggers)
    with pytest.raises(ValueError):
        open_target("inproc:bad:not-registered")


def test_cli_reproducible_readonly(tmp_path):
    repo = ROOT.parents[1]
    tracked = subprocess.check_output(["git", "ls-files", "-z"], cwd=repo).split(b"\0")

    def snapshot():
        files = [repo / p.decode() for p in tracked if p]
        files += [p for p in ROOT.rglob("*") if p.is_file() and "__pycache__" not in p.parts and ".pytest_cache" not in p.parts]
        return {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in files}

    before = snapshot()
    command = [sys.executable, str(ROOT / "wp3.py"), "run", "--target", "inproc:reference", "--role", "public-service", "--profile", "P-SUB", "--json-out", str(tmp_path / "r.json"), "--report-out", str(tmp_path / "r.md")]
    outputs = []
    for _ in range(2):
        result = subprocess.run(command, capture_output=True, text=True)
        assert result.returncode == 2, result.stderr
        outputs.append(((tmp_path / "r.json").read_bytes(), (tmp_path / "r.md").read_bytes()))
    assert outputs[0] == outputs[1]
    assert snapshot() == before
    result = subprocess.run([sys.executable, str(ROOT / "wp3.py"), "validate", str(PACKAGES / "valid"), str(PACKAGES / "missing-file"), "--json"], capture_output=True, text=True)
    assert result.returncode == 1
    assert len(json.loads(result.stdout)["paths"]) == 2
    result = subprocess.run([sys.executable, str(ROOT / "wp3.py"), "list", "--json"], capture_output=True, text=True)
    assert result.returncode == 0 and len(json.loads(result.stdout)) >= 26


ALL_PROFILES = ["P-COM", "P-SUB", "P-GRD", "P-AI", "P-DIA"]
FIRST_BATCH = ["T01", "T05", "T06", "T07", "T08-P", "T08-C", "T08-A", "T08-R", "T09", "T10", "T11", "T23", "T25"]


@pytest.mark.parametrize("name", FIRST_BATCH)
def test_each_reference(name):
    target = open_target("inproc:reference")
    try:
        result = execute(target, profiles=ALL_PROFILES, cases=[name])
        row = case(result, name)
        assert row["status"] == "passed", row
        assert row["observations"] and all(o["status"] == "passed" for o in row["observations"])
    finally:
        target.close()


def test_container_aggregation():
    target = open_target("inproc:reference")
    try:
        result = execute(target, profiles=ALL_PROFILES, cases=FIRST_BATCH)
        assert case(result, "T08")["status"] == "passed"
        assert case(result, "T12")["status"] == "not_applicable"
        assert case(result, "T20")["status"] == "skipped"
        assert all(case(result, name)["container"] for name in ("T08", "T12", "T20"))
        assert sum(result["summary"]["cases"].values()) == len(result["cases"]) - 3
        assert result["summary"]["cases"]["passed"] == 13
        assert "父项按子用例聚合，不重复计数" in markdown(result)
        partial = execute(target, profiles=["P-GRD"], cases=["T08-P"])
        assert case(partial, "T08")["status"] == "skipped"
    finally:
        target.close()


def test_all_cases_target_errors():
    class Broken:
        admin_token = "synthetic-only"

        def call(self, *args, **kwargs):
            return {"status": "rejected"}

    result = execute(Broken(), profiles=ALL_PROFILES, cases=FIRST_BATCH)
    assert all(case(result, name)["status"] == "failed" for name in FIRST_BATCH)
    assert case(result, "T08")["status"] == "failed"
    missing_admin = HTTP("http://127.0.0.1:1")
    result = execute(missing_admin, profiles=ALL_PROFILES, cases=FIRST_BATCH)
    assert all(case(result, name)["status"] == "skipped" for name in FIRST_BATCH)


def test_t23_every_call_and_no_tokens():
    target = open_target("inproc:reference")
    try:
        result = execute(target, profiles=ALL_PROFILES, cases=["T23"])
        row = case(result, "T23")
        assert row["status"] == "passed", row
        attempts = [o for o in row["observations"] if "-direct-" in o["id"] or "-indirect-" in o["id"]]
        assert len(attempts) == 20
        assert all(json.loads(o["actual"])["rejected_audit_present"] for o in attempts)
        assert target.admin_token not in json.dumps(result)
    finally:
        target.close()
