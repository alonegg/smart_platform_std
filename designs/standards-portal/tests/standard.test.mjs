import test from "node:test";
import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import { marked } from "marked";

const source = await readFile(
  new URL("../../../标准/评审稿/智慧教学-数据模型标准.md", import.meta.url),
  "utf8",
);
const section = (start, end) => {
  const escape = (text) => text.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  const match = new RegExp(`^${escape(start)}`, "m").exec(source);
  assert.ok(match, `missing section start: ${start}`);
  const rest = source.slice(match.index + match[0].length);
  const endAt = end === "\n" ? rest.indexOf("\n") : rest.search(new RegExp(`^${escape(end)}`, "m"));
  assert.ok(endAt >= 0, `missing section end: ${end}`);
  return rest.slice(0, endAt);
};
const rows = (text) => text.split("\n")
  .filter((line) => line.startsWith("| "))
  .map((line) => line.split("|").slice(1, -1).map((s) => s.trim()));

const matrixCells = (text) => {
  const cells = new Map();
  let groups = [];
  for (const row of rows(text)) {
    if (row[0] === "Profile") groups = row.slice(1);
    if (!row[0].startsWith("P-")) continue;
    const code = row[0].split(" ")[0];
    assert.equal(row.length - 1, groups.length, code);
    for (let i = 0; i < groups.length; i++) {
      const key = `${code}/${groups[i]}`;
      assert.ok(!cells.has(key), `duplicate matrix cell: ${key}`);
      cells.set(key, row[i + 1]);
    }
  }
  return cells;
};

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
      // "表 A.9" etc. are appendix table numbers (GB/T 1.1 style), not clause references.
      /(?<![\w/.\-])(?<!表 )([4-9]\.\d+\.\d+(?:\.\d+)*|1[0-2]\.\d+\.\d+(?:\.\d+)*|[A-E]\.\d+(?:\.\d+)*)(?![\w/.\-])/g,
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
    codes(section("表 4-3 能力 Profile", "4.2.1.3")),
    codes(section("### A.2 能力 Profile 定义", "### A.3")),
  );
  assert.equal(codes(section("### A.2", "### A.3")).length, 9);
  assert.doesNotMatch(source, /\bP[0-5]\b/);
  assert.match(section("9.3.1 ", "9.3.2"), /接入管理类别/);
  for (const code of codes(section("### A.2", "### A.3"))) {
    assert.ok(rows(section("### A.6", "### A.7")).some((r) => r[0] === code));
  }
});

test("common mandatory requirements do not mask specialized conditional cells", () => {
  const cells = matrixCells(section("### A.4 适用矩阵", "### A.5"));
  assert.equal(cells.size, 288);
  const masked = [...cells.entries()].filter(([key, level]) => {
    const [code, group] = key.split("/");
    return code !== "P-COM" && level === "C" && cells.get(`P-COM/${group}`) === "M";
  });
  assert.deepEqual(masked, [], "a false C condition must not silently remain M through P-COM");
  for (const key of ["P-RES/11-C", "P-RSB/12-A", "P-RSB/12-B"])
    assert.equal(cells.get(key), "M", key);
  const conditions = rows(section("### A.5", "### A.6"));
  assert.ok(!conditions.some((row) => row[0] === "11-C"));
  assert.ok(!conditions.some((row) => row[0] === "12-A、12-B"));
});

test("external-reference indexes use unique appendix records and no second adoption level", () => {
  const registry = rows(section("### B.2", "### B.4"))
    .filter((row) => /^B-[ID]\d+[a-z]?$/.test(row[0]));
  const ids = registry.map((row) => row[0]);
  assert.equal(ids.length, new Set(ids).size);
  const index = rows(section("### 2.2", "### 2.4"))
    .filter((row) => /^B-[ID]/.test(row[1] ?? ""));
  assert.equal(index.length, 54);
  for (const row of index) {
    assert.equal(row.length, 3);
    for (const id of row[1].split("、")) assert.ok(ids.includes(id), id);
  }
  const levels = Object.fromEntries(registry.map((r) => [r[0], r[5].split(/[（；]/)[0]]));
  for (const id of ["B-D01", "B-D10", "B-D11", "B-D13", "B-D14", "B-D15", "B-D16b", "B-I32"])
    assert.equal(levels[id], "条件强制", id);
  for (const id of ["B-D16a", "B-D20b"]) assert.equal(levels[id], "参照", id);
  assert.equal(levels["B-D20a"], "强制");
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
    ["T08-P", "T08-C", "T08-A", "T08-R", "T12-T", "T12-R", "T12-O", "T20-F", "T20-L", "T20-E"]);
  const uses = [...source.matchAll(/\bT\d+-[A-Z]\b/g)].map((m) => m[0]);
  for (const use of uses) assert.ok(definitions.some((r) => r[0] === use), use);
  assert.match(definitions.find((r) => r[0] === "T12-T")[2], /不应进入包/);
  assert.match(definitions.find((r) => r[0] === "T12-R")[2], /允许经批准的历史证据/);
  assert.match(definitions.find((r) => r[0] === "T08-P")[2], /服务确认请求拒绝/);
  assert.match(section("### A.6", "### A.7"), /T20.*完整归档与复核由登记主体联合执行/);
});

