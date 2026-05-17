/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  // Produce a self-contained build under .next/standalone so the prod image
  // can ship without node_modules.
  output: "standalone",
  async rewrites() {
    const backend = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
    // Proxy backend routes through the frontend origin so HttpOnly auth
    // cookies (dr_session) live on the user-facing domain.
    return [
      { source: "/api/auth/:path*", destination: `${backend}/api/auth/:path*` },
      { source: "/api/billing/:path*", destination: `${backend}/api/billing/:path*` },
      { source: "/api/admin/:path*", destination: `${backend}/api/admin/:path*` },
      { source: "/api/painpoints/:path*", destination: `${backend}/api/painpoints/:path*` },
      { source: "/api/weekly/:path*", destination: `${backend}/api/weekly/:path*` },
      { source: "/api/briefs/:path*", destination: `${backend}/api/briefs/:path*` },
      { source: "/api/waitlist", destination: `${backend}/api/waitlist` },
      { source: "/api/newsletter/:path*", destination: `${backend}/api/newsletter/:path*` },
      { source: "/api/insights/:path*", destination: `${backend}/api/insights/:path*` },
      { source: "/api/health", destination: `${backend}/api/health` },
    ];
  },
};

export default nextConfig;
