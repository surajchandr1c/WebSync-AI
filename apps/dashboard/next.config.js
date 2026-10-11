/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  transpilePackages: ['@websync/api-client', '@websync/shared-types', '@websync/ui'],
};

module.exports = nextConfig;
