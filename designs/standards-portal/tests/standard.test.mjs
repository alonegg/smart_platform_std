import test from "node:test";
import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import { marked } from "marked";

const source = await readFile(
  new URL("../../../标准/评审稿/智慧教学-数据模型标准.md", import.meta.url),
  "utf8",
);
const section = (start, end) => source.split(start)[1].split(end)[0];
const rows = (text) => text.split("\n")
  .filter((line) => line.startsWith("| "))
  .map((line) => line.split("|").slice(1, -1).map((s) => s.trim()));

test("all pipe rows belong to real Markdown tables", () => {
  const orphanRows = marked.lexer(source)
    .filter((token) => token.type === "paragraph" && /^\|/m.test(token.raw));
  assert.deepEqual(orphanRows.map((token) => token.raw), []);
});

test("internal clause references resolve independently of the publication renderer", () => {
  const definitions = new Set([...source.matchAll(
    /^(?:#{2,4} )?([A-E]\.\d+(?:\.\d+)*|\d+\.\d+(?:\.\d+)*)\s/gm,
  )].map((m) => m[1]));
  const unresolved = [];
  for (const [i, line] of source.split("\n").entries()) {
    // These references explicitly belong to an external standard, not this document.
    if (line.startsWith("11.6.3 JY/T 0643")) continue;
    for (const match of line.matchAll(
      /(?<![\w/.\-])([4-9]\.\d+\.\d+(?:\.\d+)*|1[0-2]\.\d+\.\d+(?:\.\d+)*|[A-E]\.\d+(?:\.\d+)*)(?![\w/.\-])/g,
    )) {
      if (!definitions.has(match[1])) unresolved.push(`${i + 1}: ${match[1]}`);
    }
  }
  assert.deepEqual(unresolved, []);
  assert.match(section("| C | 条件", "\n"), /A\.5/);
});

test("chapter 4 and appendix A declare the same nine capability codes", () => {
  const codes = (s) => rows(s).filter((row) => row[0].startsWith("P-"))
    .map((row) => row[0].split(" ")[0]);
  assert.deepEqual(
    codes(section("**表 5 能力 Profile**", "4.2.1.3")),
    codes(section("### A.2 能力 Profile 定义", "### A.3")),
  );
  assert.equal(codes(section("### A.2", "### A.3")).length, 9);
  assert.doesNotMatch(source, /\bP[0-5]\b/);
  assert.match(section("9.3.1 ", "9.3.2"), /接入管理类别/);
  for (const code of codes(section("### A.2", "### A.3"))) {
    assert.ok(rows(section("### A.6", "### A.7")).some((r) => r[0] === code));
  }
});

test("external-reference indexes use unique appendix records and no second adoption level", () => {
  const registry = rows(section("### B.2", "### B.4"))
    .filter((row) => /^B-[ID]\d+$/.test(row[0]));
  const ids = registry.map((row) => row[0]);
  assert.equal(ids.length, new Set(ids).size);
  const index = rows(section("### 2.2", "### 2.4"))
    .filter((row) => /^B-[ID]/.test(row[1] ?? ""));
  assert.equal(index.length, 55);
  for (const row of index) {
    assert.equal(row.length, 3);
    for (const id of row[1].split("、")) assert.ok(ids.includes(id), id);
  }
  const levels = Object.fromEntries(registry.map((r) => [r[0], r[5].split(/[（；]/)[0]]));
  for (const id of ["B-D01", "B-D10", "B-D11", "B-D13", "B-D14", "B-D15", "B-D16", "B-I32"])
    assert.equal(levels[id], "条件强制", id);
  assert.equal(levels["B-I10"], "跟踪");
  assert.equal(levels["B-I34"], "强制");
  assert.equal(levels["B-I36"], "参照");
  assert.equal(levels["B-I37"], "参照");
  // cmi5 Quartz is released; its separate IEEE PAR does not turn that release into a candidate.
  for (const row of registry.filter((r) => /^(?:Public )?Candidate|^IEEE.*PAR/.test(r[3])))
    assert.match(row[5], /^(可选|跟踪)/, row[0]);
});

test("operation and package subcases are defined, used and keep separate expected results", () => {
  const definitions = rows(section("12.3.2 ", "### 12.4"))
    .filter((row) => /^T\d+-[A-Z]$/.test(row[0]));
  assert.deepEqual(definitions.map((r) => r[0]),
    ["T08-P", "T08-C", "T08-A", "T08-R", "T12-T", "T12-R", "T12-O"]);
  const uses = [...source.matchAll(/\bT\d+-[A-Z]\b/g)].map((m) => m[0]);
  for (const use of uses) assert.ok(definitions.some((r) => r[0] === use), use);
  assert.match(definitions.find((r) => r[0] === "T12-T")[2], /不得进入包/);
  assert.match(definitions.find((r) => r[0] === "T12-R")[2], /允许经批准的历史证据/);
  assert.match(definitions.find((r) => r[0] === "T08-P")[2], /服务确认请求拒绝/);
  assert.match(section("### A.6", "### A.7"), /T20.*完整归档与复核由登记主体联合执行/);
});

test("decision dependencies cover contract, course and actual-use gates", () => {
  const decisions = rows(section("E.1 下列事项", "### E.2"));
  const e23 = decisions.find((r) => r[0] === "E23");
  for (const id of ["E23a", "E23b", "E23c"]) {
    assert.ok(e23[1].includes(id));
    assert.ok(rows(source.split("### E.3")[1]).some((r) => r[0].startsWith(id)));
  }
  assert.match(e23[5], /D2/);
  assert.match(e23[5], /开课/);
  assert.match(e23[5], /首次教学反馈或验收用途前/);
  assert.match(decisions.find((r) => r[0] === "E17")[5], /设计冻结时或之前/);
  assert.match(decisions.find((r) => r[0] === "E25")[5], /首次相应复用用途前/);
});
