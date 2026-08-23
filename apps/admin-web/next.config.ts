import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Produces .next/standalone (a self-contained server.js + the minimal
  // node_modules subset it actually needs) -- required by
  // infrastructure/docker/admin-web-prod/Dockerfile's runtime stage, which
  // copies only that output rather than shipping full node_modules into
  // the production image. See docs/DEPLOYMENT.md.
  output: "standalone",
};

export default nextConfig;
