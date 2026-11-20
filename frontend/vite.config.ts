import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

/**
 * Long-lived vendor chunks; pages are split per route via React.lazy. antd and its icons share
 * one chunk because they import each other.
 */
const VENDOR_CHUNKS: [chunk: string, pattern: RegExp][] = [
    ["react", /\/node_modules\/(react|react-dom|scheduler)\//],
    ["router", /\/node_modules\/(react-router|react-router-dom)\//],
    ["antd", /\/node_modules\/(antd|@ant-design|@rc-component|rc-[^/]+)\//],
];

/** Where the dev server forwards `/api/*` (Docker dev sets this to the backend service). */
const apiProxyTarget = process.env.API_PROXY_TARGET ?? "http://localhost:8000";

export default defineConfig({
    plugins: [react()],
    server: {
        port: 5173,
        proxy: {
            // Same-origin API in dev, mirroring nginx in production. http-proxy streams
            // responses, so the SSE endpoints work through it unchanged.
            "/api": {
                target: apiProxyTarget,
                changeOrigin: true,
                rewrite: path => path.replace(/^\/api/, ""),
            },
        },
    },
    build: {
        outDir: "dist",
        sourcemap: false,
        // antd is intentionally kept as one cached vendor chunk (~370 kB gzip).
        chunkSizeWarningLimit: 1300,
        rollupOptions: {
            output: {
                manualChunks: id => VENDOR_CHUNKS.find(([, pattern]) => pattern.test(id))?.[0],
            },
        },
    },
});
