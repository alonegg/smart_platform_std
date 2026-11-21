"""Check draft fixture coverage and the boundaries of the public review draft."""
from __future__ import annotations

import csv
import json
import re
from pathlib import Path
from xml.etree import ElementTree
from zipfile import ZipFile

HERE = Path(__file__).resolve().parent
DOCUMENT = "智慧教学-数据模型标准"
WORD_NS = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def section(text: str, start: str, end: str) -> str:
    return text.split(start, 1)[1].split(end, 1)[0]


def check_document(current: str, internal: str) -> None:
    for first, last in (
        ("## 附录 A", "## 附录 B"),
        ("\n12.3.6 ", "### 12.4"),
        ("\n12.5.2 ", "\n12.5.3 "),
        ("## 附录 E", "### E.4 "),
    ):
        require(section(current, first, last) == section(internal, first, last),
                f"Unexpected requirement change between {first} and {last}")
    old_rows = [line for line in section(internal, "表 E.3 部分待决事项的可选方案", "\n\n\n").splitlines()
                if line.startswith("| E")]
    new_rows = [line for line in section(current, "表 E.3 部分待决事项的可选方案", "\n\n\n").splitlines()
                if line.startswith("| E")]
    require(len(old_rows) == len(new_rows) == 17, "E.3 must retain all options")
    require(old_rows == [re.sub(r"^\| E12[a-d]", "| E12", row) for row in new_rows],
            "E.3 grouping changed the original options")
    require(set(re.findall(r"^\| (E12[a-d])", "\n".join(new_rows), re.M))
            == {"E12a", "E12b", "E12c", "E12d"}, "Incomplete E12 grouping")


def check_word(path: Path, tables: int, markers: tuple[str, ...]) -> None:
    with ZipFile(path) as docx:
        root = ElementTree.fromstring(docx.read("word/document.xml"))
    words = "".join(node.text or "" for node in root.findall(".//w:t", WORD_NS))
    require(len(root.findall(".//w:tbl", WORD_NS)) == tables, f"{path.name}: table count")
    require(all(marker in words for marker in markers), f"{path.name}: missing source text")


def check_fixtures(document: str) -> int:
    payload = json.loads((HERE / "原子用例-draft.json").read_text(encoding="utf-8"))
    cases = payload["cases"]
    require(payload["status"] == "draft", "Fixtures must remain draft")
    require([row["id"] for row in cases] == [f"F{i:02d}" for i in range(1, len(cases) + 1)],
            "Fixture IDs must be consecutive and unique")
    require({row["clause"] for row in cases} == {f"12.3.6 {mark})" for mark in "abcdefghijklm"},
            "The case index must cover all 13 subclauses")
    parent_tests = set(re.findall(r"^\| (T\d{2}(?:-[A-Z])?)(?: |\s*\|)", document, re.M))
    for row in cases:
        require(set(row["parent_tests"]) <= parent_tests and bool(row["parent_tests"]),
                f"{row['id']}: unknown parent test")
        require(all(isinstance(row[key], dict) and bool(row[key]) for key in ("input", "expect")),
                f"{row['id']}: missing structured input or expected results")

    by_id = {row["id"]: row for row in cases}
    highest = by_id["F14"]
    scores = highest["input"]["confirmed"]
    selected = max(scores, key=scores.__getitem__)
    require(highest["expect"]["selected"] == selected, "F14: use confirmed scores")

    recon = by_id["F17"]
    outcome = recon["expect"]
    explained = [item for key in ("stored", "quarantined", "rejected", "pending")
                 for item in outcome[key]]
    require(len(explained) == len(set(explained)), "F17: outcomes must be disjoint")
    require(outcome["unexplained_gaps"] == len(set(outcome["expected"]) - set(explained)),
            "F17: unexplained gaps do not reconcile")
    require(outcome["retry_requests"] == len(recon["input"]["retry_requests"]),
            "F17: keep retries out of the submission denominator")

    late = by_id["F23"]["expect"]
    require(late["decision_status"] == "confirmed" and late["supersedes"] == "v1"
            and late["v2_registrar_status"] == "not_sent" and not late["late_receipt_advances_v2"]
            and late["platform_value"] - late["official_value"] == late["difference"],
            "F23: late receipt must not advance the corrected decision")
    for case, evidence, expected_state in (
        ("F39", None, "unknown"),
        ("F40", [], "unknown"),
        ("F41", [{"role": "inconclusive"}], "insufficient_evidence"),
    ):
        require(by_id[case]["input"]["evidence_links"] == evidence
                and by_id[case]["expect"]["estimate_status"] == expected_state
                and not by_id[case]["expect"]["definite_mastery"],
                f"{case}: inconsistent evidence semantics")
    return len(cases)


def main() -> None:
    current = (HERE / f"{DOCUMENT}.md").read_text(encoding="utf-8")
    internal = (HERE.parent / f"{DOCUMENT}-修订稿.md").read_text(encoding="utf-8")
    check_document(current, internal)
    with (HERE / "成员映射-draft.csv").open(encoding="utf-8", newline="") as handle:
        mapping = list(csv.DictReader(handle))
    require(bool(mapping) and all(None not in row and all(row.values()) and row["状态"] == "draft"
                                 for row in mapping), "Malformed draft field mapping")
    check_word(HERE / f"{DOCUMENT}.docx", 57,
               ("2026-11-21", "E12d", "差分查询", "两类跳过均不计为通过", "alone@swufe.edu.cn"))
    check_word(HERE / "评议意见表.docx", 2, ("2026-11-21", "alone@swufe.edu.cn"))
    count = check_fixtures(current)
    print(f"Checked 57 document tables, {len(mapping)} draft field mappings and {count} synthetic cases.")


if __name__ == "__main__":
    main()
