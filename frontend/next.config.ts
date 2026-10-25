import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  /* config options here */
  cacheComponents: true,
  // The browser calls /backend/...; Next forwards it to the API on the same machine.
  // Works in Codespaces without making port 8000 public or setting CORS.
  async rewrites() {
    return [{ source: "/backend/:path*", destination: `${process.env.BACKEND_URL ?? "http://127.0.0.1:8000"}/:path*` }];
  },
  partialPrefetching: true,
  turbopack: {
    rules: {
      "*.css": {
        loaders: ["@tailwindcss/turbopack"],
        as: "*.css",
      },
    },
  },
};

export default nextConfig;
