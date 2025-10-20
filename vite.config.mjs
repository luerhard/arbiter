import { defineConfig } from 'vite';
import { resolve } from 'path';
import tailwindcss from '@tailwindcss/vite'
import inject from '@rollup/plugin-inject'

export default defineConfig({
    base: "/static/",
    build: {
        manifest: "manifest.json",
        outDir: resolve("./assets"),
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
    server: {
        host: 'localhost',
        port: 5173,
        strictPort: true,
        cors: true
    }

})
