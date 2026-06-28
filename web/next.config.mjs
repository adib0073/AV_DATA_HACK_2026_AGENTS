/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  // Produce a self-contained server bundle for a small Docker runtime image.
  output: "standalone",
};

export default nextConfig;
