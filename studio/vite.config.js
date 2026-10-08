import { defineConfig } from 'vite';
export default defineConfig({
  base: '/assets/studio/',
  build: { outDir: '../webapp/assets/studio', emptyOutDir: true,
    rollupOptions: { input: 'src/main.jsx', output: { entryFileNames: 'main.js', assetFileNames: '[name][extname]', chunkFileNames: '[name]-[hash].js' } } }
});
