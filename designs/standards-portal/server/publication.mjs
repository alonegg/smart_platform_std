const notice = "网站正在更新，当前审阅版本已冻结。更新期间暂停公开阅读、全文检索与文稿下载。";

const page = `<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <meta name="robots" content="noindex, nofollow" />
  <meta name="description" content="${notice}" />
  <title>暂停发布 · 智慧教学-数据模型标准</title>
  <style>
    :root { color-scheme: light; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "PingFang SC", "Microsoft YaHei", sans-serif; color: #193331; background: #f4f5f0; }
    * { box-sizing: border-box; }
    body { margin: 0; min-height: 100svh; display: flex; flex-direction: column; }
    header, footer { width: min(960px, 100%); margin: 0 auto; padding: 30px 28px; }
    header { font-size: 16px; font-weight: 600; letter-spacing: .04em; }
    main { width: min(760px, 100%); margin: auto; padding: 64px 28px 88px; }
    .status { display: inline-block; padding: 7px 12px; border: 1px solid #b8cbc3; border-radius: 3px; color: #315b4d; font-size: 13px; letter-spacing: .08em; }
    h1 { margin: 28px 0 24px; font-size: clamp(32px, 6vw, 52px); font-weight: 600; letter-spacing: -.03em; line-height: 1.25; }
    p { margin: 0 0 18px; font-size: 17px; line-height: 1.9; }
    .lead { font-size: 21px; font-weight: 500; }
    .detail { max-width: 35em; color: #4b625c; }
    .boundary { margin-top: 36px; padding-top: 24px; border-top: 1px solid #d4ddd4; color: #4b625c; font-size: 14px; }
    footer { color: #4b625c; font-size: 13px; line-height: 1.8; }
  </style>
</head>
<body>
  <header>智慧教学-数据模型标准</header>
  <main>
    <span class="status">正在更新 · 审阅版本冻结</span>
    <h1>网站暂停发布</h1>
    <p class="lead">当前审阅版本已冻结，网站内容正在更新。</p>
    <p class="detail">更新期间暂停公开阅读、全文检索与文稿下载。恢复发布后，请以本站重新开放的审阅版本为准。</p>
    <p class="boundary">本文件仍为征求意见稿。审阅版本冻结不表示标准已经审定发布。</p>
  </main>
  <footer>感谢理解，请待更新完成后再访问。</footer>
</body>
</html>`;

export function publicationPausedResponse(request) {
  const { pathname } = new URL(request.url);
  const headers = {
    "Cache-Control": "no-store, max-age=0",
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "no-referrer",
    "X-Robots-Tag": "noindex, nofollow",
    "Content-Security-Policy": "default-src 'none'; style-src 'unsafe-inline'; base-uri 'none'; frame-ancestors 'none'; form-action 'none'",
  };
  const robots = pathname === "/robots.txt";
  const machine = pathname.startsWith("/api/") || pathname === "/version.json";
  const body = robots
    ? "User-agent: *\nDisallow: /\n"
    : machine
      ? JSON.stringify({ status: "publication_paused", reviewStatus: "frozen", message: notice })
      : page;
  return new Response(request.method === "HEAD" ? null : body, {
    status: robots ? 200 : 503,
    headers: {
      ...headers,
      ...(robots ? {} : { "Retry-After": "3600" }),
      "Content-Type": robots
        ? "text/plain; charset=utf-8"
        : machine
          ? "application/json; charset=utf-8"
          : "text/html; charset=utf-8",
    },
  });
}
