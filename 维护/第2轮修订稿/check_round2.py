#!/usr/bin/env python3
"""第 2 轮修订稿检查：Issue 全覆盖、条款号与交叉引用有效、既有约束与待决事项未被删改。

用法（仓库根目录，Python 3.11+，仅标准库）：
    python3 -B 维护/第2轮修订稿/check_round2.py            # 离线检查
    python3 -B 维护/第2轮修订稿/check_round2.py --online   # 另用 gh 核对 Issue 存在且标题一致
    MARKED_DIR=<marked 安装目录> python3 -B 维护/第2轮修订稿/check_round2.py --marked   # 用网站锁定版本的 Marked 实际解析表格
    python3 -B 维护/第2轮修订稿/check_round2.py --no-git   # 无 git 历史时跳过受保护目录检查
只读运行，不改写任何文件；任何一项失败时退出码为 1。
"""
from __future__ import annotations

import difflib
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import build_revision  # noqa: E402
import make_diff  # noqa: E402
from build_revision import BASELINE, HERE, REVISED, ROOT, load_ledger  # noqa: E402
from docmodel import ITEM_RE, items_of, parse_units, strip_blank, table_captions  # noqa: E402

NOTES = HERE / "修订说明.md"
EXPECTED_ISSUES = list(range(39, 48)) + list(range(57, 77))
DISPOSITIONS = ("采纳", "部分采纳", "不采纳", "需学校或标准维护机构裁定")
PROTECTED_DIRS = ("标准", "designs", "archive")
# 计划点名的六项待决事项：只能给建议方案，表 E.1/E.2 中的行不得改动。
BLOCKING_PENDING = ("E12", "E13", "E14", "E22", "E23a", "E26")
# 改写了原句的替换（其余替换必须逐字保留原文）：修订编号 -> 改写后仍须出现的原约束片段。
REWRITTEN = {
    "R02": ("独立版本化目标还应包含非空字符串 `version_id`", "随所属版本固定的目标还应包含 `owner_ref`",
            "指向所属对象具体版本的 ObjectRef", "`object_id` 均取目标在所属对象内的局部标识，不携带目标自身的 `version_id`",
            "不可变记录目标只需 `object_id`，携带 `version_id` 时应与 `object_id` 相同", "非版本化目标不应携带 `version_id`"),
    "R27": ("`not_sent`（未送）、`sent`（已送待回执）、`accepted`（教务已接收）、`rejected`（教务拒收）、`quarantined`（教务隔离待处置）",
            "教务归档回执确定", "属于 5.6.9 的派生状态，按 5.6.9 承载，不写入 GradeDecision 记录"),
    "R07": ("随所属 Resource 版本固定（见 5.1.8）", "`start_ms`、`end_ms`", "0 ≤ start_ms < end_ms ≤ 源时长",
            "关联字幕及目标", "按 5.1.3 a) 以 `owner_ref` 指向所属资源版本"),
}
# 修订稿正文不得出现的追溯性内容（AGENTS.md）；允许数为当前正文中已有的次数。
FORBIDDEN = (r"Issue", r"#\d+", r"WP\d", r"\bH-\d{2}\b", r"\bS-\d{2}\b", r"W3-\d", r"第\s*2\s*轮", r"修订稿",
             r"修订说明", r"修订清单", r"\bPR\b", r"审查方", r"问题解决委员会")
CLAUSE_TOKEN_RE = re.compile(r"(?<![\w.\-/—])(\d{1,2}(?:\.\d{1,2}){1,3})(?![\w]|\.\d)")
APPENDIX_TOKEN_RE = re.compile(r"(?<![\w.\-/])(?<!表 )([A-E]\.\d{1,2}(?:\.\d{1,2})?)(?![\w]|\.\d)")
ITEM_REF_RE = re.compile(r"(\d{1,2}(?:\.\d{1,2}){1,3}) ([a-z])\)")
TABLE_REF_RE = re.compile(r"表 (\d{1,2}-\d{1,2}|[A-E]\.\d{1,2})")
PENDING_RE = re.compile(r"(?<![\w-])(E\d{2}[abc]?)(?![\w])")
CASE_RE = re.compile(r"(?<![\w-])(T\d{2}(?:-[A-Z])?)(?![\w])")
EXTERNAL_RE = re.compile(r"(?<![\w])(B-[ID]\d{2}[a-z]?)(?!\d)")

