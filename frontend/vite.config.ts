
import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import { VitePWA } from 'vite-plugin-pwa';

export default defineConfig(({ mode }) => {
  const isAnna = mode === 'anna';

  return {
    // Relative asset paths for Anna's embedded runtime.
    // Preserve the normal root path for standalone deployment.
    base: isAnna ? './' : '/',

    plugins: [
      react(),

      // PWA is enabled only for standalone builds.
      ...(!isAnna
        ? [
            VitePWA({
              registerType: 'autoUpdate',
              includeAssets: [
                'favicon.ico',
                'apple-touch-icon.png',
                'masked-icon.svg',
              ],
              manifest: {
                name: 'AI STEM Lab Assistant',
                short_name: 'NeuroLab',
                description:
                  'Interactive Agentic AI Physics & STEM platform',
                theme_color: '#09090b',
                background_color: '#09090b',
                display: 'standalone',
                icons: [
                  {
                    src: 'pwa-192x192.png',
                    sizes: '192x192',
                    type: 'image/png',
                  },
                  {
                    src: 'pwa-512x512.png',
                    sizes: '512x512',
                    type: 'image/png',
                  },
                ],
              },
            }),
          ]
        : []),
    ],

    optimizeDeps: {
      exclude: ['lucide-react'],
    },

    build: {
      chunkSizeWarningLimit: 1000,
      rollupOptions: {
        output: {
          manualChunks(id) {
            if (id.includes('node_modules')) {
              if (id.includes('framer-motion')) {
                return 'vendor-motion';
              }
              if (id.includes('lucide-react')) {
                return 'vendor-icons';
              }
              if (id.includes('recharts') || id.includes('d3-')) {
                return 'vendor-charts';
              }
              if (id.includes('html2pdf') || id.includes('jspdf') || id.includes('html2canvas')) {
                return 'vendor-pdf';
              }
            }
          },
        },
      },
    },
  };
});
