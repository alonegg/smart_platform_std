import { mkdir, readFile, writeFile, rm } from "node:fs/promises";
import { execFileSync } from "node:child_process";
import path from "node:path";
import { build } from "esbuild";
import { pathToFileURL } from "node:url";
import { generateContent, project, root } from "./content.mjs";
const data = await generateContent();
await writeFile(
  path.join(project, "server/document-info.json"),
  JSON.stringify({ sourceSha: data.sourceSha256 }),
);
execFileSync(path.join(project, "node_modules/.bin/vite"), ["build"], {
  cwd: project,
  stdio: "inherit",
});
const scratch = path.join(root, "temp/portal-ssr");
await mkdir(scratch, { recursive: true });
try {
  await build({
    entryPoints: [path.join(project, "src/prerender.jsx")],
    bundle: true,
    platform: "node",
    format: "cjs",
    outfile: path.join(scratch, "render.cjs"),
    define: { "process.env.NODE_ENV": '"production"' },
    logLevel: "warning",
  });
  const { render, routes } = await import(
    pathToFileURL(path.join(scratch, "render.cjs"))
  );
  const template = await readFile(
    path.join(project, "dist/index.html"),
    "utf8",
  );
  const titles = {
    "/": "阅读指南",
    "/architecture/": "三层架构",
    "/profiles/": "能力适用矩阵",
    "/roadmap/": "实施路线",
    "/decisions/": "待决事项",
    "/downloads/": "资料下载",
    "/privacy/": "阅读登记隐私说明",
    "/admin/": "阅读者登记管理",
  };
  for (const route of [...routes, "/admin/", "/404/"]) {
    const section = data.sections.find((s) => route === `/read/${s.key}/`);
    const title = `${section?.title ?? titles[route] ?? "页面未找到"} · ${data.title}`;
    const html = template
      .replace('<div id="root"></div>', `<div id="root">${render(route)}</div>`)
      .replace(/<title>[^<]*<\/title>/, `<title>${title}</title>`)
      .replace(
        "</head>",
        `<link rel="canonical" href="https://stds.chunlin.ch${route}" /></head>`,
      );
    const output =
      route === "/404/"
        ? path.join(project, "dist/404.html")
        : path.join(project, "dist", route, "index.html");
    await mkdir(path.dirname(output), { recursive: true });
    await writeFile(output, html);
  }
  await writeFile(
    path.join(project, "dist/sitemap.xml"),
    `<?xml version="1.0" encoding="UTF-8"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">${routes.map((route) => `<url><loc>https://stds.chunlin.ch${route}</loc></url>`).join("")}</urlset>`,
  );
  await writeFile(
    path.join(project, "dist/robots.txt"),
    "User-agent: *\nAllow: /\nSitemap: https://stds.chunlin.ch/sitemap.xml\n",
  );
  console.info(
    `Prerendered ${routes.length} pages; ${data.sections.length} source sections; ${data.pending.length} pending decisions.`,
  );
} finally {
  await rm(scratch, { recursive: true, force: true });
}
