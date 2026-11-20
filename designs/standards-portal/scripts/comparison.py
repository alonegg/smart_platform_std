"""Reuse the revision checker’s clause units and ledger; emit build-only data."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "维护/第2轮修订稿"))
from build_revision import BASELINE, REVISED, load_ledger
from docmodel import parse_units, strip_blank
from make_diff import unit_of_clause

base = parse_units(BASELINE.read_text())
revised = parse_units(REVISED.read_text())
tags = {}
for entry in load_ledger():
    for clause in entry.clause.split("、"):
        tags.setdefault(unit_of_clause(clause.strip()), []).append(entry)

rows = []
for key in dict.fromkeys([*revised, *base]):
    before = "\n".join(strip_blank(base.get(key, [])))
    after = "\n".join(strip_blank(revised.get(key, [])))
    entries = tags.get(key, tags.get(key.rsplit(".", 1)[0], []))
    changed = before != after
    if changed and not entries:
        raise ValueError(f"No revision ledger entry for {key}")
    rows.append({"clause": key, "before": before, "after": after,
                 "kind": "未改动" if not changed else "新增" if not before else "删除" if not after else "修改",
                 "revisions": sorted({e.rid for e in entries}) if changed else [],
                 "issues": sorted({n for e in entries for n in e.issues}) if changed else []})
print(json.dumps(rows, ensure_ascii=False))
