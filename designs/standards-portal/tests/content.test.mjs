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

test("29 canonical pages are indexed, with a separate 404", async () => {
  const sitemap = await readFile(
    path.join(project, "dist/sitemap.xml"),
    "utf8",
  );
  assert.equal([...sitemap.matchAll(/<loc>/g)].length, 29);
  assert.ok(
    (await readFile(path.join(project, "dist/404.html"), "utf8")).includes(
      "页面未找到",
    ),
  );
});

test("search preserves technical field names and unknown", async () => {
  const index = JSON.parse(
    await readFile(path.join(project, "src/search-index.json")),
  );
  const full = index.map((item) => item.text).join("\n");
  for (const term of ["source_event_id", "payload_hash", "unknown"])
    assert.ok(full.includes(term), term);
});

test("review publication contains no editorial history in pages or search", async () => {
  const forbidden =
    /v0\.1|chunlin@1106|原 S[0-7]|S[0-7]-\d|S0—S7|前序版本|跨版本对照|修订依据|本次修订|专家意见—条款对照|PR #26|#11—#25/;
  assert.ok(!forbidden.test(source));
  for (const section of data.sections) {
    assert.ok(!forbidden.test(section.html), section.key);
    const page = await readFile(
      path.join(project, "dist/read", section.key, "index.html"),
      "utf8",
    );
    assert.ok(!forbidden.test(page), section.key);
  }
  for (const route of [
    "index.html",
    "decisions/index.html",
    "downloads/index.html",
  ]) {
    assert.ok(
      !forbidden.test(
        await readFile(path.join(project, "dist", route), "utf8"),
      ),
      route,
    );
  }
  assert.ok(
    !forbidden.test(
      await readFile(path.join(project, "src/search-index.json"), "utf8"),
    ),
  );
  assert.ok(
    data.sections
      .find((section) => section.key === "c")
      .title.includes("评议指引"),
  );
  assert.deepEqual(
    (await readdir(path.join(project, "dist/downloads"))).sort(),
    ["index.html", ...data.downloads.map((file) => file.file)].sort(),
  );
});

test("only the approved matrix clarifications (three C-to-M, one —-to-C) differ from the technical source", async () => {
  const technical = await readFile(
    path.join(
      root,
      "archive/起草稿_chunlin@1106/未来智慧教学平台数据资产层标准_chunlin@1106.md",
    ),
    "utf8",
  );
  const baseline = new Map();
  let groups = [];
  for (const line of technical.split("### A.4 适用矩阵")[1].split("### A.5")[0].split("\n")) {
    if (!line.startsWith("| ")) continue;
    const row = line.split("|").slice(1, -1).map((cell) => cell.trim());
    if (row[0] === "Profile") groups = row.slice(1);
    if (!row[0].startsWith("P-")) continue;
    assert.equal(row.length - 1, groups.length);
    for (let i = 0; i < groups.length; i++) {
      const key = `${row[0].split(" ")[0]}/${groups[i]}`;
      assert.ok(!baseline.has(key), key);
      baseline.set(key, row[i + 1]);
    }
  }
  const current = new Map();
  for (const table of data.matrixTables) {
    for (const row of table.rows) {
      assert.equal(row.length - 1, table.columns.length);
      for (let i = 0; i < table.columns.length; i++) {
        const key = `${row[0].split(" ")[0]}/${table.columns[i]}`;
        assert.ok(!current.has(key), key);
        current.set(key, row[i + 1]);
      }
    }
  }
  assert.equal(baseline.size, 288);
  assert.equal(current.size, 288);
  assert.deepEqual([...current.keys()], [...baseline.keys()]);
  const changes = [];
  let unchanged = 0;
  for (const [cell, before] of baseline) {
    const after = current.get(cell);
    if (before === after) unchanged++;
    else changes.push({ cell, before, after });
  }
  const byCell = (a, b) => a.cell.localeCompare(b.cell);
  assert.deepEqual(changes.sort(byCell), [
    { cell: "P-RES/11-C", before: "C", after: "M" },
    { cell: "P-RSB/10-B", before: "—", after: "C" },
    { cell: "P-RSB/12-A", before: "C", after: "M" },
    { cell: "P-RSB/12-B", before: "C", after: "M" },
  ]);
  assert.equal(unchanged, 284);
});
