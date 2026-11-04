import { isIP } from "node:net";

/** Vercel overwrites this platform header. Caller-supplied Sipi/XFF are ignored. */
export function trustedClientIP(
  headers: Headers,
  env: NodeJS.ProcessEnv = process.env,
): string | null {
  if (env.VERCEL !== "1" || env.SIPI_VERCEL_SERVICES?.toLowerCase() !== "true") return null;
  const value = headers.get("x-vercel-forwarded-for")?.trim();
  if (!value || value.includes("%") || !isIP(value)) return null;
  if (isIP(value) === 4) return value;
  // URL parsing compresses/lowercases a single IPv6 address; lists and zones fail above.
  return new URL(`https://[${value}]/`).hostname.slice(1, -1);
}

/** Match Django's primary origin; a private binding URL is never a public fallback. */
export function publicProxyURL(
  requestURL: string,
  env: NodeJS.ProcessEnv = process.env,
): URL | null {
  const services = env.SIPI_VERCEL_SERVICES?.toLowerCase() === "true";
  const explicit = env.FRONTEND_URL?.trim();
  const productionHost = env.VERCEL_PROJECT_PRODUCTION_URL?.trim();
  const source = explicit || (services && productionHost ? `https://${productionHost}` : "");
  if (services && !source) return null;
  try {
    const url = new URL(source || requestURL);
    if (
      services &&
      (url.protocol !== "https:" ||
        url.username ||
        url.password ||
        url.pathname !== "/" ||
        url.search ||
        url.hash ||
        url.port ||
        url.hostname.includes("*") ||
        url.hostname.startsWith(".") ||
        ["localhost", "127.0.0.1"].includes(url.hostname))
    )
      return null;
    return url;
  } catch {
    return null;
  }
}
