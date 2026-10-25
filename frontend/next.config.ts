import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  /* config options here */
  cacheComponents: true,
  partialPrefetching: true,
  // The browser calls /backend/...; Next forwards it to the API on the same machine.
  // Works in Codespaces without making port 8000 public or setting CORS.
  async rewrites() {
    return [{ source: "/backend/:path*", destination: `${process.env.BACKEND_URL ?? "http://127.0.0.1:8000"}/:path*` }];
  },
  turbopack: {
    // A stray package-lock.json outside this repo made Next guess the wrong workspace root.
    root: import.meta.dirname,
    rules: {
      "*.css": {
        loaders: ["@tailwindcss/turbopack"],
        as: "*.css",
      },
    },
  },
};

export default nextConfig;
