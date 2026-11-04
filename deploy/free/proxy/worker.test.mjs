import assert from "node:assert/strict";
import test from "node:test";
import { proxy, PUBLIC_ORIGIN, UPSTREAM_ORIGIN } from "./worker.mjs";

function request(path = "/", init = {}) {
  return new Request(PUBLIC_ORIGIN + path, init);
}

test("fixed origin preserves Next/RSC paths, query and headers without reading a response", async () => {
  for (const path of [
    "/my-tasks?_rsc=abc",
    "/_next/static/chunks/app.js",
    "//other.example/path",
  ]) {
    const stream = new ReadableStream({
      start(controller) {
        controller.enqueue(new Uint8Array([1, 2]));
      },
    });
    const upstream = new Response(stream, {
      headers: {
        "Content-Type": "text/x-component",
        Vary: "RSC, Next-Router-State-Tree",
      },
    });
    const result = await proxy(
      request(path, {
        headers: {
          RSC: "1",
          "Next-Router-State-Tree": "encoded",
          "Next-Router-Prefetch": "1",
        },
      }),
      async (url, init) => {
        assert.equal(url.origin, UPSTREAM_ORIGIN);
        assert.equal(url.pathname + url.search, path);
        assert.equal(init.headers.get("RSC"), "1");
        assert.equal(init.headers.get("Next-Router-State-Tree"), "encoded");
        assert.equal(init.headers.get("Next-Router-Prefetch"), "1");
        assert.equal(init.redirect, "manual");
        assert.equal(init.cache, "no-store");
        assert.deepEqual(init.cf, { cacheTtlByStatus: { "100-599": -1 } });
        return upstream;
      },
    );
    assert.equal(result.body, stream);
    assert.equal(upstream.bodyUsed, false);
    assert.equal(result.headers.get("Vary"), "RSC, Next-Router-State-Tree");
    assert.equal(result.headers.get("Cache-Control"), "no-store");
    await result.body.cancel();
  }
});

test("POST streams the original body, cookies and CSRF; hostile Origin stays hostile", async () => {
  const req = request("/api/projects?x=1", {
    method: "POST",
    body: '{"title":"test"}',
    headers: {
      Origin: "https://hostile.example",
      Referer: "https://hostile.example/form",
      Cookie: "sessionid=unit-test",
      "X-CSRFToken": "unit-test-csrf",
      Accept: "application/json",
      "X-Forwarded-Host": "spoof.example",
      "X-Forwarded-For": "1.2.3.4",
      "X-Sipi-Public-Host": "spoof.example",
      "X-Sipi-Client-IP": "1.2.3.4",
      "X-Vercel-Protection-Bypass": "unit-test",
      "X-Vercel-Forwarded-For": "1.2.3.4",
    },
  });
  let calls = 0;
  const response = await proxy(req, async (url, init) => {
    calls++;
    assert.equal(url.href, UPSTREAM_ORIGIN + "/api/projects?x=1");
    assert.equal(init.body, req.body);
    assert.equal(await new Response(init.body).text(), '{"title":"test"}');
    assert.equal(init.headers.get("Cookie"), "sessionid=unit-test");
    assert.equal(init.headers.get("X-CSRFToken"), "unit-test-csrf");
    assert.equal(init.headers.get("Origin"), "https://hostile.example");
    assert.equal(init.headers.get("Referer"), "https://hostile.example/form");
    assert.equal(
      init.headers.get("X-Forwarded-Host"),
      new URL(PUBLIC_ORIGIN).host,
    );
    assert.equal(init.headers.get("X-Forwarded-Proto"), "https");
    for (const name of [
      "X-Sipi-Public-Host",
      "X-Sipi-Client-IP",
      "X-Vercel-Protection-Bypass",
      "X-Vercel-Forwarded-For",
      "X-Forwarded-For",
    ])
      assert.equal(init.headers.has(name), false);
    return new Response(null, { status: 403 });
  });
  assert.equal(response.status, 403);
  assert.equal(calls, 1);
});

test("each session/CSRF cookie remains distinct; only matching origin Domain is removed", async () => {
  const headers = new Headers();
  headers.append(
    "Set-Cookie",
    "sessionid=test; Path=/; HttpOnly; Secure; SameSite=Lax",
  );
  headers.append(
    "Set-Cookie",
    "csrftoken=test; Domain=.sipi-pilot.vercel.app; Expires=Wed, 01 Jan 2031 00:00:00 GMT; Path=/; Secure",
  );
  const result = await proxy(
    request("/api/bootstrap"),
    async () => new Response("{}", { headers }),
  );
  const cookies = result.headers.getSetCookie();
  assert.equal(cookies.length, 2);
  assert.equal(
    cookies[0],
    "sessionid=test; Path=/; HttpOnly; Secure; SameSite=Lax",
  );
  assert.equal(
    cookies[1],
    "csrftoken=test; Expires=Wed, 01 Jan 2031 00:00:00 GMT; Path=/; Secure",
  );
});

test("same-origin redirects stay on Worker; external protection redirects are never followed", async () => {
  for (const [location, expected] of [
    [
      UPSTREAM_ORIGIN + "/login?next=%2Fmy-tasks",
      PUBLIC_ORIGIN + "/login?next=%2Fmy-tasks",
    ],
    ["//sipi-pilot.vercel.app/login", PUBLIC_ORIGIN + "/login"],
    ["/login?next=%2Fmy-tasks", "/login?next=%2Fmy-tasks"],
    ["https://vercel.com/login", "https://vercel.com/login"],
  ]) {
    let calls = 0;
    const result = await proxy(request(), async (_, init) => {
      calls++;
      assert.equal(init.redirect, "manual");
      return new Response(null, {
        status: 307,
        headers: { Location: location },
      });
    });
    assert.equal(result.status, 307);
    assert.equal(result.headers.get("Location"), expected);
    assert.equal(calls, 1);
  }
});

test("HEAD and upstream failures are safe, with no retry or leaked exception data", async () => {
  const head = await proxy(
    request("/api/health", { method: "HEAD" }),
    async () => new Response(null, { headers: { "Content-Encoding": "gzip" } }),
  );
  assert.equal(head.body, null);
  assert.equal(head.headers.get("Content-Encoding"), "gzip");
  let calls = 0;
  const failure = await proxy(request(), async () => {
    calls++;
    throw new Error("unit-test-private-url-and-headers");
  });
  assert.equal(failure.status, 502);
  assert.equal((await failure.text()).includes("unit-test-private"), false);
  assert.equal(calls, 1);
});

test("another public hostname cannot turn this into an open proxy", async () => {
  let calls = 0;
  const result = await proxy(
    new Request("https://other.example/"),
    async () => {
      calls++;
      throw new Error();
    },
  );
  assert.equal(result.status, 421);
  assert.equal(calls, 0);
});
