/**
 * 截图：聊天页带完整 AI 回答（新提问并等待）
 */
import {createRequire} from 'module'
import path from 'path'
import {fileURLToPath} from 'url'

const require = createRequire(import.meta.url)
const puppeteer = require('puppeteer-core')

const __dirname = path.dirname(fileURLToPath(import.meta.url))
const OUT = path.resolve(__dirname, '../docs/images/03-智能咨询.png')

const b = await puppeteer.launch({
  executablePath: 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe',
  headless: 'new',
  args: ['--no-sandbox'],
  defaultViewport: { width: 1440, height: 900 },
})

try {
  const ctx = await b.createBrowserContext()
  const p = await ctx.newPage()
  await p.setViewport({ width: 1440, height: 900 })

  // 登录患者
  await p.goto('http://localhost:5173/login', { waitUntil: 'networkidle2', timeout: 30000 })
  await p.waitForSelector('.demo-item', { timeout: 10000 })
  await new Promise((r) => setTimeout(r, 1000))
  await p.evaluate(() => {
    for (const it of document.querySelectorAll('.demo-item')) {
      if (it.innerText.includes('患者')) { it.click(); return }
    }
  })
  await new Promise((r) => setTimeout(r, 3500))

  // 新建对话
  await p.evaluate(() => {
    for (const b of document.querySelectorAll('button')) {
      if (b.innerText.trim() === '新对话') { b.click(); return }
    }
  })
  await new Promise((r) => setTimeout(r, 1500))

  // 选知识库（心血管疾病）
  await p.evaluate(() => {
    const body = document.querySelector('.chat-topbar .el-select')
    if (body) body.click()
  })
  await new Promise((r) => setTimeout(r, 800))
  await p.evaluate(() => {
    for (const o of document.querySelectorAll('.el-select-dropdown__item')) {
      if (o.innerText.includes('心血管')) { o.click(); return }
    }
  })
  await new Promise((r) => setTimeout(r, 600))

  // 输入问题
  const ta = await p.$('textarea')
  await ta.click()
  await ta.type('高血压应该怎么控制？', { delay: 15 })
  await new Promise((r) => setTimeout(r, 500))

  // 发送
  await p.evaluate(() => {
    for (const b of document.querySelectorAll('button')) {
      if (b.innerText.trim() === '发送' || b.innerText.includes('发送')) { b.click(); return }
    }
  })

  // 等待 AI 完整回答（~20s）
  console.log('Waiting for AI response...')
  await new Promise((r) => setTimeout(r, 18000))

  // 滚动到底
  await p.evaluate(() => {
    const body = document.querySelector('.chat-body')
    if (body) body.scrollTop = body.scrollHeight
  })
  await new Promise((r) => setTimeout(r, 800))

  await p.screenshot({ path: OUT })
  console.log('Saved:', OUT)
  await ctx.close()
} finally {
  await b.close()
}
