import { defineConfig } from 'vite';
import { resolve } from 'path';
import tailwindcss from '@tailwindcss/vite'
import inject from '@rollup/plugin-inject'

export default defineConfig(({ command }) => ({
    base: "/static/",
    server: {
        host: '0.0.0.0',
        port: 5173,
        watch: {
            usePolling: true,
            interval: 2000
        },
        hmr: {
            host: 'localhost',
            overlay: false
        },
        ...(command === "serve" ? { origin: "http://localhost:5173" } : {}),
    },
    build: {
        manifest: "manifest.json",
        outDir: resolve("./dist"),
        rollupOptions: {
            input: {
                test: resolve('./static/js/main.js')
            }
        },
    },
    plugins: [
        tailwindcss(),
        inject({
            htmx: 'htmx.org'
        }),
    ],
}));
