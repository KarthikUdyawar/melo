/** @type {import('next').NextConfig} */
const nextConfig = {
  output: "export",       // static HTML/JS, served by existing nginx — no Node runtime in prod
  images: { unoptimized: true }, // static export can't use next/image optimizer
  reactStrictMode: true,
  trailingSlash: true,    // matches nginx static-file serving expectations
};

export default nextConfig;