test("duplicate receipts expose processing state without claiming business completion", () => {
  const retry = section("7.6.2 ", "7.6.3 ");
  const receipt = section("8.7.1 ", "8.7.2 ");
  assert.match(retry, /duplicate/);
  assert.match(retry, /(?:不独立|不单独|不能独立|不表示|不证明)/);
  assert.match(retry, /(?:处理状态|处理结果)/);
  assert.match(retry, /持久化/);
  assert.match(retry, /(?:拒收|rejected)/);
  assert.match(retry, /(?:隔离|quarantined)/);
  assert.match(retry, /(?:修复|纠正)[\s\S]*重新验证/);
  assert.match(retry, /conflict/);
  assert.match(receipt, /duplicate/);
  assert.match(receipt, /(?:原事实|源事实)/);
  assert.match(receipt, /(?:处理状态|处理结果)/);
  assert.match(receipt, /持久化/);
});

test("T20 distinguishes lawful evidence limits from failed business review", () => {
  const cases = rows(section("12.3.4 ", "### 12.4"));
  const find = (code) => {
    const row = cases.find((item) => item[0] === code);
    assert.ok(row, `${code} must have an explicit input and expected result`);
    assert.ok(row.length >= 3, code);
    return row.join(" ");
  };
  const complete = find("T20-F");
  assert.match(complete, /合法/);
  assert.match(complete, /(?:获准|获授权)/);
  for (const evidence of ["考核方案", "量规", "作品", "反馈", "评分决定"])
    assert.ok(complete.includes(evidence), evidence);
  assert.match(complete, /重建.*(?:当时依据|历史依据)/);
  const limited = find("T20-L");
  assert.match(limited, /(?:合法删除|依法删除|(?:已核验|有效).*处置决定.*(?:删除|限制))/);
  assert.match(limited, /(?:不表示|不能证明|不代表).*个案.*(?:判分|完整.*复核)/);
  assert.match(limited, /(?:复核流程|教学复核)/);
  const exceptional = find("T20-E");
  assert.match(exceptional, /异常(?:证据)?丢失/);
  assert.match(exceptional, /越权恢复/);
  assert.match(exceptional, /(?:负向|正确识别|拒绝)/);
  assert.match(exceptional, /(?:个案|业务)[\s\S]*(?:不通过|不予通过|不得|不应)/);
  const summary = rows(section("表 12-1", "12.3.2 ")).find((row) => row[0].startsWith("T20 "));
  assert.ok(summary, "T20 summary must exist");
  assert.ok(summary.some((cell) => cell.includes("12.3.4")));
  const grading = rows(section("### A.6", "### A.7")).find((row) => row[0] === "P-GRD");
  assert.ok(grading, "P-GRD test selection must exist");
  assert.ok(grading.some((cell) => cell.includes("12.3.4")));
});

test("scenario contracts route to existing T cases and preserve capability-scoped execution", () => {
  const design = section("12.3.5 ", "### 12.4");
  assert.match(design, /按实际能力/);
  assert.match(design, /未声明/);
  assert.match(design, /不代替执行证据/);
  const cases = rows(design).filter((row) => /^T\d{2}/.test(row[0]));
  assert.equal(cases.length, 9);
  const defined = new Set(rows(section("表 12-1", "12.3.2 "))
    .map((row) => row[0].match(/^T(\d{2}) /)?.[1]).filter(Boolean));
  assert.equal(defined.size, 26);
  for (const row of cases) {
    assert.equal(row.length, 3);
    assert.ok(row[1].length && row[2].length, row[0]);
    for (const match of row[0].matchAll(/T(\d{2})(?:[—–-]T(\d{2}))?/g)) {
      const from = Number(match[1]);
      const to = Number(match[2] ?? match[1]);
      assert.ok(from <= to, row[0]);
      for (let i = from; i <= to; i++)
        assert.ok(defined.has(String(i).padStart(2, "0")), `undefined scenario target T${i}`);
    }
  }
  for (const topic of ["初修", "服务端字段", "仿真", "补录", "量规", "撤权", "处置", "方法", "原应用"])
    assert.ok(cases.some((row) => row[1].includes(topic)), topic);
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
