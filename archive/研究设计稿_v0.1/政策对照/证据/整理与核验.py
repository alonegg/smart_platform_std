"""Extract official policy text and verify the archived PDF against it."""

from __future__ import annotations

import hashlib
import json
import logging
import re
import subprocess
from datetime import datetime
from html.parser import HTMLParser
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
LOG = logging.getLogger(__name__)


class PolicyParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.depth = 0
        self.parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "div":
            if self.depth:
                self.depth += 1
            elif dict(attrs).get("id") == "downloadContent":
                self.depth = 1
        if self.depth and tag == "br":
            self.parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if self.depth and tag in {"p", "h1"}:
            self.parts.append("\n\n")
        if tag == "div" and self.depth:
            self.depth -= 1

    def handle_data(self, data: str) -> None:
        if self.depth:
            self.parts.append(data)


def normalize(value: str) -> str:
    return re.sub(r"\s+", "", value)


def main() -> None:
    official = ROOT / "原文/教育部_人工智能+教育行动计划_官方网页.html"
    parser = PolicyParser()
    parser.feed(official.read_text(encoding="utf-8"))
    paragraphs = [p.strip() for p in "".join(parser.parts).split("\n\n") if p.strip()]
    plain = "\n\n".join(paragraphs) + "\n"
    (ROOT / "原文/人工智能+教育行动计划_官网正文.txt").write_text(plain, encoding="utf-8")
    pdf = ROOT / "原文/人工智能+教育行动计划_高校存档版.pdf"
    pdf_text = subprocess.run(
        ["pdftotext", "-layout", str(pdf), "-"], check=True, capture_output=True, text=True
    ).stdout
    (ROOT / "原文/人工智能+教育行动计划_高校存档版_提取文本.txt").write_text(pdf_text, encoding="utf-8")
    pdf_norm = normalize(pdf_text)
    checks = [{"paragraph": i, "prefix": p[:46], "exact_after_whitespace_removal": normalize(p) in pdf_norm}
              for i, p in enumerate(paragraphs, 1)]
    tasks = re.findall(r"（[一二三四五六七八九十]+）[^。]+。", plain)
    sections = re.findall(r"^[一二三四五六]、[^\n]+", plain, flags=re.MULTILINE)
    assert len(tasks) == 16, tasks
    assert len(sections) == 6, sections
    assert "教科信〔2026〕1号" in plain
    assert "2026年4月2日" in plain
    manifest = {
        "verified_at": datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(),
        "official_source": "https://hudong.moe.gov.cn/srcsite/A16/s3342/202604/t20260410_1433240.html",
        "canonical_source": "https://www.moe.gov.cn/srcsite/A16/s3342/202604/t20260410_1433240.html",
        "official_qa_source": "https://hudong.moe.gov.cn/jyb_xwfb/s271/202604/t20260410_1433232.html",
        "pdf_mirror_source": "https://ihe.qdbhu.edu.cn/__local/E/B8/E7/675F5C1031BD829E5E545B1777F_3A1866D4_60387.pdf",
        "pdf_source_status": "高校重新排版存档；不是教育部盖章扫描件；已按官网正文逐段核对",
        "official_pdf_attempt": "官网按钮使用HTML转PDF服务；本次HTTPS请求返回HTTP 550，未将响应冒充PDF",
        "signed_date": "2026-04-02", "metadata_generation_date": "2026-04-08",
        "web_publication_date": "2026-04-10", "policy_number": "教科信〔2026〕1号",
        "sections": sections, "tasks": tasks, "pdf_pages": 9,
        "paragraph_comparison": checks,
        "comparison_note": "仅去空白逐段匹配；未匹配项必须另行检查，不能以hash替代正文一致性",
        "files": [{"path": str(p.relative_to(ROOT)), "bytes": p.stat().st_size,
                   "sha256": hashlib.sha256(p.read_bytes()).hexdigest()}
                  for p in sorted((ROOT / "原文").iterdir()) if p.is_file()],
    }
    (ROOT / "证据/下载与正文核验.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    LOG.info("Extracted %d sections, %d tasks; matched %d/%d paragraphs", len(sections), len(tasks), sum(c["exact_after_whitespace_removal"] for c in checks), len(checks))
    for check in checks:
        if not check["exact_after_whitespace_removal"]:
            LOG.warning("Unmatched paragraph: %s", check)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    main()