failures: list[str] = []
notes: list[str] = []


def check(ok: bool, message: str) -> None:
    if not ok:
        failures.append(message)


class Doc:
    def __init__(self, text: str) -> None:
        self.text = text
        self.lines = text.split("\n")
        self.units = parse_units(text)
        self.tables = table_captions(text)
        self.pending = set(re.findall(r"^\| (E\d{2}[abc]?) ", text, re.M))
        self.cases = set(re.findall(r"^\| (T\d{2}(?:-[A-Z])?) ", text, re.M))
        self.external = set(re.findall(r"^\| (B-[ID]\d{2}[a-z]?) ", text, re.M))

    def resolves(self, token: str) -> bool:
        return token in self.units

    def unresolved(self) -> dict[str, list[str]]:
        text = self.text
        out: dict[str, list[str]] = {}
        out["条款"] = sorted(t for t in CLAUSE_TOKEN_RE.findall(text) if not self.resolves(t))
        out["附录条款"] = sorted(t for t in APPENDIX_TOKEN_RE.findall(text) if not self.resolves(t))
        out["表"] = sorted(t for t in TABLE_REF_RE.findall(text) if f"表 {t}" not in self.tables)
        out["待决事项"] = sorted(t for t in PENDING_RE.findall(text) if t not in self.pending)
        out["测试用例"] = sorted(t for t in CASE_RE.findall(text) if t not in self.cases)
        out["外部标准登记号"] = sorted(t for t in EXTERNAL_RE.findall(text) if t not in self.external)
        out["列项"] = sorted(f"{c} {i})" for c, i in ITEM_REF_RE.findall(text)
                           if c in self.units and i not in items_of(self.units[c]))
        return out


def git(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["git", "-C", str(ROOT), *args], capture_output=True, text=True)


def check_protected_dirs() -> None:
    if "--no-git" in sys.argv:
        notes.append("已按 --no-git 跳过受保护目录检查")
        return
    base = None
    for ref in ("origin/main", "main"):
        found = git("merge-base", "HEAD", ref)
        if found.returncode == 0:
            base = found.stdout.strip()
            break
    if base is None:
        check(False, "无法确定与 main 的分叉点，不能核对受保护目录（可用 --no-git 跳过）")
        return
    changed = git("diff", "--name-only", base, "--", *PROTECTED_DIRS).stdout.split("\n")
    dirty = git("status", "--porcelain", "--", *PROTECTED_DIRS).stdout.split("\n")
    touched = sorted({x.strip() for x in changed + dirty if x.strip()})
    check(not touched, f"受保护目录相对 main 有改动：{touched}")


def check_build(ledger) -> None:
    built = build_revision.apply(BASELINE.read_text(encoding="utf-8"), ledger)
    check(REVISED.read_text(encoding="utf-8") == built, "修订稿与“当前正文 + 修订清单”不一致")
    check((HERE / "diff.md").read_text(encoding="utf-8") == make_diff.render(), "diff.md 不是最新的")


def check_preservation(base: Doc, rev: Doc, ledger) -> None:
    """当前正文除声明替换的行外逐行保留；替换行不丢原约束。"""
    replaced = {}
    for r in ledger:
        if r.op == "replace":
            hit = [line for line in base.lines if line.startswith(r.anchor)]
            replaced[hit[0]] = r
    lost: list[str] = []
    matcher = difflib.SequenceMatcher(a=base.lines, b=rev.lines, autojunk=False)
    for op, a0, a1, _, _ in matcher.get_opcodes():
        if op in ("delete", "replace"):
            lost += [line for line in base.lines[a0:a1] if line.strip()]
    undeclared = [line[:40] for line in lost if line not in replaced]
    check(not undeclared, f"当前正文有未声明的行被删除或改写：{undeclared}")
    check(sorted(lost) == sorted(replaced), "声明替换的行与实际被替换的行不一致")
    for old, r in replaced.items():
        new_first = r.paragraphs[0]
        if r.rid in REWRITTEN:
            missing = [frag for frag in REWRITTEN[r.rid] if frag not in r.text]
            check(not missing, f"{r.rid}: 改写后缺少原约束片段 {missing}")
        else:
            stem = old.rstrip("；。")
            check(new_first.startswith(stem), f"{r.rid}: 替换未逐字保留原文（如确需改写，应登记到 REWRITTEN 并说明）")
    check(set(REWRITTEN) <= {r.rid for r in ledger if r.op == "replace"}, "REWRITTEN 含不存在的替换编号")


