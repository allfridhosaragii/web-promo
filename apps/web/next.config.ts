import type { NextConfig } from "next";
const nextConfig: NextConfig = {
  reactStrictMode: true,
  transpilePackages: ["@burupromo/ui", "@burupromo/contracts"],
};
export default nextConfig;
