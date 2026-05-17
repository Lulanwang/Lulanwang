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
  // (e.g. local QA, Playwright), point /dicom-web at the backend so
  // the WADO loader still resolves.
  async rewrites() {
    if (!process.env.NEXT_PUBLIC_API_BASE) return [];
    const backend = new URL(process.env.NEXT_PUBLIC_API_BASE).origin;
    return [
      { source: "/dicom-web/:path*", destination: `${backend}/dicom-web/:path*` },
    ];
  },
};

export default nextConfig;