def check_protected_blocks(base: Doc, rev: Doc) -> None:
    """附录 A、表 12-1—12-5、表 E.1、表 E.2 逐字未改；待决事项行一条不少。"""
    for key, lines in base.units.items():
        protected = (key.startswith("A.") or key.startswith("附录 A") or key.startswith("附录 E")
                     or key in ("E.1", "E.2", "E.2.1", "E.2.2", "E.3")
                     or key in ("12.3.1", "12.3.2", "12.3.3", "12.3.4"))
        if protected:
            check(rev.units.get(key) == lines, f"受保护单元 {key} 与当前正文不一致")
    table_125 = [line for line in base.units["12.3.5"] if line.startswith("|")]
    check(table_125 == [line for line in rev.units["12.3.5"] if line.startswith("|")], "表 12-5 被改动")
    for doc, name in ((base, "当前正文"), (rev, "修订稿")):
        ids = [f"E{n:02d}" for n in range(1, 31)] + ["E23a", "E23b", "E23c"]
        check(all(i in doc.pending for i in ids), f"{name} 的待决事项清单不完整")
    for pid in BLOCKING_PENDING:
        def row(d: Doc) -> list[str]:  # 只取表 E.1、表 E.2 所在单元，不含表 E.3 的建议方案行
            return [line for key in ("E.1", "E.3") for line in d.units[key] if line.startswith(f"| {pid} ")]

        check(row(base) == row(rev) and len(row(base)) == 1, f"{pid} 在表 E.1/E.2 中的行被改动")
    for row_line in [line for line in rev.lines if re.match(r"^\| P-[A-Z]{3} \| T\d{2}", line)]:
        cell = re.sub(r"（[^）]*）", "", row_line.split("|")[2]).strip()
        bad = [x for x in cell.split("、") if not re.fullmatch(r"T\d{2}(-[A-Z])?", x.strip())]
        check(not bad, f"表 A.9 用例列分隔符异常：{row_line[:12]} {bad}")


def numbering_gaps(doc: Doc) -> list[str]:
    """同一上级之下，条款号应从 1 起连续且不重复。"""
    problems = [key for key in doc.units if key.endswith("（重复）")]
    groups: dict[str, list[int]] = {}
    for key in doc.units:
        if re.fullmatch(r"\d{1,2}(\.\d{1,2}){1,3}|[A-E]\.\d{1,2}(\.\d{1,2})?", key):
            parent, last = key.rsplit(".", 1)
            groups.setdefault(parent, []).append(int(last))
    for parent, numbers in groups.items():
        start = numbers[0]
        if parent in ("0",):  # 引言 0.1 起
            start = 1
        if start not in (0, 1) or numbers != list(range(start, start + len(numbers))):
            problems.append(f"{parent}.x 编号不连续：{numbers}")
    return problems


def check_numbering(base: Doc, rev: Doc) -> None:
    before, after = set(numbering_gaps(base)), numbering_gaps(rev)
    new = [p for p in after if p not in before]
    check(not new, f"修订稿新增条款编号问题：{new}")
    if before:
        notes.append(f"当前正文既有的编号现象（未处理）：{sorted(before)}")
    check(len(rev.tables) == len(set(rev.tables)), "修订稿有重复的表编号")


def check_clause_groups(rev: Doc) -> None:
    """A.3.1：第 5—12 章每一节归入且仅归入表 A.3 的一个条款组。"""
    covered: dict[str, int] = {}
    for line in rev.units["A.3.2"]:
        cells = [c.strip() for c in line.split("|")]
        if len(cells) < 5 or not re.fullmatch(r"\d{1,2}-[A-E]", cells[1]):
            continue
        for part in cells[3].split("、"):
            if "—" in part:
                lo, hi = part.split("—")
                chapter = lo.split(".")[0]
                for n in range(int(lo.split(".")[1]), int(hi.split(".")[1]) + 1):
                    covered[f"{chapter}.{n}"] = covered.get(f"{chapter}.{n}", 0) + 1
            else:
                covered[part] = covered.get(part, 0) + 1
    check(bool(covered), "未能解析表 A.3")
    sections = [k for k in rev.units if re.fullmatch(r"(?:[5-9]|1[0-2])\.\d{1,2}", k)]
    for section in sections:
        check(covered.get(section, 0) == 1, f"{section} 节未归入或重复归入表 A.3 的条款组")
    for key in rev.units:
        if re.fullmatch(r"(?:[5-9]|1[0-2])(\.\d{1,2}){2}", key):
            check(key.rsplit(".", 1)[0] in sections, f"条款 {key} 不在任何已编号的节内")


