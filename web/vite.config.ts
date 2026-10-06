import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";
import { VitePWA } from "vite-plugin-pwa";

export default defineConfig({
  plugins: [
    react(),
    tailwindcss(),
    VitePWA({
      registerType: "autoUpdate",
      includeAssets: ["locales/*.json"],
      manifest: {
        name: "NetraSetu",
        short_name: "NetraSetu",
        display: "standalone",
        background_color: "#F4F6F7",
        theme_color: "#141A21",
        start_url: "/field",
      },
      workbox: {
        globPatterns: ["**/*.{js,css,html,woff2,svg,json}"],
        navigateFallback: "index.html",
        runtimeCaching: [
          {
            urlPattern: ({ url }) => url.pathname.includes("/locales/"),
            handler: "StaleWhileRevalidate",
            options: { cacheName: "locales" },
          },
          {
            urlPattern: ({ url }) => url.pathname.includes("/tiles/") || url.pathname.includes("/dzi/"),
            handler: "CacheFirst",
            options: {
              cacheName: "tiles",
              expiration: { maxEntries: 2000, maxAgeSeconds: 60 * 60 * 4 },
            },
          },
        ],
      },
      devOptions: { enabled: false },
    }),
  ],
  server: { port: 5173, strictPort: true },
  test: {
    environment: "jsdom",
    setupFiles: "./src/test/setup.ts",
  },
});
