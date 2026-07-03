/** @type {import('next').NextConfig} */
const nextConfig = {
  async rewrites() {
    return [
      {
        source: "/api/convert",
        destination: "/api",
      },
    ];
  },
};

export default nextConfig;
