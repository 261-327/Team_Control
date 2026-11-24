import { test, expect } from "@playwright/test";
import { GET } from "../src/app/api/[...path]/route";

for (const status of [405, 429]) {
  test(`proxy retains protocol/security headers and separate cookies for ${status}`, async () => {
    const savedFetch = globalThis.fetch;
    const savedServices = process.env.SIPI_VERCEL_SERVICES;
    process.env.SIPI_VERCEL_SERVICES = "false";
    globalThis.fetch = async () => {
      const headers = new Headers({
        Allow: "GET, POST",
        "Retry-After": "60",
        "X-Frame-Options": "DENY",
        "X-Content-Type-Options": "nosniff",
        "X-Internal-Secret": "not-for-client",
      });
      headers.append("Set-Cookie", "a=1; HttpOnly; SameSite=Lax");
      headers.append("Set-Cookie", "b=2; SameSite=Lax");
      return new Response(JSON.stringify({ error: { message: "Тестовый отказ" } }), {
        status,
        headers,
      });
    };
    try {
      const response = await GET(new Request("http://127.0.0.1/api/bootstrap"), {
        params: Promise.resolve({ path: ["bootstrap"] }),
      });
      expect(response.status).toBe(status);
      expect(response.headers.get("allow")).toBe("GET, POST");
      expect(response.headers.get("retry-after")).toBe("60");
      expect(response.headers.get("x-frame-options")).toBe("DENY");
      expect(response.headers.get("x-content-type-options")).toBe("nosniff");
      expect(response.headers.getSetCookie()).toHaveLength(2);
      expect(response.headers.has("x-internal-secret")).toBe(false);
      expect(response.headers.get("cache-control")).toBe("no-store");
    } finally {
      globalThis.fetch = savedFetch;
      if (savedServices === undefined) delete process.env.SIPI_VERCEL_SERVICES;
      else process.env.SIPI_VERCEL_SERVICES = savedServices;
    }
  });
}
