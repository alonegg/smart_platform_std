const keyCache = new Map();
const decode = (part) =>
  Uint8Array.from(atob(part.replace(/-/g, "+").replace(/_/g, "/")), (char) =>
    char.charCodeAt(0),
  );
const parse = (part) => JSON.parse(new TextDecoder().decode(decode(part)));

export async function verifyAccess(request, env, fetchKeys = fetch) {
  const token = request.headers.get("Cf-Access-Jwt-Assertion");
  if (
    !token ||
    token.length > 12000 ||
    !env.ACCESS_AUD ||
    !/^[a-z0-9-]+\.cloudflareaccess\.com$/.test(env.ACCESS_TEAM_DOMAIN ?? "")
  )
    return null;
  try {
    const parts = token.split(".");
    if (parts.length !== 3) return null;
    const header = parse(parts[0]);
    const claims = parse(parts[1]);
    const now = Date.now() / 1000;
    const issuer = `https://${env.ACCESS_TEAM_DOMAIN}`;
    if (
      header.alg !== "RS256" ||
      typeof header.kid !== "string" ||
      header.kid.length > 200 ||
      claims.iss !== issuer ||
      !Array.isArray(claims.aud) ||
      !claims.aud.includes(env.ACCESS_AUD) ||
      !Number.isFinite(claims.exp) ||
      claims.exp <= now ||
      (claims.nbf !== undefined &&
        (!Number.isFinite(claims.nbf) || claims.nbf > now + 30)) ||
      typeof claims.email !== "string" ||
      claims.email.toLowerCase() !== env.ADMIN_EMAIL?.toLowerCase()
    )
      return null;
    let cached = keyCache.get(issuer);
    if (
      !cached ||
      cached.expires < Date.now() ||
      !cached.keys.some((key) => key.kid === header.kid)
    ) {
      const response = await fetchKeys(`${issuer}/cdn-cgi/access/certs`, {
        signal: AbortSignal.timeout(5000),
      });
      if (!response.ok) return null;
      const jwks = await response.json();
      if (!Array.isArray(jwks.keys) || jwks.keys.length > 30) return null;
      cached = { keys: jwks.keys, expires: Date.now() + 300000 };
      keyCache.set(issuer, cached);
    }
    const jwk = cached.keys.find(
      (key) =>
        key.kid === header.kid &&
        key.kty === "RSA" &&
        (!key.alg || key.alg === "RS256"),
    );
    if (!jwk) return null;
    const key = await crypto.subtle.importKey(
      "jwk",
      jwk,
      { name: "RSASSA-PKCS1-v1_5", hash: "SHA-256" },
      false,
      ["verify"],
    );
    const valid = await crypto.subtle.verify(
      "RSASSA-PKCS1-v1_5",
      key,
      decode(parts[2]),
      new TextEncoder().encode(`${parts[0]}.${parts[1]}`),
    );
    return valid ? { email: claims.email } : null;
  } catch {
    return null;
  }
}