def check_references(base: Doc, rev: Doc, ledger) -> None:
    before, after = base.unresolved(), rev.unresolved()
    for kind in after:
        remaining = list(after[kind])
        for token in before[kind]:
            if token in remaining:
                remaining.remove(token)
        check(not remaining, f"修订稿新增不可解析的{kind}引用：{sorted(set(remaining))}")
        if before[kind]:
            notes.append(f"当前正文既有、无法按条款解析的{kind}记号（多为外部规范版本号，未处理）："
                         f"{sorted(set(before[kind]))}")
    new_text = Doc("\n".join(r.text for r in ledger))
    new_text.units, new_text.tables = rev.units, rev.tables
    new_text.pending, new_text.cases, new_text.external = rev.pending, rev.cases, rev.external
    for kind, tokens in new_text.unresolved().items():
        check(not tokens, f"新增文字中有不可解析的{kind}引用：{sorted(set(tokens))}")
    for r in ledger:
        for pid in r.pending:
            check(pid in rev.pending, f"{r.rid}: pending 中的 {pid} 不在待决事项清单")
            check(pid in r.text, f"{r.rid}: 声明涉及 {pid}，但新文未注明该待决事项")
        mentioned = set(PENDING_RE.findall(r.text))
        check(mentioned <= set(r.pending), f"{r.rid}: 新文提到 {sorted(mentioned - set(r.pending))}，但 pending 未登记")


def check_content_rules(base: Doc, rev: Doc, ledger) -> None:
    for pattern in FORBIDDEN:
        allowed = len(re.findall(pattern, base.text))
        found = len(re.findall(pattern, rev.text))
        check(found <= allowed, f"修订稿正文出现追溯性内容 /{pattern}/ {found} 处（当前正文 {allowed} 处）")
    for r in ledger:
        values = re.findall(r"\d+(?:\.\d+)?\s*(?:秒|分钟|小时|个工作日|天|%|％)", r.text)
        extra = [v for v in values if v != "5%"]
        check(not extra, f"{r.rid}: 新文含未经审定的时限或阈值 {extra}")
    e4 = "\n".join(rev.units.get("E.4.1", []))
    check("不构成决定" in e4 and "仍按表 E.1" in e4, "E.4.1 未声明建议方案不构成决定")
    for pid in BLOCKING_PENDING:
        rows = [line for line in rev.units.get("E.4.1", []) if line.startswith("| ") and pid in line.split("|")[1]]
        check(len(rows) >= 1, f"表 E.3 缺少 {pid} 的可选方案行")
    check(not re.search(r"推荐|建议方案|起草方", e4), "表 E.3 应中立列出可选方案，不写入推荐意见")


