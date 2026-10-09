import { defineConfig } from 'vite';
import {readFileSync, readdirSync} from 'node:fs';
import {fileURLToPath} from 'node:url';
const basicPitch = fileURLToPath(new URL('./node_modules/@spotify/basic-pitch/', import.meta.url));
export default defineConfig({
  base: '/assets/studio/',
  plugins: [{name: 'basic-pitch-model', generateBundle() {
    for (const name of readdirSync(basicPitch + 'model')) {
      this.emitFile({type: 'asset', fileName: 'models/basic-pitch/' + name, source: readFileSync(basicPitch + 'model/' + name)});
    }
    this.emitFile({type: 'asset', fileName: 'models/basic-pitch/LICENSE', source: readFileSync(basicPitch + 'LICENSE')});
  }}],
  build: { outDir: '../webapp/assets/studio', emptyOutDir: true,
    rollupOptions: { input: 'src/main.jsx', output: { entryFileNames: 'main.js', assetFileNames: '[name][extname]', chunkFileNames: '[name]-[hash].js' } } }
});
