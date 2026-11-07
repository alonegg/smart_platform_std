import test from "node:test";
import assert from "node:assert/strict";
import { readFile, readdir } from "node:fs/promises";
import path from "node:path";
import { createHash } from "node:crypto";
import {
  root,
  project,
  sourcePath,
  sourceCommit,
} from "../scripts/content.mjs";
const data = JSON.parse(
  await readFile(path.join(project, "src/generated.json")),
);
const source = await readFile(path.join(root, sourcePath), "utf8");

test("controlled version, complete chapter set and decision identifiers", () => {
  assert.equal(data.sourceCommit, sourceCommit);
  assert.equal(
    data.sourceSha256,
    createHash("sha256").update(source).digest("hex"),
  );
  assert.deepEqual(
    data.sections.map((s) => s.key),
    [
      "foreword",
      "introduction",
      ...Array.from({ length: 12 }, (_, i) => String(i + 1)),
      "a",
      "b",
      "c",
      "d",
      "e",
    ],
  );
  assert.deepEqual(
    data.pending.map((s) => s.code),
    Array.from({ length: 30 }, (_, i) => `E${String(i + 1).padStart(2, "0")}`),
  );
  assert.equal(data.phases.length, 6);
  assert.equal(data.profiles.length, 9);
  assert.equal(data.groups.length, 32);
});

test("all 288 Profile applicability cells exactly match appendix A.4", () => {
  const original = source.split("### A.4 适用矩阵")[1].split("### A.5")[0];
  const rows = original.split("\n").filter((line) => line.startsWith("| P-"));
  const rendered = data.matrixTables.flatMap((table) =>
    table.rows.map((row) => `| ${row.join(" | ")} |`),
  );
  assert.deepEqual(rendered, rows);
  assert.equal(
    data.matrixTables.reduce(
      (sum, table) => sum + table.rows.length * table.columns.length,
      0,
    ),
    288,
  );
});

test("every subsection has a unique stable anchor and complete static page", async () => {
  for (const section of data.sections) {
    const ids = [...section.html.matchAll(/ id="([^"]+)"/g)].map(
      (match) => match[1],
    );
    assert.equal(
      ids.length,
      new Set(ids).size,
      `duplicate anchors in ${section.key}`,
    );
    for (const heading of section.headings) assert.ok(ids.includes(heading.id));
    const html = await readFile(
      path.join(project, "dist/read", section.key, "index.html"),
      "utf8",
    );
    assert.ok(html.includes(section.title));
    assert.ok(
      html.includes(section.html),
      `static content missing for ${section.key}`,
    );
    assert.ok(html.includes("征求意见稿"));
    assert.ok(!/localhost|\/Users\/alone|swufe80@gmail/.test(html));
  }
});

test("download bytes match original controlled files and manifest", async () => {
  for (const item of data.downloads) {
    const original = await readFile(path.join(root, item.from));
    const download = await readFile(
      path.join(project, "dist/downloads", item.file),
    );
    assert.ok(original.equals(download), item.file);
    assert.equal(
      createHash("sha256").update(download).digest("hex"),
      item.sha256,
    );
  }
});

test("25 canonical pages are indexed, with a separate 404", async () => {
  const sitemap = await readFile(
    path.join(project, "dist/sitemap.xml"),
    "utf8",
  );
  assert.equal([...sitemap.matchAll(/<loc>/g)].length, 25);
  assert.ok(
    (await readFile(path.join(project, "dist/404.html"), "utf8")).includes(
      "页面未找到",
    ),
  );
});

test("search preserves field names, expert issue references and unknown", async () => {
  const index = JSON.parse(
    await readFile(path.join(project, "src/search-index.json")),
  );
  const full = index.map((item) => item.text).join("\n");
  for (const term of ["source_event_id", "payload_hash", "#11", "unknown"])
    assert.ok(full.includes(term), term);
});
