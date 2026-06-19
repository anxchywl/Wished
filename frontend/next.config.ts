import type { NextConfig } from "next";

const allowedDevOrigins = process.env.NEXT_PUBLIC_TELEGRAM_DEV_ORIGINS
  ? process.env.NEXT_PUBLIC_TELEGRAM_DEV_ORIGINS.split(",").map((origin) => origin.trim()).filter(Boolean)
  : [];

const nextConfig: NextConfig = {
  devIndicators: false,
  reactStrictMode: true,
  async rewrites() {
    return [
      {
        source: "/api/v1/:path*",
        destination: "http://127.0.0.1:8000/api/v1/:path*",
      },
      {
        source: "/wished-media/:path*",
        destination: "http://127.0.0.1:9000/wished-media/:path*",
      },
    ];
  },
};

;(nextConfig as any).allowedDevOrigins = allowedDevOrigins;

export default nextConfig;
