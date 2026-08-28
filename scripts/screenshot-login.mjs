/**
 * 单独截图：登录页（无登录态）
 */
import { createRequire } from 'module'
import path from 'path'
import { fileURLToPath } from 'url'

const require = createRequire(import.meta.url)
const puppeteer = require('puppeteer-core')

const __dirname = path.dirname(fileURLToPath(import.meta.url))
const OUT = path.resolve(__dirname, '../docs/images/01-登录页.png')

const b = await puppeteer.launch({
  executablePath: 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe',
  headless: 'new',
  args: ['--no-sandbox'],
  defaultViewport: { width: 1440, height: 900 },
})

try {
  const p = await b.newPage()
  // 创建干净的 incognito 上下文，确保无登录态
  const ctx = await b.createBrowserContext()
  const page = await ctx.newPage()
  await page.setViewport({ width: 1440, height: 900 })
  await page.goto('http://localhost:5173/login', { waitUntil: 'networkidle2', timeout: 30000 })
  await new Promise((r) => setTimeout(r, 2500))
  await page.screenshot({ path: OUT })
  console.log('Saved:', OUT)
  await ctx.close()
} finally {
  await b.close()
}
