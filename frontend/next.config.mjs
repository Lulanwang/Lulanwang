/** @type {import('next').NextConfig} */
const nextConfig = {
  output: "standalone",
  reactStrictMode: true,
  // Caddy fronts everything on a single origin; no rewrites needed.
};

export default nextConfig;
