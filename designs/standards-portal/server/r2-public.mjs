import documentInfo from "./document-info.json" with { type: "json" };

const unpublishedPaths = /^\/(admin|api|comment|compare|privacy|responses)(?:\/|$)/i;

export async function servePublicDraft(request, assets, path, enabled = true) {
  let response;
  if (!enabled) {
    response = new Response("只读版本配置错误。", { status: 503 });
  } else if (unpublishedPaths.test(path)) {
    response = new Response("页面未找到。", { status: 404 });
  } else if (request.method !== "GET" && request.method !== "HEAD") {
    response = new Response("此网站仅提供阅读。", {
      status: 405,
      headers: { Allow: "GET, HEAD" },
    });
  } else {
    response = await assets.fetch(request);
  }
  const result = new Response(request.method === "HEAD" ? null : response.body, response);
  result.headers.set("X-Robots-Tag", "noindex");
  result.headers.set("Cache-Control", "no-store");
  return result;
}

export default {
  fetch(request, env) {
    return servePublicDraft(
      request,
      env.ASSETS,
      new URL(request.url).pathname,
      documentInfo.edition === "r2-public",
    );
  },
};
