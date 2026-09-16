import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Standalone output keeps the production Docker image small.
  output: "standalone",
  reactStrictMode: true,
  // The backend base URL is read at runtime in the browser via
  // NEXT_PUBLIC_API_BASE_URL (see lib/api.ts). Server-side rewrites are not
  // used so the SSE EventSource connects to the API directly.
};

export default nextConfig;
