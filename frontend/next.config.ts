import type { NextConfig } from "next";
import { execFileSync } from "node:child_process";
import { version } from "./package.json";

function buildRevision() {
  const revision = process.env.VERCEL_GIT_COMMIT_SHA || process.env.GITHUB_SHA;
  if (revision && /^[a-f0-9]{40}$/i.test(revision)) return revision.toLowerCase();
  try {
    return execFileSync("git", ["rev-parse", "HEAD"], {
      encoding: "utf8",
      stdio: ["ignore", "pipe", "ignore"],
      timeout: 1000,
    }).trim();
  } catch {
    return "";
  }
}

const nextConfig: NextConfig = {
  devIndicators: false,
  env: {
    NEXT_PUBLIC_SIPI_VERSION: version,
    NEXT_PUBLIC_SIPI_REVISION: buildRevision(),
    NEXT_PUBLIC_SIPI_BUILT_AT: new Date().toISOString(),
    NEXT_PUBLIC_SIPI_ENVIRONMENT: process.env.VERCEL_ENV || "local",
  },
  output: "standalone",
  // Django session bootstrap intentionally gates client-rendered workspace pages.
  experimental: {
    instantInsights: { validationLevel: "manual-warning" },
    // A stale persistent dev graph can loop on "HMR hash mismatch" after updates.
    // Rebuild it on startup; production build caching stays enabled.
    turbopackFileSystemCacheForDev: false,
  },
  cacheComponents: true,
  partialPrefetching: true,
};

export default nextConfig;
