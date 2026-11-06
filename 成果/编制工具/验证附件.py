"""Check authored artifacts and synthetic examples, not production systems."""

from __future__ import annotations

import copy
import csv
import hashlib
import json
import logging
import re
import zipfile
from pathlib import Path
from typing import Any

from pypdf import PdfReader

ROOT = Path(__file__).resolve().parents[1]
LOG = logging.getLogger(__name__)


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def validate_sample(value: dict[str, Any]) -> None:
    objects = value["objects"]
    ids = {(item["object_id"], item["version_id"]) for item in objects}
    if len(ids) != len(objects):
        raise ValueError("duplicate_object")

    def walk(item: Any) -> None:
        if isinstance(item, dict):
            if set(item) == {"object_id", "version_id"}:
                if (item["object_id"], item["version_id"]) not in ids:
                    raise ValueError("missing_reference")
            for sub in item.values():
                walk(sub)
        elif isinstance(item, list):
            for sub in item:
                walk(sub)

    walk(value)
    for item in objects:
        if item["object_type"] != "CognitiveState":
            continue
        if item["status"] in {"unknown", "insufficient_evidence"} and item["value"] is not None:
            raise ValueError("unknown_has_value")
        if item["status"] in {"estimated", "reviewed"}:
            if not item["evidence_refs"]:
                raise ValueError("estimate_without_evidence")
            if not item["method_ref"] or not item["scale_ref"]:
                raise ValueError("estimate_without_method_or_scale")


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    checks: list[dict[str, Any]] = []

    def check(name: str, ok: bool, detail: Any = None) -> None:
        checks.append({"name": name, "passed": ok, "detail": detail})
        if not ok:
            raise ValueError(name)

    sample = read_json(ROOT / "样例" / "三类数据关联示例.json")
    validate_sample(sample)
    check("synthetic_reference_chain", True, len(sample["objects"]))
    for case, expected in (("missing_ref", "missing_reference"), ("unknown_value", "unknown_has_value"), ("no_evidence", "estimate_without_evidence"), ("duplicate", "duplicate_object")):
        modified = copy.deepcopy(sample)
        if case == "missing_ref":
            modified["objects"][0]["unit_refs"][0]["object_id"] = "missing"
        elif case == "unknown_value":
            next(x for x in modified["objects"] if x["object_id"] == "state-unknown")["value"] = 0.9
        elif case == "no_evidence":
            next(x for x in modified["objects"] if x["object_id"] == "state-demo")["evidence_refs"] = []
        else:
            modified["objects"].append(copy.deepcopy(modified["objects"][0]))
        caught = ""
        try:
            validate_sample(modified)
        except ValueError as exc:
            caught = str(exc)
        check("negative_" + case, caught == expected, caught)

    pack = ROOT / "样例" / "教学复用包"
    manifest = read_json(pack / "manifest.json")
    check("manifest_unique_paths", len({x["path"] for x in manifest["files"]}) == len(manifest["files"]))
    for record in manifest["files"]:
        content = (pack / record["path"]).read_bytes()
        check("package_file_" + record["path"], len(content) == record["byte_length"] and hashlib.sha256(content).hexdigest() == record["sha256"])
    teaching_text = "\n".join(p.read_text(encoding="utf-8") for p in pack.rglob("*") if p.is_file())
    check("teaching_sample_no_personal_history", not any(key in teaching_text for key in ('"learner_ref"', '"evidence_refs"', '"CognitiveState"', '"correct_answer"')))
    event = sample["events"][0]
    core = {key: val for key, val in event.items() if key not in {"received_at", "payload_hash"}}
    check("event_hash", hashlib.sha256(json.dumps(core, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode()).hexdigest() == event["payload_hash"])
    initial_path = ROOT.parent / "temp" / "原始文件哈希.json"
    originals = read_json(ROOT / "附件" / "原始文件核验.json")
    for record in originals:
        file = ROOT.parent / "原始文档" / record["file"]
        check("original_unchanged_" + file.suffix, hashlib.sha256(file.read_bytes()).hexdigest() == record["sha256"])
    if initial_path.exists():
        check("originals_match_initial_snapshot", {x["file"]: x["sha256"] for x in read_json(initial_path)} == {x["file"]: x["sha256"] for x in originals})
    docs = list(ROOT.glob("0*.md"))
    text = "\n".join(p.read_text(encoding="utf-8") for p in docs)
    forbidden = re.findall(r"合同编号|合同金额|付款|履约|采购金额", text)
    check("neutral_scope", not forbidden, forbidden)
    standard_text = (ROOT / "02_数据资产层标准体系草案.md").read_text(encoding="utf-8")
    clauses = re.findall(r"^### (S\d-\d+)", standard_text, re.M)
    check("unique_clause_ids", len(clauses) == len(set(clauses)), len(clauses))
    check("eight_standard_groups", {x.split("-")[0] for x in clauses} == {"S" + str(i) for i in range(8)})
    for file in (ROOT / "附件").glob("*.csv"):
        with file.open(encoding="utf-8-sig", newline="") as handle:
            rows = list(csv.reader(handle))
        check("csv_" + file.name, len(rows) > 1 and all(len(row) == len(rows[0]) for row in rows), len(rows) - 1)
    pdfs = []
    for file in ROOT.glob("*.pdf"):
        reader = PdfReader(file)
        page_texts = [page.extract_text() or "" for page in reader.pages]
        check("pdf_nonempty_" + file.name, all(len(re.sub(r"\s", "", page)) > 45 for page in page_texts), len(page_texts))
        pdfs.append({"file": file.name, "pages": len(reader.pages), "page_text_lengths": [len(x) for x in page_texts]})
        all_text = "\n".join(page_texts)
        check("pdf_no_forbidden_context_" + file.name, not re.search(r"合同编号|合同金额|付款|履约|采购金额", all_text))
    for file in ROOT.glob("*.docx"):
        with zipfile.ZipFile(file) as archive:
            check("docx_zip_" + file.name, archive.testzip() is None)
            xml = archive.read("word/document.xml").decode()
            check("docx_has_image_" + file.name, "<w:drawing>" in xml)
    result = {"scope": "document_and_synthetic_sample_checks_only", "real_interoperability_tests_run": False, "cognition_validity_tested": False, "checks": checks, "all_passed": all(x["passed"] for x in checks), "pdfs": pdfs}
    output = ROOT / "验证"
    output.mkdir(exist_ok=True)
    (output / "结构与样例核验.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    LOG.info("Passed %s authored-artifact checks; PDFs: %s", len(checks), pdfs)


if __name__ == "__main__":
    main()
