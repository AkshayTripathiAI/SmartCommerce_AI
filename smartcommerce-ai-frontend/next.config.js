// The browser calls /api/* on this origin; Next proxies it to the FastAPI backend.
// Set BACKEND_URL in the hosting environment (e.g. https://smartcommerce-ai-api.onrender.com).
const BACKEND_URL = (process.env.BACKEND_URL || 'http://localhost:8000').replace(/\/$/, '')

/** @type {import('next').NextConfig} */
const nextConfig = {
    images: {
        remotePatterns: [
            {
                protocol: 'https',
                hostname: 'images.unsplash.com',
            },
        ],
    },
    async rewrites() {
        return [
            {
                source: '/api/:path*',
                destination: `${BACKEND_URL}/api/:path*`,
            },
        ]
    },
}

module.exports = nextConfig
