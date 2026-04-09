import type { NextConfig } from "next";

const isStaticExport = process.env.STATIC_EXPORT === "true";

const nextConfig: NextConfig = {
  serverExternalPackages: ["child_process"],
  // For the GitHub Pages static export the basePath is hard-coded so all
  // assets resolve to /litxbench/explorer/_next/…  This means a plain
  // localhost:8000/explorer/ won't load CSS/JS — see docs/README.md for
  // the local preview workaround.
  ...(isStaticExport && {
    output: "export",
    basePath: "/litxbench/explorer",
    images: { unoptimized: true },
    env: {
      NEXT_PUBLIC_BASE_PATH: "/litxbench/explorer",
      NEXT_PUBLIC_STATIC_EXPORT: "true",
    },
  }),
};

export default nextConfig;
