#!/usr/bin/env python3
"""按《修订清单.txt》在当前正文的副本上生成修订稿全文。

用法（仓库根目录，Python 3.11+，仅标准库，不联网）：
    python3 -B 维护/第2轮修订稿/build_revision.py          # 重新生成修订稿
    python3 -B 维护/第2轮修订稿/build_revision.py --check  # 只核对已提交修订稿与清单一致
不改写 标准/、designs/、archive/。
"""
from __future__ import annotations

import sys
from dataclasses import dataclass, field
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
BASELINE = ROOT / "标准" / "评审稿" / "智慧教学-数据模型标准.md"
REVISED = HERE / "智慧教学-数据模型标准-修订稿.md"
LEDGER = HERE / "修订清单.txt"


@dataclass
class Revision:
    rid: str
    op: str = ""
    anchor: str = ""
    clause: str = ""
    issues: list[int] = field(default_factory=list)
    pending: list[str] = field(default_factory=list)
    sources: str = ""
    text: str = ""

    @property
    def paragraphs(self) -> list[str]:
        return [p for p in self.text.split("\n") if p.strip()]


def load_ledger(path: Path = LEDGER) -> list[Revision]:
    revisions: list[Revision] = []
    current: Revision | None = None
    in_body = False
    body: list[str] = []
    for raw in path.read_text(encoding="utf-8").split("\n"):
        if raw.startswith("### R") and raw[5:].strip().isdigit():
            if current is not None:
                current.text = "\n".join(body).strip("\n")
                revisions.append(current)
            current, in_body, body = Revision(raw[4:].strip()), False, []
            continue
        if current is None:
            continue
        if not in_body:
            if raw.strip() == "---":
                in_body = True
                continue
            if ":" not in raw:
                continue
            key, value = (part.strip() for part in raw.split(":", 1))
            if key == "issues":
                current.issues = [int(x) for x in value.replace("，", ",").split(",") if x.strip()]
            elif key == "pending":
                current.pending = [x.strip() for x in value.replace("，", ",").split(",") if x.strip()]
            elif key in ("op", "anchor", "clause", "sources"):
                setattr(current, key, value)
            else:
                raise SystemExit(f"{current.rid}: 未知字段 {key}")
        else:
            body.append(raw)
    if current is not None:
        current.text = "\n".join(body).strip("\n")
        revisions.append(current)
    ids = [r.rid for r in revisions]
    if len(ids) != len(set(ids)):
        raise SystemExit("修订清单存在重复编号")
    for r in revisions:
        if r.op not in ("replace", "insert_after") or not r.anchor or not r.clause or not (r.issues or r.sources) or not r.text:
            raise SystemExit(f"{r.rid}: 字段不完整")
    return revisions


def apply(baseline: str, revisions: list[Revision]) -> str:
    lines = baseline.split("\n")
    located: dict[int, list[Revision]] = {}
    for r in revisions:
        hits = [i for i, line in enumerate(lines) if line.startswith(r.anchor)]
        if len(hits) != 1:
            raise SystemExit(f"{r.rid}: 锚点在当前正文中命中 {len(hits)} 次，应恰为 1 次：{r.anchor}")
        located.setdefault(hits[0], []).append(r)
    for index in sorted(located, reverse=True):
        group = located[index]
        if len(group) > 1 and any(r.op != "insert_after" for r in group):
            raise SystemExit(f"{group[0].rid}: 同一锚点的多条修订只能是 insert_after")
        new: list[str] = []
        for r in group:  # 同一锚点按清单顺序依次追加
            for para in r.paragraphs:
                in_table = bool(new) and new[-1].startswith("|") and para.startswith("|")
                if (new or r.op == "insert_after") and not in_table:  # 表格各行之间不插空行
                    new.append("")
                new.append(para)
        if group[0].op == "replace":
            lines[index:index + 1] = new
        else:
            lines[index + 1:index + 1] = new
    return "\n".join(lines)


def main() -> int:
    result = apply(BASELINE.read_text(encoding="utf-8"), load_ledger())
    if "--check" in sys.argv[1:]:
        if not REVISED.exists() or REVISED.read_text(encoding="utf-8") != result:
            print("修订稿与“当前正文 + 修订清单”不一致", file=sys.stderr)
            return 1
        print("修订稿与“当前正文 + 修订清单”一致")
        return 0
    REVISED.write_text(result, encoding="utf-8")
    print(f"已生成 {REVISED.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
