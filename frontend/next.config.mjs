/** @type {import('next').NextConfig} */
const nextConfig = {
  output: "standalone",
  reactStrictMode: true,
  // Cornerstone3D pulls in WASM modules; webpack 5 requires opting in.
  webpack(config) {
    config.experiments = {
      ...config.experiments,
      asyncWebAssembly: true,
      layers: true,
    };
    config.module.rules.push({
      test: /\.wasm$/,
      type: "asset/resource",
    });
    return config;
  },
  // In docker-compose, Caddy fronts everything on a single origin and
  // no rewrites are needed. When running the dev server standalone
  // (e.g. local QA, Playwright), point /dicom-web AND /api at the
  // backend so client code can keep using relative URLs without
  // depending on NEXT_PUBLIC_API_BASE being baked in at build time
  // (which doesn't always work in `next dev`).
  async rewrites() {
    if (!process.env.NEXT_PUBLIC_API_BASE) return [];
    const backend = new URL(process.env.NEXT_PUBLIC_API_BASE).origin;
    return [
      { source: "/dicom-web/:path*", destination: `${backend}/dicom-web/:path*` },
      { source: "/api/:path*", destination: `${backend}/api/:path*` },
    ];
  },
};

export default nextConfig;
