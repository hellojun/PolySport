#!/usr/bin/env node
/**
 * Prerender public pages to static HTML for SEO crawlers.
 * Run after `npm run build` — outputs to dist/prerendered/
 *
 * Requires: puppeteer-core (devDep) + system Chromium
 *   Server: sudo apt install chromium-browser
 *   macOS:  npx puppeteer browsers install chrome
 */
import { createServer } from 'http'
import { readFileSync, writeFileSync, mkdirSync, existsSync } from 'fs'
import { resolve, join, dirname } from 'path'
import { fileURLToPath, pathToFileURL } from 'url'
import { createRequire } from 'module'

const __dirname = dirname(fileURLToPath(import.meta.url))
const DIST = resolve(__dirname, '../frontend/dist')

// Pages to prerender (path → output file)
const PAGES = [
  { path: '/', outFile: 'index.html' },
  { path: '/predict', outFile: 'predict/index.html' },
]

// Find Chromium executable
function findChromium() {
  const candidates = [
    '/usr/bin/chromium-browser',       // Ubuntu/Debian
    '/usr/bin/chromium',               // Arch/Alpine
    '/snap/bin/chromium',              // Snap
    '/usr/bin/google-chrome-stable',   // Chrome on Linux
    '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome', // macOS
  ]
  for (const p of candidates) {
    if (existsSync(p)) return p
  }
  return null
}

// Minimal static file server for the dist directory
function startServer(port) {
  const mimeTypes = {
    '.html': 'text/html',
    '.js': 'application/javascript',
    '.css': 'text/css',
    '.json': 'application/json',
    '.svg': 'image/svg+xml',
    '.png': 'image/png',
    '.ico': 'image/x-icon',
    '.woff2': 'font/woff2',
    '.woff': 'font/woff',
  }

  return new Promise((res) => {
    const server = createServer((req, resp) => {
      let url = req.url.split('?')[0]
      let filePath = join(DIST, url)

      // SPA fallback: if file doesn't exist, serve index.html
      try {
        const stat = readFileSync(filePath)
        const ext = url.match(/\.[^.]+$/)?.[0] || '.html'
        resp.writeHead(200, { 'Content-Type': mimeTypes[ext] || 'application/octet-stream' })
        resp.end(stat)
      } catch {
        try {
          const html = readFileSync(join(DIST, 'index.html'))
          resp.writeHead(200, { 'Content-Type': 'text/html' })
          resp.end(html)
        } catch {
          resp.writeHead(404)
          resp.end('Not found')
        }
      }
    })
    server.listen(port, () => res(server))
  })
}

async function main() {
  if (!existsSync(DIST)) {
    console.error('Error: frontend/dist not found. Run `npm run build` first.')
    process.exit(1)
  }

  // Resolve puppeteer-core from frontend/node_modules
  let puppeteer
  try {
    const frontendRequire = createRequire(resolve(__dirname, '../frontend/package.json'))
    const puppeteerCjsPath = frontendRequire.resolve('puppeteer-core')
    puppeteer = await import(pathToFileURL(puppeteerCjsPath).href)
  } catch {
    console.error('Error: puppeteer-core not installed. Run: cd frontend && npm i -D puppeteer-core')
    process.exit(1)
  }

  const chromePath = findChromium()
  if (!chromePath) {
    console.error('Error: Chromium not found. Install with: sudo apt install chromium-browser')
    process.exit(1)
  }
  console.log(`Using Chromium: ${chromePath}`)

  const PORT = 4173
  const server = await startServer(PORT)
  console.log(`Static server running on http://localhost:${PORT}`)

  const browser = await puppeteer.default.launch({
    executablePath: chromePath,
    headless: 'new',
    args: ['--no-sandbox', '--disable-setuid-sandbox', '--disable-dev-shm-usage'],
  })

  const outDir = join(DIST, 'prerendered')

  for (const page of PAGES) {
    console.log(`Prerendering ${page.path} ...`)

    const tab = await browser.newPage()

    // Set English locale for consistent SEO content
    await tab.evaluateOnNewDocument(() => {
      localStorage.setItem('locale', 'en')
    })

    await tab.goto(`http://localhost:${PORT}${page.path}`, {
      waitUntil: 'networkidle0',
      timeout: 30000,
    })

    // Wait for Vue to mount
    await tab.waitForSelector('#app > *', { timeout: 10000 })
    // Extra wait for async content
    await new Promise((r) => setTimeout(r, 2000))

    const html = await tab.content()
    const outPath = join(outDir, page.outFile)
    mkdirSync(dirname(outPath), { recursive: true })
    writeFileSync(outPath, html, 'utf-8')
    console.log(`  -> ${outPath}`)

    await tab.close()
  }

  await browser.close()
  server.close()
  console.log('Prerendering complete!')
}

main().catch((err) => {
  console.error(err)
  process.exit(1)
})
