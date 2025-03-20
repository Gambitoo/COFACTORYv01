import { fileURLToPath, URL } from 'node:url'

import { defineConfig, loadEnv } from 'vite'
import vueDevTools from 'vite-plugin-vue-devtools'
import vue from '@vitejs/plugin-vue'
import vueJsx from '@vitejs/plugin-vue-jsx';

// https://vitejs.dev/config/
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd())

  return {
    base: "/App/MetalPlanning",
    plugins: [vue(), vueJsx(), vueDevTools({launchEditor: "code"}),],
    resolve: {
      alias: {
        '@': fileURLToPath(new URL('./src', import.meta.url))
      }
    },
    server: {
      host: env.VITE_HOST || 'localhost',
      port: parseInt(env.VITE_PORT || 5173),
      proxy: {
        // Proxy API requests to Flask backend
        '/api': {
          target: `${env.VITE_FLASK_HOST || 'localhost'}:${env.VITE_FLASK_PORT || 5001}`,
          changeOrigin: true,
          rewrite: (path) => path.replace(/^\/api/, '')
        }
      }
    },
    define: {
      'import.meta.env.VITE_FLASK_HOST': JSON.stringify(env.VITE_FLASK_HOST || 'localhost'),
      'import.meta.env.VITE_FLASK_PORT': JSON.stringify(env.VITE_FLASK_PORT || 5001)
    }
  }
})
