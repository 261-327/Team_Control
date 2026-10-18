/** Same-origin bridge: session and CSRF cookies remain on the frontend origin. */
async function proxy(request: Request, context: { params: Promise<{ path: string[] }> }) {
  const { path } = await context.params;
  if (path.some((part) => !part || part === "." || part === ".." || /[\\/\u0000]/.test(part)))
    return Response.json({ error: { message: "Некорректный адрес запроса." } }, { status: 400 });
  const base = process.env.DJANGO_API_URL || "http://127.0.0.1:8000";
  const url = new URL(`/api/${path.map(encodeURIComponent).join("/")}/`, base);
  url.search = new URL(request.url).search;
  const headers = new Headers({ Accept: "application/json" });
  for (const name of ["cookie", "x-csrftoken", "content-type", "origin", "referer"])
    if (request.headers.has(name)) headers.set(name, request.headers.get(name)!);
  try {
    const upstream = await fetch(url, {
      method: request.method,
      headers,
      body: ["GET", "HEAD"].includes(request.method) ? undefined : await request.text(),
      cache: "no-store",
      redirect: "manual",
      signal: AbortSignal.timeout(30000),
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