def check_issue_coverage(rev: Doc, ledger) -> None:
    text = NOTES.read_text(encoding="utf-8")
    blocks = re.split(r"^### #", text, flags=re.M)[1:]
    seen: dict[int, dict[str, str]] = {}
    for block in blocks:
        block = re.split(r"^## ", block, flags=re.M)[0]
        number = int(re.match(r"(\d+)", block).group(1))
        fields = dict(re.findall(r"^- \*\*(.+?)\*\*：(.*)$", block, flags=re.M))
        fields["标题"] = block.split("\n", 1)[0].split(" ", 1)[1].strip()
        check(number not in seen, f"修订说明重复处理 #{number}")
        seen[number] = fields
    check(sorted(seen) == EXPECTED_ISSUES,
          f"修订说明的 Issue 覆盖不完整：缺 {sorted(set(EXPECTED_ISSUES) - set(seen))}，"
          f"多 {sorted(set(seen) - set(EXPECTED_ISSUES))}")
    by_issue: dict[int, set[str]] = {}
    for r in ledger:
        for n in r.issues:
            check(n in EXPECTED_ISSUES, f"{r.rid}: Issue #{n} 不在本轮范围")
            by_issue.setdefault(n, set()).add(r.rid)
    base_units = parse_units(BASELINE.read_text(encoding="utf-8"))
    changed = {k for k, v in rev.units.items() if k not in base_units or strip_blank(base_units[k]) != strip_blank(v)}
    counts = {d: [] for d in DISPOSITIONS}
    for number, fields in seen.items():
        disposition = fields.get("结论", "")
        check(disposition in DISPOSITIONS, f"#{number}: 结论“{disposition}”不在规定取值内")
        counts.setdefault(disposition, []).append(number)
        check(len(fields.get("理由", "")) >= 20, f"#{number}: 缺少理由")
        clauses = [c.strip() for c in fields.get("改动条款", "").split("、") if c.strip()]
        rids = {c.strip() for c in fields.get("修订编号", "").split("、") if c.strip() and c.strip() != "无"}
        check(rids == by_issue.get(number, set()),
              f"#{number}: 修订编号 {sorted(rids)} 与修订清单 {sorted(by_issue.get(number, set()))} 不一致")
        if clauses == ["无"]:
            check(not rids and disposition in ("不采纳", "需学校或标准维护机构裁定"), f"#{number}: 无改动条款但结论为{disposition}")
        else:
            check(bool(clauses), f"#{number}: 未列改动条款")
            for clause in clauses:
                check(clause in changed, f"#{number}: 改动条款 {clause} 在修订稿中不存在或未改动")
            expected = {c.strip().split(" ")[0] for r in ledger if number in r.issues for c in r.clause.split("、")}
            check(set(clauses) == expected, f"#{number}: 改动条款 {clauses} 与修订清单 {sorted(expected)} 不一致")
        if disposition == "部分采纳":
            check("未采纳部分" in fields, f"#{number}: 部分采纳应说明未采纳部分")
    for disposition in DISPOSITIONS:
        row = re.search(rf"^\| {disposition} \| (\d+) \| (.*?) \|$", text, flags=re.M)
        check(row is not None, f"统计表缺少“{disposition}”行")
        if row:
            listed = sorted(int(x) for x in re.findall(r"#(\d+)", row.group(2)))
            check(int(row.group(1)) == len(counts[disposition]) and listed == sorted(counts[disposition]),
                  f"统计表“{disposition}”与逐条结论不一致：应为 {sorted(counts[disposition])}")
    total = re.search(r"^\| 合计 \| (\d+) \|", text, flags=re.M)
    check(total is not None and int(total.group(1)) == len(EXPECTED_ISSUES), "统计表合计与 Issue 数不一致")
    section7 = text.split("## 7 需人工裁定的事项", 1)[-1].split("\n## ", 1)[0]
    for pid in BLOCKING_PENDING:
        check(pid in section7, f"需人工裁定事项清单未列 {pid}")
    for number in counts["部分采纳"] + counts["需学校或标准维护机构裁定"]:
        check(f"#{number}" in section7, f"#{number} 有待裁定部分，但未列入需人工裁定事项清单")
    if "--online" in sys.argv:
        for number, fields in seen.items():
            got = subprocess.run(["gh", "issue", "view", str(number), "--json", "title"],
                                 capture_output=True, text=True, cwd=ROOT)
            if got.returncode != 0:
                check(False, f"#{number}: gh 读取失败：{got.stderr.strip()[:80]}")
                continue
            title = json.loads(got.stdout)["title"].replace("[标准评议]", "")
            norm = lambda s: re.sub(r"\s+", "", s)  # noqa: E731
            check(norm(title) == norm(fields["标题"]), f"#{number}: 标题与 GitHub 不一致")
    notes.append("Issue 处理统计：" + "；".join(f"{d} {len(counts[d])}" for d in DISPOSITIONS))


def table_blocks(lines: list[str]) -> list[list[str]]:
    blocks: list[list[str]] = []
    previous = False
    for line in lines:
        current = line.startswith("|")
        if current:
            if previous:
                blocks[-1].append(line)
            else:
                blocks.append([line])
        previous = current
    return blocks


MARKED_JS = """
const { marked } = require(process.argv[1]);
const count = (tokens) => { let t = 0, p = 0; for (const k of tokens) {
  if (k.type === 'table') t++; else if (k.type === 'paragraph' && k.raw.startsWith('|')) p++;
  if (k.tokens && k.type !== 'table') { const c = count(k.tokens); t += c[0]; p += c[1]; } } return [t, p]; };
const out = process.argv.slice(2).map((f) => count(marked.lexer(require('fs').readFileSync(f, 'utf8'))));
console.log(JSON.stringify(out));
"""


