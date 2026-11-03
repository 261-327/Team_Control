import { publicProxyURL, trustedClientIP } from "@/services/server-client-ip";

/** Same-origin bridge: session and CSRF cookies remain on the frontend origin. */
// Cloud inference can outlast the default request timeout; Hobby Fluid allows 300s.
export const maxDuration = 300;
async function proxy(request: Request, context: { params: Promise<{ path: string[] }> }) {
  const { path } = await context.params;
  if (path.some((part) => !part || part === "." || part === ".." || /[\\/\u0000]/.test(part)))
    return Response.json({ error: { message: "Некорректный адрес запроса." } }, { status: 400 });
  if (process.env.SIPI_VERCEL_SERVICES?.toLowerCase() === "true" && !process.env.DJANGO_API_URL)
    return Response.json(
      { error: { message: "Подключение к серверу ещё не настроено." } },
      { status: 503 },
    );
  const base = process.env.DJANGO_API_URL || "http://127.0.0.1:8000";
  // A service binding may include a private path prefix. Keep it when adding API routes.
  const url = new URL(
    `api/${path.map(encodeURIComponent).join("/")}/`,
    `${base.replace(/\/+$/, "")}/`,
  );
  url.search = new URL(request.url).search;
  const headers = new Headers({ Accept: "application/json" });
  for (const name of ["cookie", "x-csrftoken", "content-type", "origin", "referer"])
    if (request.headers.has(name)) headers.set(name, request.headers.get(name)!);
  // Replace caller-supplied forwarding headers. Django trusts these only in Services mode.
  const publicUrl = publicProxyURL(request.url);
  if (!publicUrl)
    return Response.json(
      { error: { message: "Публичный адрес сайта ещё не настроен." } },
      { status: 503 },
    );
  headers.set("x-forwarded-host", publicUrl.host);
  headers.set("x-forwarded-proto", publicUrl.protocol.slice(0, -1));
  const clientIP = trustedClientIP(request.headers);
  if (clientIP) headers.set("x-sipi-client-ip", clientIP);
  const inference = path.length === 1 && path[0] === "assistant" && request.method === "POST";
  try {
    const upstream = await fetch(url, {
      method: request.method,
      headers,
      body: ["GET", "HEAD"].includes(request.method) ? undefined : await request.text(),
      cache: "no-store",
      redirect: "manual",
      signal: AbortSignal.timeout(inference ? 280000 : 90000),
    });
    const responseHeaders = new Headers({
      "Content-Type": upstream.headers.get("content-type") || "application/json",
      "Cache-Control": "no-store",
      Vary: "Cookie",
    });
    for (const cookie of upstream.headers.getSetCookie())
      responseHeaders.append("Set-Cookie", cookie);
    return new Response(request.method === "HEAD" ? null : await upstream.arrayBuffer(), {
      status: upstream.status,
      headers: responseHeaders,
    });
  } catch {
    return Response.json(
      {
        error: {
          code: "unavailable",
          message: "Не удалось связаться с сервером. Попробуйте ещё раз.",
        },
      },
      { status: 503 },
    );
  }
}
export {
  proxy as GET,
  proxy as POST,
  proxy as PATCH,
  proxy as DELETE,
  proxy as PUT,
  proxy as HEAD,
};
