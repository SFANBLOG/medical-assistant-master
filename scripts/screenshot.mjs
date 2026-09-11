/**
 * 医智助手 · 自动截图脚本
 *
 * 使用 puppeteer-core + 本机 Chrome，自动登录 5 种角色并截图关键页面。
 *
 * 用法:
 *   cd scripts && npm install puppeteer-core
 *   node screenshot.mjs
 *
 * 截图输出到 ../docs/images/
 */
import {createRequire} from 'module'
import {mkdirSync} from 'fs'
import path from 'path'
import {fileURLToPath} from 'url'

const require = createRequire(import.meta.url)
// puppeteer-core 通过 NODE_PATH / 前端 node_modules 解析
const puppeteer = require('puppeteer-core')

const __dirname = path.dirname(fileURLToPath(import.meta.url))
const OUT_DIR = path.resolve(__dirname, '../docs/images')
mkdirSync(OUT_DIR, { recursive: true })

const BASE_URL = process.env.BASE_URL || 'http://localhost:5173'
const CHROME_PATH =
  process.env.CHROME_PATH ||
  'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe'

const DEMO_ACCOUNTS = [
  { username: 'admindemo', role: 'admin' },
  { username: 'doctordemo', role: 'doctor' },
  { username: 'nursedemo', role: 'nurse' },
  { username: 'patientdemo', role: 'patient' },
  { username: 'publicdemo', role: 'public' },
]

const PASSWORD = 'demo123'
const VIEWPORT = { width: 1440, height: 900 }

// 每个角色要截图的页面
const PAGE_PLAN = {
  admin: [
    ['01-登录页', '/login'],
    ['15-系统管理', '/admin/system'],
  ],
  doctor: [
    ['09-医生工作台', '/doctor/patients'],
    ['11-住院信息管理', '/doctor/hospitalization'],
    ['12-排班管理', '/doctor/schedules'],
    ['13-知识库管理', '/kb'],
    ['02-数据仪表盘', '/dashboard'],
  ],
  nurse: [
    ['14-护理工作台', '/nurse'],
  ],
  patient: [
    ['02-患者数据仪表盘', '/dashboard'],
    ['03-智能咨询', '/chat'],
    ['04-咨询历史', '/chat/history'],
    ['05-患者健康档案', '/health-records'],
    ['06-预约挂号', '/appointment'],
    ['07-健康资讯', '/health-info'],
    ['08-就诊指南', '/guide'],
  ],
}

async function main() {
  const browser = await puppeteer.launch({
    executablePath: CHROME_PATH,
    headless: 'new',
    args: ['--no-sandbox', '--disable-setuid-sandbox'],
    defaultViewport: VIEWPORT,
  })

  try {
    const page = await browser.newPage()

    // 登录页
    await page.goto(`${BASE_URL}/login`, { waitUntil: 'networkidle2', timeout: 30000 })
    await page.waitForSelector('input', { timeout: 10000 })
    await page.screenshot({ path: path.join(OUT_DIR, '01-登录页.png'), fullPage: false })
    console.log('✓ 01-登录页')

    // 各角色登录截图
    for (const acc of DEMO_ACCOUNTS) {
      console.log(`\n=== 角色: ${acc.role} (${acc.username}) ===`)

      // 清除上一位用户的登录态
      await page.goto(`${BASE_URL}/login`, { waitUntil: 'domcontentloaded', timeout: 30000 }).catch(() => {})
      await page.evaluate(() => {
        localStorage.clear()
        sessionStorage.clear()
      }).catch(() => {})
      const cookies = await page.cookies()
      for (const c of cookies) {
        await page.deleteCookie(c).catch(() => {})
      }

      await page.goto(`${BASE_URL}/login`, { waitUntil: 'networkidle2', timeout: 30000 })
      await page.waitForSelector('input', { timeout: 15000 })

      // 找到用户名/密码输入框
      const inputs = await page.$$('input')
      if (inputs.length >= 2) {
        await inputs[0].click({ clickCount: 3 })
        await inputs[0].type(acc.username, { delay: 20 })
        await inputs[1].click({ clickCount: 3 })
        await inputs[1].type(PASSWORD, { delay: 20 })
      }

      // 点击登录按钮
      const btn = await page.$('button[type="submit"], .login-btn, button')
      if (btn) {
        await btn.click()
      }

      // 等待跳转
      await new Promise((r) => setTimeout(r, 2500))
      await page.waitForFunction(
        (path) => !window.location.pathname.includes('login'),
        { timeout: 10000 },
        acc.role,
      ).catch(() => console.log('  (跳转超时，继续)'))

      const plan = PAGE_PLAN[acc.role] || []
      for (const [name, route] of plan) {
        try {
          if (route !== '/login') {
            await page.goto(`${BASE_URL}${route}`, {
              waitUntil: 'networkidle2',
              timeout: 30000,
            }).catch(() => {})
          }
          await new Promise((r) => setTimeout(r, 1800))
          await page.screenshot({
            path: path.join(OUT_DIR, `${name}.png`),
            fullPage: false,
          })
          console.log(`✓ ${name}`)
        } catch (e) {
          console.log(`✗ ${name}: ${e.message}`)
        }
      }
    }

    console.log(`\n全部截图完成 → ${OUT_DIR}`)
  } finally {
    await browser.close()
  }
}

main().catch((e) => {
  console.error(e)
  process.exit(1)
})
