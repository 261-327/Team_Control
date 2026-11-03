import assert from "node:assert/strict";
import test from "node:test";
import { publicProxyURL, trustedClientIP } from "../src/services/server-client-ip.ts";

const deployed = { VERCEL: "1", SIPI_VERCEL_SERVICES: "true" };

test("uses only a Vercel platform IP in the explicitly enabled profile", () => {
  const headers = new Headers({
    "x-vercel-forwarded-for": "198.51.100.24",
    "x-forwarded-for": "203.0.113.99",
    "x-sipi-client-ip": "203.0.113.98",
  });
  assert.equal(trustedClientIP(headers, deployed), "198.51.100.24");
  assert.equal(trustedClientIP(headers, { SIPI_VERCEL_SERVICES: "true" }), null);
  assert.equal(trustedClientIP(headers, { VERCEL: "1" }), null);
  headers.delete("x-vercel-forwarded-for");
  assert.equal(trustedClientIP(headers, deployed), null);
});

test("canonicalizes IPv6 and rejects lists, zones, ports and malformed addresses", () => {
  assert.equal(
    trustedClientIP(new Headers({ "x-vercel-forwarded-for": "2001:0DB8:0:0::1" }), deployed),
    "2001:db8::1",
  );
  for (const value of ["1.2.3.4, 5.6.7.8", "fe80::1%eth0", "198.51.100.1:80", "anything"])
    assert.equal(trustedClientIP(new Headers({ "x-vercel-forwarded-for": value }), deployed), null);
});

test("Services uses the configured public origin or stable production domain", () => {
  const privateURL = "http://backend.private.internal/binding/api/bootstrap";
  const env = { SIPI_VERCEL_SERVICES: "true", VERCEL_PROJECT_PRODUCTION_URL: "sipi.vercel.app" };
  assert.equal(publicProxyURL(privateURL, env)?.origin, "https://sipi.vercel.app");
  assert.equal(
    publicProxyURL(privateURL, { ...env, FRONTEND_URL: "https://uni.example.test/" })?.origin,
    "https://uni.example.test",
  );
  assert.equal(publicProxyURL(privateURL, { SIPI_VERCEL_SERVICES: "true" }), null);
  assert.equal(
    publicProxyURL("http://localhost:3000/api/bootstrap", {})?.origin,
    "http://localhost:3000",
  );
});

test("Services never forwards an invalid configured public host", () => {
  for (const origin of [
    "http://site.example",
    "https://user:pass@site.example",
    "https://site.example/path",
    "https://*.example",
    "https://localhost",
  ])
    assert.equal(
      publicProxyURL("http://private.internal/api/bootstrap", {
        SIPI_VERCEL_SERVICES: "true",
        FRONTEND_URL: origin,
      }),
      null,
    );
});
