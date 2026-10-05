import { defineConfig } from "vite";

export default defineConfig({
  server: {
    port: 3000,
    host: "0.0.0.0",
    proxy: {
      "/api": {
        target: process.env.VITE_BACKEND_URL || "http://127.0.0.1:8000",
        changeOrigin: true,
        secure: false,
      },
      "/static": {
        target: "http://127.0.0.1:3000",
        rewrite: (path) => path.replace(/^\/static/, ""),
      },
    },
  },
  preview: {
    port: 3000,
    host: "0.0.0.0",
  },
});
