import { readFile, writeFile, mkdir, copyFile, rm } from "node:fs/promises";
import { execFileSync } from "node:child_process";
import { createHash } from "node:crypto";
import { fileURLToPath } from "node:url";
import path from "node:path";
import { marked } from "marked";

export const project = fileURLToPath(new URL("../", import.meta.url));
export const root = path.resolve(project, "../..");
export const sourcePath = "标准/评审稿/智慧教学-数据模型标准.md";
export const sourceCommit = "0ac34e9814c105de3b5af30bb6ba9bb31fc0a2fb";
export const standardTitle = "智慧教学-数据模型标准";
export const sourceBase = `https://github.com/alonegg/smart_platform_std/blob/${sourceCommit}/`;
const digest = (text) => createHash("sha256").update(text).digest("hex");
const plain = (text) =>
  text
    .replace(/<[^>]*>/g, "")
    .replace(/[*`]/g, "")
    .replace(/^#{1,6}\s+/gm, "")
    .replace(/\[([^\]]+)\]\([^)]+\)/g, "$1");
const headingId = (text) => {
  const number = plain(text).match(
    /^(\d+(?:\.\d+)*|[A-E]\.\d+(?:\.\d+)*)(?:\s|　|$)/,
  )?.[1];
  return number
    ? `clause-${number.replaceAll(".", "-")}`
    : `heading-${digest(text).slice(0, 10)}`;
};

export function parseSections(markdown) {
  const parts = markdown.split(/^## /m).slice(1);
  return parts
    .filter((part) => !part.startsWith("目次"))
    .map((part) => {
      const [title, ...rest] = part.split("\n");
      const body = rest.join("\n").trim();
      const key =
        title.match(/^(\d+) /)?.[1] ??
        title.match(/^附录 ([A-E])/)?.[1]?.toLowerCase() ??
        (title === "前言" ? "foreword" : "introduction");
      const headings = [];
      const renderer = new marked.Renderer();
      renderer.heading = ({ tokens, depth, text }) => {
        const id = headingId(text);
        headings.push({ id, title: plain(text), depth });
        return `<h${depth - 1} id="${id}">${marked.parseInline(text)}</h${depth - 1}>\n`;
      };
      const paragraphIds = new Set();
      renderer.paragraph = function ({ tokens, text }) {
        const inner = this.parser.parseInline(tokens);
        const number = plain(text).match(
          /^((?:\d+|[A-E])(?:\.\d+){2,})(?:\s|　)/,
        )?.[1];
        if (!number) return `<p>${inner}</p>\n`;
        const id = `clause-${number.replaceAll(".", "-")}`;
        if (paragraphIds.has(id) || headings.some((h) => h.id === id))
          return `<p>${inner}</p>\n`;
        paragraphIds.add(id);
        return `<p id="${id}" class="clause" data-clause="${number}">${inner}<a class="clause-comment" href="/comment/?clause=${encodeURIComponent(number)}&amp;section=${key}" aria-label="对 ${number} 提出意见">意见</a></p>\n`;
      };
      const html = marked
        .parse(body, { renderer, gfm: true })
        .replace(
          /<table>/g,
          '<div class="table-wrap" tabindex="0" role="region" aria-label="标准原文表格（可横向滚动）"><table>',
        )
        .replace(/<\/table>/g, "</table></div>");
      const blocks = body.split(/(?=^#{3,4} )/m).map((block) => {
        const title = block.match(/^#{3,4} (.+)/)?.[1];
        return {
          title: title ? plain(title) : plain(part.split("\n")[0]),
          anchor: title ? headingId(title) : "",
          text: plain(block),
        };
      });
      return { key, title, body, html, headings, blocks };
    });
}

function tableRows(body, heading) {
  const segment = body.split(heading)[1]?.split(/^### /m)[0] ?? "";
  return segment
    .split("\n")
    .filter((line) => /^\|/.test(line))
    .map((line) =>
      line
        .split("|")
        .slice(1, -1)
        .map((cell) => cell.trim()),
    )
    .filter((row) => !row.every((cell) => /^[-:]+$/.test(cell)))
    .slice(1);
}

export async function generateContent() {
  const markdown = await readFile(path.join(root, sourcePath), "utf8");
  const controlled = execFileSync(
    "git",
    ["show", `${sourceCommit}:${sourcePath}`],
    { cwd: root, encoding: "utf8" },
  );
  if (markdown !== controlled)
    throw new Error(
      "Source differs from the controlled review draft. Review and update the baseline explicitly.",
    );
  const sections = parseSections(markdown);
  const appendixA = sections.find((s) => s.key === "a");
  const profiles = tableRows(appendixA.body, "### A.2 能力 Profile 定义").map(
    ([code, name, scope, boundary]) => ({ code, name, scope, boundary }),
  );
  const groups = tableRows(appendixA.body, "### A.3 条款组定义");
  const triggers = tableRows(appendixA.body, "### A.5 条件适用触发条件").map(
    ([group, condition]) => ({ group, condition }),
  );
  const pending = tableRows(
    sections.find((s) => s.key === "e").body,
    "E.1 下列事项",
  ).map(([code, title, treatment, owner, clause, stage]) => ({
    code,
    title,
    treatment,
    owner,
    clause,
    stage,
  }));
  const phases = tableRows(
    sections.find((s) => s.key === "d").body,
    "### D.1 阶段与放行条件",
  ).map(([name, output, gate]) => ({ name, output, gate }));
  const matrixTables = [
    ...appendixA.body
      .split("### A.4 适用矩阵")[1]
      .split("### A.5")[0]
      .matchAll(/^\| Profile \|[^\n]*\n(?:\|[^\n]*(?:\n|$))+/gm),
  ].map((match) => {
    const rows = match[0]
      .split("\n")
      .map((line) =>
        line
          .split("|")
          .slice(1, -1)
          .map((cell) => cell.trim()),
      )
      .filter((row) => !row.every((cell) => /^[-:]+$/.test(cell)));
    return { columns: rows[0].slice(1), rows: rows.slice(1) };
  });
  const data = {
    title: standardTitle,
    version: "征求意见稿",
    date: "2026-11-10",
    synced: "2026-11-10",
    sourceCommit,
    frontMatterHtml: marked.parse(
      markdown
        .split("## 目次")[0]
        .split("\n")
        .slice(1)
        .join("\n")
        .replace(/---\s*$/, ""),
    ),
    sourcePath,
    sourceUrl:
      sourceBase + sourcePath.split("/").map(encodeURIComponent).join("/"),
    sourceSha256: digest(markdown),
    sections: sections.map(({ body, blocks, ...section }) => section),
    profiles,
    groups,
    triggers,
    matrixTables,
    pending,
    phases,
    downloads: [
      {
        title: `${standardTitle} · Word`,
        description: "完整征求意见稿，便于批注与评议",
        file: "standard-review.docx",
        from: sourcePath.replace(/\.md$/, ".docx"),
        type: "DOCX",
        current: true,
      },
      {
        title: `${standardTitle} · PDF`,
        description: "便于阅读与打印，内容与 Word 稿一致",
        file: "standard-review.pdf",
        from: sourcePath.replace(/\.md$/, ".pdf"),
        type: "PDF",
        current: true,
      },
      {
        title: `${standardTitle} · Markdown`,
        description: "与在线标准全文一致",
        file: "standard-review.md",
        from: sourcePath,
        type: "MD",
        current: true,
      },
      {
        title: "评议意见汇总表 · Word",
        description: "多行汇总格式，每行一条意见，填写后发送至编制组",
        file: "review-comments.docx",
        from: "标准/评审稿/评议意见表.docx",
        type: "DOCX",
        current: true,
      },
      {
        title: "评议意见汇总表 · Markdown",
        description: "可复制的评议格式",
        file: "review-comments.md",
        from: "标准/评审稿/评议意见表.md",
        type: "MD",
        current: true,
      },
    ],
  };
  if (
    sections.length !== 19 ||
    profiles.length !== 9 ||
    triggers.length !== 17 ||
    pending.length !== 30 ||
    phases.length !== 6 ||
    matrixTables.length !== 4 ||
    matrixTables.some((table) => table.rows.length !== 9)
  ) {
    throw new Error(
      `Incomplete source extraction: ${JSON.stringify({ sections: sections.length, profiles: profiles.length, pending: pending.length, phases: phases.length, matrices: matrixTables.length })}`,
    );
  }
  await mkdir(path.join(project, "src"), { recursive: true });
  await rm(path.join(project, "public/downloads"), {
    recursive: true,
    force: true,
  });
  await mkdir(path.join(project, "public/downloads"), { recursive: true });
  for (const item of data.downloads) {
    const bytes = await readFile(path.join(root, item.from));
    item.sha256 = digest(bytes);
    item.bytes = bytes.length;
    await copyFile(
      path.join(root, item.from),
      path.join(project, "public/downloads", item.file),
    );
  }
  await writeFile(
    path.join(project, "src/generated.json"),
    JSON.stringify(data),
  );
  await writeFile(
    path.join(project, "src/search-index.json"),
    JSON.stringify(
      sections.flatMap((section) =>
        section.blocks.map((block) => ({
          ...block,
          section: { key: section.key, title: section.title },
        })),
      ),
    ),
  );
  await writeFile(
    path.join(project, "public/version.json"),
    JSON.stringify(
      {
        version: data.version,
        sourceCommit,
        sourceSha256: data.sourceSha256,
        documentStatus: "征求意见稿",
        siteCommit: execFileSync("git", ["rev-parse", "HEAD"], {
          cwd: root,
          encoding: "utf8",
        }).trim(),
        downloads: data.downloads.map(({ file, sha256, bytes }) => ({
          file,
          sha256,
          bytes,
        })),
      },
      null,
      2,
    ),
  );
  return data;
}