def check_tables(base: Doc, rev: Doc, ledger) -> None:
    """表格语法：结构检查始终执行；找到网站锁定版本的 Marked 时再实际解析（--marked 时找不到即失败）。"""
    delimiter = re.compile(r"^\|(\s*:?-+:?\s*\|)+\s*$")
    for block in table_blocks(rev.lines):
        ok = len(block) >= 2 and delimiter.match(block[1]) is not None
        check(ok, f"表格缺少紧随表头的分隔行或被空行拆开：{block[0][:30]}")
    added = sum(1 for r in ledger for i, p in enumerate(r.paragraphs)
                if p.startswith("|") and (i == 0 or not r.paragraphs[i - 1].startswith("|")))
    check(len(table_blocks(rev.lines)) == len(table_blocks(base.lines)) + added,
          "修订稿的表格数不等于当前正文表格数加清单新增表格数")
    portal = ROOT / "designs" / "standards-portal"
    locked = json.loads((portal / "package.json").read_text(encoding="utf-8"))
    locked = {**locked.get("devDependencies", {}), **locked.get("dependencies", {})}.get("marked", "")
    candidates = [Path(os.environ["MARKED_DIR"])] if os.environ.get("MARKED_DIR") else []
    candidates.append(portal / "node_modules" / "marked")
    found = next((c for c in candidates if (c / "package.json").exists()), None)
    if found is None or shutil.which("node") is None:
        check("--marked" not in sys.argv, "未找到 Marked 或 node，无法按 --marked 实际解析表格")
        notes.append(f"表格只做了结构检查；未找到 Marked {locked}（可设 MARKED_DIR 指向其安装目录）")
        return
    version = json.loads((found / "package.json").read_text(encoding="utf-8"))["version"]
    check(version == locked, f"Marked 版本 {version} 与网站锁定的 {locked} 不一致")
    got = subprocess.run(["node", "-e", MARKED_JS, str(found), str(BASELINE), str(REVISED)], capture_output=True, text=True)
    if got.returncode != 0:
        check(False, f"Marked 解析失败：{got.stderr.strip()[:120]}")
        return
    (base_tables, base_stray), (rev_tables, rev_stray) = json.loads(got.stdout)
    check(rev_tables == base_tables + added, f"Marked 解析出表格 {rev_tables} 个，应为 {base_tables} + {added}")
    check(rev_stray <= base_stray, f"修订稿有 {rev_stray} 个以竖线开头却未解析为表格的段落（当前正文 {base_stray} 个）")
    notes.append(f"Marked {version} 解析：当前正文表格 {base_tables} 个，修订稿 {rev_tables} 个（新增 {added} 个）；未解析为表格的竖线段落 {rev_stray} 个")


def main() -> int:
    ledger = load_ledger()
    base = Doc(BASELINE.read_text(encoding="utf-8"))
    rev = Doc(REVISED.read_text(encoding="utf-8"))
    steps = (
        ("受保护目录未改", lambda: check_protected_dirs()),
        ("修订稿可由清单复现且 diff.md 最新", lambda: check_build(ledger)),
        ("当前正文逐行保留", lambda: check_preservation(base, rev, ledger)),
        ("附录 A、测试集与待决事项未改", lambda: check_protected_blocks(base, rev)),
        ("条款号唯一连续", lambda: check_numbering(base, rev)),
        ("新增条款归入条款组", lambda: check_clause_groups(rev)),
        ("交叉引用可解析", lambda: check_references(base, rev, ledger)),
        ("正文体例与待决性质", lambda: check_content_rules(base, rev, ledger)),
        ("表格可解析", lambda: check_tables(base, rev, ledger)),
        ("Issue 全覆盖", lambda: check_issue_coverage(rev, ledger)),
    )
    for name, step in steps:
        before = len(failures)
        step()
        print(f"[{'通过' if len(failures) == before else '失败'}] {name}")
    for note in notes:
        print(f"  说明：{note}")
    for failure in failures:
        print(f"  失败：{failure}", file=sys.stderr)
    print(f"修订 {len(ledger)} 条；Issue {len(EXPECTED_ISSUES)} 个；失败 {len(failures)} 项")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
