import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  devIndicators: false,
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
