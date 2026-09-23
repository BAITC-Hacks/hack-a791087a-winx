import { defineConfig } from 'vite';
import { fileURLToPath } from 'node:url';
import { readFileSync } from 'node:fs';

export default defineConfig({
  plugins: [{
    name: 'bundle-third-party-license',
    generateBundle() {
      this.emitFile({ type: 'asset', fileName: 'THIRD_PARTY_LICENSES.txt',
        source: readFileSync(new URL('./node_modules/three/LICENSE', import.meta.url), 'utf8') });
    },
  }],
  build: {
    outDir: '../build',
    emptyOutDir: true,
    lib: {
      entry: fileURLToPath(new URL('./src/main.js', import.meta.url)),
      formats: ['es'],
      fileName: () => 'city3d.js',
      cssFileName: 'city3d',
    },
    cssCodeSplit: false,
    sourcemap: false,
  },
});
