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
  // Vercel replaces standard forwarding headers on private service calls. This
  // separate header is synthesized here and checked against Django's exact hosts.
  if (process.env.SIPI_VERCEL_SERVICES?.toLowerCase() === "true")
    headers.set("x-sipi-public-host", publicUrl.host);
  headers.set("x-forwarded-host", publicUrl.host);
  headers.set("x-forwarded-proto", publicUrl.protocol.slice(0, -1));
  const clientIP = trustedClientIP(request.headers);
  if (clientIP) headers.set("x-sipi-client-ip", clientIP);
  const inference = path.length === 1 && path[0] === "assistant" && request.method === "POST";
  try {
    const body = ["GET", "HEAD"].includes(request.method)
      ? undefined
      : await readRequestBody(request);
    if (body === null)
      return Response.json(
        { error: { code: "file_too_large", message: "Размер файла должен быть до 3 МБ." } },
        { status: 413 },
      );
    const upstream = await fetch(url, {
      method: request.method,
      headers,
      body,
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
    for (const name of ["Content-Disposition", "X-Content-Type-Options"])
      if (upstream.headers.has(name)) responseHeaders.set(name, upstream.headers.get(name)!);
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

async function readRequestBody(request: Request): Promise<ArrayBuffer | null> {
  const limit = 4 * 1024 * 1024;
  if (Number(request.headers.get("content-length")) > limit) return null;
  if (!request.body) return new ArrayBuffer(0);
  const reader = request.body.getReader();
  const chunks: Uint8Array[] = [];
  let size = 0;
  while (true) {
    const { value, done } = await reader.read();
    if (done) break;
    size += value.byteLength;
    if (size > limit) {
      await reader.cancel();
      return null;
    }
    chunks.push(value);
  }
  const buffer = new Uint8Array(size);
  let offset = 0;
  for (const chunk of chunks) {
    buffer.set(chunk, offset);
    offset += chunk.byteLength;
  }
  return buffer.buffer;
}
