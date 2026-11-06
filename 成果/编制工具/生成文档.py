"""Build editable Word documents from the reviewed Markdown sources."""

from __future__ import annotations

import logging
import subprocess
from pathlib import Path

from docx import Document
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Inches, Pt, RGBColor

ROOT = Path(__file__).resolve().parents[1]
TEMP = ROOT.parent / "temp"
LOG = logging.getLogger(__name__)
CHINESE_FONT = "Arial Unicode MS"


def set_font(style: object, east_asia: str, size: float) -> None:
    style.font.name = "Arial"
    style.font.size = Pt(size)
    fonts = style.element.get_or_add_rPr().rFonts
    for attribute in ("asciiTheme", "hAnsiTheme", "eastAsiaTheme", "cstheme"):
        fonts.attrib.pop(qn("w:" + attribute), None)
    fonts.set(qn("w:eastAsia"), east_asia)


def format_document(path: Path, combined: bool) -> None:
    doc = Document(path)
    for section in doc.sections:
        section.page_width = Cm(21)
        section.page_height = Cm(29.7)
        section.top_margin = Cm(2)
        section.bottom_margin = Cm(1.9)
        section.left_margin = Cm(2)
        section.right_margin = Cm(2)
        section.header_distance = Cm(0.8)
        section.footer_distance = Cm(0.8)
        header = section.header.paragraphs[0]
        header.text = "未来智慧教学平台  |  架构与数据资产标准体系"
        header.runs[0].font.size = Pt(8)
        header.runs[0].font.color.rgb = RGBColor.from_string("64748B")
        footer = section.footer.paragraphs[0]
        footer.alignment = 2
        run = footer.add_run("研究设计稿 v0.1  ·  2026-10-23    |    ")
        run.font.size = Pt(8)
        field = OxmlElement("w:fldSimple")
        field.set(qn("w:instr"), "PAGE")
        footer._p.append(field)
    for name in ("Normal", "Body Text", "First Paragraph", "Compact"):
        if name in doc.styles:
            style = doc.styles[name]
            set_font(style, CHINESE_FONT, 10.5)
            style.paragraph_format.line_spacing = 1.22
            style.paragraph_format.space_after = Pt(5)
    for name, size in (("Title", 25), ("Subtitle", 12), ("Heading 1", 19), ("Heading 2", 14), ("Heading 3", 11.5)):
        if name in doc.styles:
            style = doc.styles[name]
            set_font(style, CHINESE_FONT, size)
            style.font.color.rgb = RGBColor.from_string("203D60")
            style.paragraph_format.space_before = Pt(12)
            style.paragraph_format.space_after = Pt(7)
            style.paragraph_format.keep_with_next = True
    if "Verbatim Char" in doc.styles:
        set_font(doc.styles["Verbatim Char"], CHINESE_FONT, 9)
    for paragraph in doc.paragraphs:
        if combined and paragraph.style.name == "Heading 1" and paragraph.text != "阅读导航":
            paragraph.paragraph_format.page_break_before = True
        paragraph.paragraph_format.widow_control = True
    for shape in doc.inline_shapes:
        ratio = shape.height / shape.width
        shape.width = Inches(6.55)
        shape.height = int(shape.width * ratio)
    for table in doc.tables:
        table.autofit = False
        count = len(table.columns)
        ratios = {3: [0.27, 0.36, 0.37], 4: [0.18, 0.27, 0.24, 0.31], 5: [0.1, 0.22, 0.22, 0.23, 0.23]}.get(count, [1 / count] * count)
        # The source registry needs a narrow ID column and wider hyperlink titles.
        if count == 3 and table.cell(0, 0).text == "ID":
            ratios = [0.10, 0.50, 0.40]
        if count == 4 and table.cell(0, 0).text == "编号":
            ratios = [0.08, 0.24, 0.35, 0.33]
        for col, ratio in zip(table.columns, ratios):
            col.width = Cm(17 * ratio)
        for row_index, row in enumerate(table.rows):
            props = row._tr.get_or_add_trPr()
            keep = OxmlElement("w:cantSplit")
            props.append(keep)
            if row_index == 0:
                repeat = OxmlElement("w:tblHeader")
                props.append(repeat)
            for index, cell in enumerate(row.cells):
                cell.width = Cm(17 * ratios[index])
                cell.vertical_alignment = 1
                tc_pr = cell._tc.get_or_add_tcPr()
                shade = OxmlElement("w:shd")
                shade.set(qn("w:fill"), "E7EEF7" if row_index == 0 else ("F6F8FB" if row_index % 2 == 0 else "FFFFFF"))
                tc_pr.append(shade)
                margins = OxmlElement("w:tcMar")
                for edge in ("top", "bottom", "left", "right"):
                    value = OxmlElement("w:" + edge)
                    value.set(qn("w:w"), "80")
                    value.set(qn("w:type"), "dxa")
                    margins.append(value)
                tc_pr.append(margins)
                for paragraph in cell.paragraphs:
                    paragraph.paragraph_format.space_before = Pt(0)
                    paragraph.paragraph_format.space_after = Pt(2)
                    paragraph.paragraph_format.line_spacing = 1.1
                    for run in paragraph.runs:
                        run.font.size = Pt(9)
                        run.font.name = "Arial"
                        run._element.get_or_add_rPr().rFonts.set(qn("w:eastAsia"), CHINESE_FONT)
                        run.bold = row_index == 0
    doc.core_properties.author = ""
    doc.core_properties.subject = "三层架构、教学数据资产与互操作标准研究设计稿"
    doc.core_properties.keywords = "智慧教学;数据资产;xAPI;SCORM;QTI;CASE;认知状态"
    doc.save(path)


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    TEMP.mkdir(exist_ok=True)
    sources = [ROOT / name for name in ("01_三层架构具体描述.md", "02_数据资产层标准体系草案.md", "03_标准研究与采用说明.md", "04_原始材料提取追踪与编制边界.md")]
    combined = TEMP / "合订稿.md"
    intro = """---
title: 未来智慧教学平台
subtitle: 三层架构与数据资产标准体系
date: 研究设计稿 v0.1 · 2026-10-23
lang: zh-CN
---

# 阅读导航

本稿提出由基础设施层、数据资产层、应用层构成的未来智慧教学体系，重点定义课程资源、教学过程资源与数据、学生认知状态的组织和交换方式。

1. 第一部分：三层架构具体描述。适合讨论体系定位、分层职责和建设范围。
2. 第二部分：数据资产层标准体系。包含 S0—S7、核心字段及 T01—T16 验证场景。
3. 第三部分：标准研究与采用说明。包括版本状态、采用选择和官方来源。
4. 第四部分：原始材料提取追踪。说明来源定位、重新组织和新增设计。

配套目录提供架构图、核心字段字典、事件词表、国内外标准采用矩阵、来源索引及合成数据样例。

版本性质：供学校研究与审议。规范尚未正式发布，互操作和教学效果须按后续试点验证。

"""
    parts = []
    names = ["第一部分  三层架构具体描述", "第二部分  数据资产层标准体系", "第三部分  标准研究与采用说明", "第四部分  原始材料提取追踪"]
    for source, title in zip(sources, names):
        body = source.read_text(encoding="utf-8").split("\n", 1)[1]
        parts.append("# " + title + "\n" + body)
    combined.write_text(intro + "\n\n".join(parts), encoding="utf-8")
    outputs = [(combined, ROOT / "未来智慧教学平台_架构与标准体系_v0.1.docx", True), (sources[0], ROOT / "三层架构具体描述_v0.1.docx", False)]
    for source, destination, is_combined in outputs:
        subprocess.run(["/opt/homebrew/bin/pandoc", str(source), "--from=markdown", "--to=docx", "--resource-path=" + str(ROOT), "--output=" + str(destination)], check=True)
        format_document(destination, is_combined)
        LOG.info("Generated %s", destination.name)


if __name__ == "__main__":
    main()
