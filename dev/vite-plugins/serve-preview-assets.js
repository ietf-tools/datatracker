import send from 'send'
import path from 'node:path'

export default function servePreviewAssets () {
  return {
    name: 'serve-preview-assets',
    configurePreviewServer (server) {
      server.middlewares.use('/media/floor', (req, res, next) => {
        send(req, req.url, { root: path.join(process.cwd(), 'playwright/data/floor-plan-images') }).pipe(res)
      })
    }
  }
}
