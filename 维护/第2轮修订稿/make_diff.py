#!/usr/bin/env python3
"""生成修订稿相对于当前正文的逐条款差异（diff.md）。

用法（仓库根目录，Python 3.11+，仅标准库）：
    python3 -B 维护/第2轮修订稿/make_diff.py          # 重新生成 diff.md
    python3 -B 维护/第2轮修订稿/make_diff.py --check  # 只核对已提交的 diff.md 是最新的
差异按条款单元直接比较两份全文得出；修订编号与 Issue 取自《修订清单.txt》，仅用于标注。
"""
from __future__ import annotations

import difflib
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from build_revision import BASELINE, HERE, REVISED, load_ledger  # noqa: E402
from docmodel import parse_units, strip_blank  # noqa: E402

OUTPUT = HERE / "diff.md"


def quote(lines: list[str]) -> list[str]:
    out: list[str] = []
    for line in lines:
        out += [f"> {line}", ">"]
    return out[:-1] if out else out


def inline_notes(old: str, new: str) -> list[str]:
    """同一段落改写时，指出删去与增加的文字，便于核对未放宽原约束。"""
    matcher = difflib.SequenceMatcher(a=old, b=new, autojunk=False)
    deleted = [old[a0:a1] for op, a0, a1, _, _ in matcher.get_opcodes() if op in ("delete", "replace")]
    added = [new[b0:b1] for op, _, _, b0, b1 in matcher.get_opcodes() if op in ("insert", "replace")]
    notes = [f"- 段落“{old[:16]}…”删去的文字：" + ("；".join(f"“{x}”" for x in deleted) if deleted else "无（原文逐字保留）")]
    notes.append("- 增加的文字：" + "；".join(f"“{x}”" for x in added))
    return notes + [""]


def unit_of_clause(clause: str) -> str:
    """修订清单的 clause（如“5.1.3 a)”“11.4.7 f)”）对应的条款单元键。"""
    return clause.split(" ")[0]


def render() -> str:
    base = parse_units(BASELINE.read_text(encoding="utf-8"))
    rev = parse_units(REVISED.read_text(encoding="utf-8"))
    tags: dict[str, list[tuple[str, list[int]]]] = {}
    for r in load_ledger():
        for clause in r.clause.split("、"):
            tags.setdefault(unit_of_clause(clause.strip()), []).append((r.rid, r.issues))

    def tag_of(key: str) -> list[tuple[str, list[int]]]:
        if key in tags:
            return tags[key]
        parent = key.rsplit(".", 1)[0]
        return tags.get(parent, []) if parent != key else []

    def label(key: str) -> tuple[str, str]:
        found = tag_of(key)
        rids = "、".join(rid for rid, _ in found) or "—"
        issues = "、".join(f"#{n}" for n in sorted({n for _, ns in found for n in ns})) or "—"
        return rids, issues

    changed: list[tuple[str, str]] = []
    for key in rev:
        if key not in base:
            changed.append((key, "新增"))
        elif strip_blank(base[key]) != strip_blank(rev[key]):
            changed.append((key, "修改"))
    removed = [key for key in base if key not in rev]

    out = [
        "# 修订稿相对于当前正文的逐条款差异",
        "",
        "本文件由 `make_diff.py` 生成，请勿手工编辑。比较对象：",
        "",
        f"- 当前正文：`{BASELINE.relative_to(HERE.parents[1])}`",
        f"- 修订稿：`{REVISED.relative_to(HERE.parents[1])}`",
        "",
        f"共 {len(changed)} 个条款单元有差异：新增 {sum(1 for _, k in changed if k == '新增')} 个，"
        f"修改 {sum(1 for _, k in changed if k == '修改')} 个，删除 {len(removed)} 个。"
        "“修改”单元内只列出有变化的段落：`-` 为当前正文，`+` 为修订稿；未列出的段落逐字未变。",
        "",
        "| 条款 | 类型 | 修订编号 | Issue |",
        "|---|---|---|---|",
    ]
    for key, kind in changed:
        rids, issues = label(key)
        out.append(f"| {key} | {kind} | {rids} | {issues} |")
    for key in removed:
        out.append(f"| {key} | 删除 | — | — |")
    out.append("")

    for key, kind in changed:
        rids, _ = label(key)
        out += [f"## {key}（{kind}；{rids}）", ""]
        new_lines = strip_blank(rev[key])
        if kind == "新增":
            out += quote(new_lines) + [""]
            continue
        old_lines = strip_blank(base[key])
        matcher = difflib.SequenceMatcher(a=old_lines, b=new_lines, autojunk=False)
        out.append("```diff")
        for op, a0, a1, b0, b1 in matcher.get_opcodes():
            if op == "equal":
                continue
            out += [f"- {line}" for line in old_lines[a0:a1]]
            out += [f"+ {line}" for line in new_lines[b0:b1]]
        out += ["```", ""]
        for op, a0, a1, b0, b1 in matcher.get_opcodes():
            if op == "replace" and a1 - a0 == 1 and b1 - b0 >= 1:
                out += inline_notes(old_lines[a0], new_lines[b0])
    for key in removed:
        out += [f"## {key}（删除）", "", "```diff"] + [f"- {l}" for l in strip_blank(base[key])] + ["```", ""]
    return "\n".join(out)


def main() -> int:
    text = render()
    if "--check" in sys.argv[1:]:
        if not OUTPUT.exists() or OUTPUT.read_text(encoding="utf-8") != text:
            print("diff.md 不是最新的，请重新运行 make_diff.py", file=sys.stderr)
            return 1
        print("diff.md 为最新")
        return 0
    OUTPUT.write_text(text, encoding="utf-8")
    print(f"已生成 {OUTPUT.relative_to(HERE.parents[1])}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
