import vue from '@vitejs/plugin-vue'
import { defineConfig } from 'vite'
import { readFile } from 'node:fs/promises'
import { join } from 'node:path'
import { fileURLToPath } from 'node:url'

const coursePrefix = '/__course/reco'
const classAssets = /^(look-(?:0[1-9]|1[0-2])|avatar-0[1-7]|blue-jeans|brown-bag|cream-knit|denim-overshirt|khaki-trench|white-sneakers|floral-dress|burgundy-scarf)\.webp$/
const localCourseMedia = fileURLToPath(new URL('../backend/data/yida-classroom/state/media/', import.meta.url))

function courseAssets() {
  return {
    name: 'yida-course-loopback',
    configureServer(server) {
      server.middlewares.use((req, res, next) => {
        const target = req.url.split('?', 1)[0]
        if (target.startsWith(`${coursePrefix}/`) || target === coursePrefix) {
          const path = target.slice(coursePrefix.length)
          const allowed = req.method === 'POST' && path === '/recommendations' ||
            req.method === 'GET' && /^\/(?:cities|weather|recommendations\/[A-Za-z0-9_-]+)$/.test(path)
          if (allowed) return next()
          res.writeHead(404, { 'Content-Type': 'application/json' }).end('{"code":40401,"message":"课堂接口未开放"}')
          return
        }
        if (!target.startsWith('/__course/media/')) return next()
        const name = target.slice('/__course/media/'.length)
        if (req.method !== 'GET' || !classAssets.test(name)) return res.writeHead(404).end()
        const file = join(process.env.YIDA_COURSE_MEDIA_DIR || localCourseMedia, name)
        readFile(file).then(bytes => {
          res.writeHead(200, { 'Content-Type': 'image/webp', 'Cache-Control': 'no-store' }).end(bytes)
        }, () => res.writeHead(404).end())
      })
    },
  }
}

export default defineConfig(({ command, isPreview }) => {
  const course = command === 'serve' && !isPreview && process.env.VITE_COURSE_DEMO === '1'
  const team = { '/api/v1': { target: 'http://127.0.0.1:8002', changeOrigin: true } }
  return {
    plugins: [vue(), ...(course ? [courseAssets()] : [])],
    server: {
      host: '127.0.0.1', port: 5173, strictPort: true,
      ...(course ? { fs: { deny: ['.env', '.env.*', '*.{crt,pem}', '**/.git/**', '**/analysis/**', '**/backend/**'] } } : {}),
      proxy: {
        ...team,
        ...(course ? { ['^' + coursePrefix + '(?:/|$)']: {
          target: 'http://127.0.0.1:8010', changeOrigin: true,
          rewrite: path => '/api/v1' + path.slice(coursePrefix.length),
          configure(proxy) {
            proxy.on('proxyReq', request => {
              for (const header of request.getHeaderNames()) {
                if (!['host', 'accept', 'content-type', 'content-length', 'transfer-encoding'].includes(header)) request.removeHeader(header)
              }
              request.setHeader('Authorization', 'Bearer mock-token-u1')
            })
            proxy.on('proxyRes', response => { delete response.headers['set-cookie'] })
          },
        } } : {}),
      },
    },
    preview: { host: '127.0.0.1', proxy: team },
  }
})
