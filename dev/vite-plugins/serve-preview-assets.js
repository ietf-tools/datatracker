import send from 'send'
import path from 'path'
import url from 'url'

export default function servePreviewAssets () {
  return {
    name: 'serve-preview-assets',
    configurePreviewServer(server) {
      server.middlewares.use('/media/floor', (req, res, next) => {
        send(req, url.parse(req.url).pathname, { root: path.join(process.cwd(), 'playwright/data/floor-plan-images') }).pipe(res)
      })
    }
  }
}
