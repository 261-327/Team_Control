import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  devIndicators: false,
  output: "standalone",
  // Django session bootstrap intentionally gates client-rendered workspace pages.
  experimental: { instantInsights: { validationLevel: "manual-warning" } },
  cacheComponents: true,
  partialPrefetching: true,
};

export default nextConfig;
