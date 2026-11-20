"""把标准 Markdown 拆成“条款单元”，供差异生成与检查脚本共用。仅标准库。"""
from __future__ import annotations

import re
from collections import OrderedDict

CLAUSE_RE = re.compile(r"^(\d{1,2}(?:\.\d{1,2}){2,3})\s")          # 5.1.3、4.4.5.2
APPENDIX_CLAUSE_RE = re.compile(r"^([A-E]\.\d{1,2}(?:\.\d{1,2})?)\s")  # A.3.1、E.1
HEADING_RE = re.compile(r"^(#{1,4})\s+(.*)$")
SECTION_NO_RE = re.compile(r"^(\d{1,2}(?:\.\d{1,2}){1,2}|[A-E]\.\d{1,2})\s")
ITEM_RE = re.compile(r"^([a-z])\)\s")
TABLE_CAPTION_RE = re.compile(r"^(表 (?:\d{1,2}-\d{1,2}|[A-E]\.\d{1,2}))\s")


def parse_units(text: str) -> "OrderedDict[str, list[str]]":
    """返回 {单元键: 行列表}。单元键为条款号、带编号的标题或标题原文。"""
    units: "OrderedDict[str, list[str]]" = OrderedDict()
    key = "（文首）"
    units[key] = []
    for line in text.split("\n"):
        new_key = None
        heading = HEADING_RE.match(line)
        if heading:
            title = heading.group(2).strip()
            numbered = SECTION_NO_RE.match(title + " ")
            new_key = numbered.group(1) if numbered else title
        else:
            clause = CLAUSE_RE.match(line) or APPENDIX_CLAUSE_RE.match(line)
            if clause:
                new_key = clause.group(1)
        if new_key is not None:
            if new_key in units:
                new_key = f"{new_key}（重复）"
            key = new_key
            units[key] = []
        units[key].append(line)
    return units


def strip_blank(lines: list[str]) -> list[str]:
    return [line for line in lines if line.strip()]


def items_of(lines: list[str]) -> set[str]:
    return {m.group(1) for line in lines if (m := ITEM_RE.match(line))}


def table_captions(text: str) -> list[str]:
    """表题行：以“表 X-N 标题”独立成行；以“表 X-N”开头的叙述句（含句读）不算表题。"""
    return [m.group(1) for line in text.split("\n")
            if (m := TABLE_CAPTION_RE.match(line)) and not re.search(r"[。，；]", line)]
