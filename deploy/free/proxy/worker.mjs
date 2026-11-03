/** One public hostname -> one fixed Vercel origin. No credentials, logs or cache. */
export const PUBLIC_ORIGIN = "https://sipi.prettiqs.workers.dev";
export const UPSTREAM_ORIGIN = "https://sipi-pilot.vercel.app";

const METHODS = new Set([
  "GET",
  "HEAD",
  "POST",
  "PUT",
  "PATCH",
  "DELETE",
  "OPTIONS",
]);
const HOP_HEADERS = new Set([
  "connection",
  "keep-alive",
  "proxy-authenticate",
  "proxy-authorization",
  "te",
  "trailer",
  "transfer-encoding",
  "upgrade",
]);

function failure(message, status) {
  return Response.json(
    { error: { message } },
    {
      status,
      headers: { "Cache-Control": "no-store" },
    },
  );
}

function cleanRequestHeaders(request) {
  const headers = new Headers(request.headers);
  // Neither caller forwarding metadata nor private bridge/protection headers are trusted.
  for (const name of [...headers.keys()]) {
    if (
      HOP_HEADERS.has(name) ||
      name === "host" ||
      name === "forwarded" ||
      name === "x-real-ip" ||
      name.startsWith("x-forwarded-") ||
      name.startsWith("x-sipi-") ||
      name.startsWith("x-vercel-")
    )
      headers.delete(name);
  }
  const publicURL = new URL(PUBLIC_ORIGIN);
  headers.set("x-forwarded-host", publicURL.host);
  headers.set("x-forwarded-proto", "https");
  // Origin, Referer, Cookie, CSRF, Accept and all Next/RSC routing headers stay intact.
  return headers;
}

function rewriteLocation(value) {
  if (!value || !/^(?:https?:)?\/\//i.test(value)) return value;
  try {
    const target = new URL(value, UPSTREAM_ORIGIN);
    if (target.origin !== UPSTREAM_ORIGIN) return value;
    const publicURL = new URL(PUBLIC_ORIGIN);
    target.protocol = publicURL.protocol;
    target.host = publicURL.host;
    return target.href;
  } catch {
    return value;
  }
}

function responseCookies(headers) {
  // Workers retains separate cookie headers (Expires contains commas).
  if (typeof headers.getAll === "function") return headers.getAll("Set-Cookie");
  return headers.getSetCookie(); // Standard equivalent used by the local Node tests.
}

function publicCookie(cookie) {
  const originHost = new URL(UPSTREAM_ORIGIN).hostname;
  return cookie
    .split(";")
    .filter((part, index) => {
      if (index === 0) return true;
      const match = /^\s*domain\s*=\s*"?\.?([^";\s]+)"?\s*$/i.exec(part);
      // A cookie scoped to Vercel becomes host-only on the public Worker hostname.
      return !match || match[1].toLowerCase() !== originHost;
    })
    .join(";");
}

export async function proxy(request, fetchOrigin = fetch) {
  const incoming = new URL(request.url);
  if (incoming.origin !== PUBLIC_ORIGIN)
    return failure("Адрес прокси не настроен.", 421);
  if (!METHODS.has(request.method))
    return failure("Метод не поддерживается.", 405);
  if (request.headers.get("upgrade"))
    return failure("Этот прокси поддерживает HTTP.", 501);

  // Assign path/search as fields: even //other-host paths cannot change the fixed origin.
  const upstreamURL = new URL(UPSTREAM_ORIGIN);
  upstreamURL.pathname = incoming.pathname;
  upstreamURL.search = incoming.search;
  let upstream;
  try {
    upstream = await fetchOrigin(upstreamURL, {
      method: request.method,
      headers: cleanRequestHeaders(request),
      body: ["GET", "HEAD"].includes(request.method) ? undefined : request.body,
      redirect: "manual", // Never send cookies/auth onward to a redirect destination.
      cache: "no-store",
      cf: { cacheTtlByStatus: { "100-599": -1 } },
      signal: request.signal,
    });
  } catch {
    // Do not expose URLs, headers, bodies or provider errors containing private data.
    return failure("Сервер временно недоступен. Попробуйте ещё раз.", 502);
  }

  const headers = new Headers(upstream.headers);
  for (const name of HOP_HEADERS) headers.delete(name);
  const cookies = responseCookies(upstream.headers);
  headers.delete("Set-Cookie");
  for (const cookie of cookies)
    headers.append("Set-Cookie", publicCookie(cookie));
  for (const name of ["Location", "Content-Location"])
    if (headers.has(name))
      headers.set(name, rewriteLocation(headers.get(name)));
  headers.delete("Vercel-CDN-Cache-Control");
  headers.set("Cache-Control", "no-store");
  headers.set("CDN-Cache-Control", "no-store");
  headers.set("Cloudflare-CDN-Cache-Control", "no-store");
  // Body and Content-Encoding are passed through unchanged: SSR/RSC/images stream.
  return new Response(request.method === "HEAD" ? null : upstream.body, {
    status: upstream.status,
    statusText: upstream.statusText,
    headers,
  });
}

export default { fetch: (request) => proxy(request) };
