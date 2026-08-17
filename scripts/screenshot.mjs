/**
 * 运行截图脚本（Node + puppeteer-core，复用本机 Chrome，无需下载浏览器）。
 *
 * 用法：
 *   1) 先启动后端：cd backend && python app.py
 *   2) 再启动前端：cd frontend && npm run dev
 *   3) cd frontend && node ../scripts/screenshot.mjs
 *
 * 截图输出到 docs/images/。
 */
import puppeteer from 'puppeteer-core'
import {mkdirSync} from 'node:fs'
import path from 'node:path'
import {fileURLToPath} from 'node:url'

const CHROME = 'C:/Program Files/Google/Chrome/Application/chrome.exe'
const BASE = 'http://127.0.0.1:5173'
const OUT_DIR = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..', 'docs', 'images')
const PASSWORD = 'demo123'

mkdirSync(OUT_DIR, {recursive: true})

const browser = await puppeteer.launch({
    executablePath: CHROME,
    headless: 'new',
    args: ['--no-sandbox', '--disable-gpu', '--window-size=1440,900'],
    defaultViewport: {width: 1440, height: 900},
})

async function shot(page, name, wait = 1200) {
    await new Promise((r) => setTimeout(r, wait))
    await page.screenshot({path: path.join(OUT_DIR, name)})
    console.log('截图:', name)
}

async function login(page, username) {
    await page.goto(`${BASE}/login`, {waitUntil: 'networkidle2'})
    await page.waitForSelector('input[placeholder*="演示账号"]', {timeout: 15000})
    await page.type('input[placeholder*="演示账号"]', username)
    await page.type('input[placeholder*="演示密码"]', PASSWORD)
    // antd 会在两个汉字的按钮间插入空格（"登 录"），匹配时需忽略空白
    await page.evaluate(() => {
        const btns = [...document.querySelectorAll('button')]
        const b = btns.find((x) => x.textContent.replace(/\s/g, '').includes('登录'))
        if (b) b.click()
    })
    await page.waitForSelector('.ant-layout-sider', {timeout: 20000})
    await new Promise((r) => setTimeout(r, 800))
}

async function goto(page, route, name, wait = 1400) {
    await page.goto(`${BASE}${route}`, {waitUntil: 'networkidle2'})
    await shot(page, name, wait)
}

const page = await browser.newPage()

// ===== 登录页 =====
await page.goto(`${BASE}/login`, {waitUntil: 'networkidle2'})
await shot(page, '01-登录页.png')

// ===== 患者 =====
await login(page, 'patientdemo')
await goto(page, '/', '02-患者数据仪表盘.png')
// 智能咨询：发一条问题再截图
await page.goto(`${BASE}/chat`, {waitUntil: 'networkidle2'})
await new Promise((r) => setTimeout(r, 1200))
try {
    await page.type('textarea', '高血压患者饮食需要注意什么？')
    const btn = await page.evaluateHandle(() => {
        const btns = [...document.querySelectorAll('button')]
        return btns.find((x) => x.textContent.replace(/\s/g, '').includes('发送')) || null
    })
    if (btn) await btn.asElement().click()
    await new Promise((r) => setTimeout(r, 6000)) // 等待大模型流式回答
} catch (e) {
    console.log('智能咨询输入失败（跳过），仍截图空页面：', e.message)
}
await shot(page, '03-智能咨询.png', 1500)
await goto(page, '/chat/history', '04-咨询历史.png')
await goto(page, '/patient', '05-患者健康档案.png')
await goto(page, '/appointments', '06-预约挂号.png')

// ===== 群众 =====
await login(page, 'publicdemo')
await goto(page, '/health', '07-健康资讯.png')
await goto(page, '/guide', '08-就诊指南.png')

// ===== 医生 =====
await login(page, 'doctordemo')
await goto(page, '/doctor', '09-医生工作台.png')
await goto(page, '/doctor/patients', '10-患者管理.png')
await goto(page, '/doctor/hospitalizations', '11-住院信息管理.png')
await goto(page, '/schedule', '12-排班管理.png')
await goto(page, '/kb', '13-知识库管理.png')

// ===== 护士 =====
await login(page, 'nursedemo')
await goto(page, '/nurse', '14-护理工作台.png')

// ===== 管理员 =====
await login(page, 'admindemo')
await goto(page, '/admin', '15-系统管理.png')

await browser.close()
console.log('全部截图完成 ->', OUT_DIR)
