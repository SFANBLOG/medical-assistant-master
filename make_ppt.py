# -*- coding: utf-8 -*-
"""生成《医智助手》项目答辩 PPT（约 28 页，16:9）。
运行：python make_ppt.py   输出：医智助手-项目答辩.pptx
"""
import os
from pptx import Presentation
from pptx.util import Inches, Pt, Emu
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
from pptx.enum.shapes import MSO_SHAPE
from pptx.oxml.ns import qn

ROOT = os.path.dirname(os.path.abspath(__file__))
IMG = os.path.join(ROOT, 'docs', 'images')
OUT = os.path.join(ROOT, '医智助手-项目答辩.pptx')

# ---------------- 调色板 ----------------
TEAL      = RGBColor(0x0F, 0x76, 0x6E)   # 主色 深青
DARK_TEAL = RGBColor(0x13, 0x4E, 0x4A)
DEEP_TEAL = RGBColor(0x0B, 0x3D, 0x39)   # 封面底
LIGHT_TEAL= RGBColor(0xE6, 0xF6, 0xF1)
PALE_TEAL = RGBColor(0xCC, 0xF1, 0xE8)
MINT      = RGBColor(0x99, 0xF6, 0xE4)
BLUE      = RGBColor(0x25, 0x63, 0xEB)
LIGHT_BLUE= RGBColor(0xEA, 0xF2, 0xFE)
AMBER     = RGBColor(0xD9, 0x77, 0x06)
LIGHT_AMBER = RGBColor(0xFE, 0xF3, 0xC7)
DARK      = RGBColor(0x1E, 0x29, 0x3B)   # 主文字
GRAY      = RGBColor(0x64, 0x74, 0x8B)
LIGHT     = RGBColor(0xF1, 0xF5, 0xF9)
WHITE     = RGBColor(0xFF, 0xFF, 0xFF)
BORDER    = RGBColor(0xCB, 0xD5, 0xE1)

FONT = '微软雅黑'

# ---------------- 基础工具 ----------------
def _set_run(run, size=16, bold=False, color=DARK, font=FONT, italic=False):
    f = run.font
    f.size = Pt(size)
    f.bold = bold
    f.italic = italic
    f.color.rgb = color
    f.name = font
    rPr = run._r.get_or_add_rPr()
    ea = rPr.find(qn('a:ea'))
    if ea is None:
        ea = rPr.makeelement(qn('a:ea'), {})
        rPr.append(ea)
    ea.set('typeface', font)

def add_text(slide, x, y, w, h, text, size=16, color=DARK, bold=False,
             align=PP_ALIGN.LEFT, anchor=MSO_ANCHOR.TOP, spacing=1.0,
             before=0, after=0):
    tb = slide.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
    tf = tb.text_frame
    tf.word_wrap = True
    tf.vertical_anchor = anchor
    tf.margin_left = tf.margin_right = tf.margin_top = tf.margin_bottom = 0
    lines = text.split('\n')
    for i, line in enumerate(lines):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.alignment = align
        p.line_spacing = spacing
        p.space_before = Pt(before)
        p.space_after = Pt(after)
        r = p.add_run()
        r.text = line
        _set_run(r, size, bold, color)
    return tb

def add_para(tf, runs, align=PP_ALIGN.LEFT, spacing=1.0, before=0, after=0,
             bullet_size=15, first=False):
    """runs: list of (text, size, bold, color)"""
    p = tf.paragraphs[0] if first else tf.add_paragraph()
    p.alignment = align
    p.line_spacing = spacing
    p.space_before = Pt(before)
    p.space_after = Pt(after)
    for (t, s, b, c) in runs:
        r = p.add_run()
        r.text = t
        _set_run(r, s, b, c)
    return p

def add_bullets(slide, x, y, w, h, items, size=15, gap=8, color=DARK,
                marker='●', mcolor=TEAL, spacing=1.0):
    """items: list of (text, level) 或 str"""
    tb = slide.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
    tf = tb.text_frame
    tf.word_wrap = True
    tf.margin_left = tf.margin_right = tf.margin_top = tf.margin_bottom = 0
    for i, it in enumerate(items):
        if isinstance(it, tuple):
            text, lvl = it
        else:
            text, lvl = it, 0
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.line_spacing = spacing
        p.space_after = Pt(gap)
        p.level = lvl
        if lvl == 0:
            r1 = p.add_run(); r1.text = marker + ' '; _set_run(r1, size, True, mcolor)
            r2 = p.add_run(); r2.text = text; _set_run(r2, size, False, color)
        else:
            r1 = p.add_run(); r1.text = '    └ '; _set_run(r1, size - 1, False, GRAY)
            r2 = p.add_run(); r2.text = text; _set_run(r2, size - 1, False, GRAY)
    return tb

def add_rect(slide, x, y, w, h, fill=None, line=None, lw=1.0,
             shape=MSO_SHAPE.ROUNDED_RECTANGLE, radius=0.08):
    sp = slide.shapes.add_shape(shape, Inches(x), Inches(y), Inches(w), Inches(h))
    if shape == MSO_SHAPE.ROUNDED_RECTANGLE:
        try:
            sp.adjustments[0] = radius
        except Exception:
            pass
    if fill is None:
        sp.fill.background()
    else:
        sp.fill.solid()
        sp.fill.fore_color.rgb = fill
    if line is None:
        sp.line.fill.background()
    else:
        sp.line.color.rgb = line
        sp.line.width = Pt(lw)
    sp.shadow.inherit = False
    return sp

def add_chip(slide, x, y, w, h, text, fill, tcolor=WHITE, size=12, bold=True,
             line=None, radius=0.5, shape=MSO_SHAPE.ROUNDED_RECTANGLE):
    sp = add_rect(slide, x, y, w, h, fill=fill, line=line, shape=shape, radius=radius)
    tf = sp.text_frame
    tf.word_wrap = True
    tf.vertical_anchor = MSO_ANCHOR.MIDDLE
    tf.margin_left = tf.margin_right = Inches(0.04)
    tf.margin_top = tf.margin_bottom = Inches(0.01)
    p = tf.paragraphs[0]
    p.alignment = PP_ALIGN.CENTER
    p.line_spacing = 1.0
    r = p.add_run(); r.text = text
    _set_run(r, size, bold, tcolor)
    return sp

def add_pic(slide, fname, x, y, w, border=True):
    """按 1440x900 比例(1.6)放图片"""
    path = os.path.join(IMG, fname)
    h = w / 1.6
    pic = slide.shapes.add_picture(path, Inches(x), Inches(y), Inches(w), Inches(h))
    if border:
        add_rect(slide, x, y, w, h, fill=None, line=BORDER, lw=1.0,
                 shape=MSO_SHAPE.RECTANGLE, radius=0)
    return pic

def content_header(slide, title, tag, page):
    # 顶部色条
    add_rect(slide, 0, 0, 13.333, 0.14, fill=TEAL, shape=MSO_SHAPE.RECTANGLE)
    # 标题左侧竖条
    add_rect(slide, 0.55, 0.42, 0.09, 0.44, fill=TEAL, shape=MSO_SHAPE.RECTANGLE)
    add_text(slide, 0.78, 0.34, 9.5, 0.6, title, size=23, bold=True, color=DARK)
    # 右上章节标签
    tw = 0.32 + len(tag) * 0.155
    add_chip(slide, 13.333 - tw - 0.55, 0.42, tw, 0.4, tag, LIGHT_TEAL, tcolor=TEAL,
             size=11, bold=True)
    # 标题下分隔线
    add_rect(slide, 0.55, 1.06, 12.23, 0.016, fill=RGBColor(0xE2, 0xE8, 0xF0),
             shape=MSO_SHAPE.RECTANGLE)
    # 页脚
    add_text(slide, 0.55, 7.06, 6.0, 0.3, '医智助手 · 医疗知识库智能问答系统',
             size=9, color=GRAY)
    add_text(slide, 11.9, 7.06, 0.9, 0.3, '%02d' % page, size=10, bold=True,
             color=GRAY, align=PP_ALIGN.RIGHT)

def new_slide():
    return prs.slides.add_slide(prs.slide_layouts[6])

def bg_slide(color):
    s = new_slide()
    add_rect(s, 0, 0, 13.333, 7.5, fill=color, shape=MSO_SHAPE.RECTANGLE)
    return s

# ---------------- 封面 ----------------
def slide_cover():
    s = bg_slide(DEEP_TEAL)
    # 装饰圆
    add_rect(s, -1.2, -1.6, 4.2, 4.2, fill=RGBColor(0x14, 0x84, 0x7B),
             shape=MSO_SHAPE.OVAL)
    add_rect(s, 11.2, 5.4, 4.4, 4.4, fill=RGBColor(0x0E, 0x60, 0x5A),
             shape=MSO_SHAPE.OVAL)
    add_rect(s, 10.0, -0.8, 1.6, 1.6, fill=RGBColor(0x14, 0x8E, 0x84),
             shape=MSO_SHAPE.OVAL)
    # 顶部小标签
    add_chip(s, 5.45, 1.35, 2.43, 0.46, '项目答辩 · 课程设计', PALE_TEAL,
             tcolor=DARK_TEAL, size=13, bold=True)
    # 主标题
    add_text(s, 1.0, 2.15, 11.33, 1.3, '医智助手', size=64, bold=True,
             color=WHITE, align=PP_ALIGN.CENTER)
    add_text(s, 1.0, 3.45, 11.33, 0.7, '医疗知识库智能问答系统', size=30,
             color=MINT, align=PP_ALIGN.CENTER)
    # 分隔线
    add_rect(s, 5.92, 4.42, 1.5, 0.03, fill=MINT, shape=MSO_SHAPE.RECTANGLE)
    add_text(s, 1.0, 4.72, 11.33, 0.5,
             '基于 RAG 的可追溯医学知识问答  ·  五角色医院信息系统教学平台',
             size=16, color=RGBColor(0xCC, 0xEA, 0xE6), align=PP_ALIGN.CENTER)
    # 底部信息
    add_text(s, 1.0, 6.15, 11.33, 0.5, '技术栈：Vue 3 · Flask · MySQL 8 · Milvus · 大语言模型',
             size=13, color=RGBColor(0x9E, 0xC9, 0xC4), align=PP_ALIGN.CENTER)
    add_text(s, 1.0, 6.55, 11.33, 0.4, '2026 年 8 月', size=13,
             color=RGBColor(0x9E, 0xC9, 0xC4), align=PP_ALIGN.CENTER)

# ---------------- 目录 ----------------
TOC = [
    ('01', '项目背景与需求分析', '背景意义 · 系统简介 · 角色权限 · 功能/非功能需求'),
    ('02', '系统总体设计', '总体架构 · 技术栈 · 数据库 · 权限安全 · RAG 设计'),
    ('03', '系统详细实现', '后端架构 · 前端架构 · 四大核心功能'),
    ('04', '系统运行与测试', '运行效果 · 测试用例'),
    ('05', '项目总结', '亮点与难点 · 总结展望'),
]

def slide_toc(page):
    s = new_slide()
    add_rect(s, 0, 0, 13.333, 0.14, fill=TEAL, shape=MSO_SHAPE.RECTANGLE)
    add_rect(s, 0.55, 0.42, 0.09, 0.44, fill=TEAL, shape=MSO_SHAPE.RECTANGLE)
    add_text(s, 0.78, 0.34, 6, 0.6, '目录', size=23, bold=True, color=DARK)
    add_text(s, 0.78, 1.05, 6, 0.4, 'CONTENTS', size=12, bold=True,
             color=RGBColor(0x94, 0xA3, 0xB8))
    # 右侧装饰
    add_rect(s, 9.3, 1.6, 3.6, 3.6, fill=RGBColor(0xF0, 0xFD, 0xFA),
             shape=MSO_SHAPE.OVAL)
    add_rect(s, 10.7, 2.9, 1.6, 1.6, fill=RGBColor(0xE0, 0xF2, 0xFE),
             shape=MSO_SHAPE.OVAL)
    y = 1.75
    for num, title, desc in TOC:
        add_rect(s, 0.8, y, 7.9, 0.86, fill=LIGHT, line=None,
                 shape=MSO_SHAPE.ROUNDED_RECTANGLE, radius=0.18)
        add_text(s, 1.15, y + 0.12, 0.9, 0.6, num, size=24, bold=True, color=TEAL)
        add_text(s, 2.1, y + 0.08, 6.4, 0.45, title, size=17, bold=True, color=DARK)
        add_text(s, 2.1, y + 0.47, 6.4, 0.35, desc, size=10.5, color=GRAY)
        y += 1.0
    footer(s, page, '目录')
    return s

def footer(s, page, tag=''):
    add_text(s, 0.55, 7.06, 6.0, 0.3, '医智助手 · 医疗知识库智能问答系统',
             size=9, color=GRAY)
    add_text(s, 11.9, 7.06, 0.9, 0.3, '%02d' % page, size=10, bold=True,
             color=GRAY, align=PP_ALIGN.RIGHT)

# ---------------- 章节页 ----------------
def slide_section(num, title, en, items):
    s = bg_slide(WHITE)
    # 左侧粗色块
    add_rect(s, 0, 0, 0.35, 7.5, fill=TEAL, shape=MSO_SHAPE.RECTANGLE)
    # 大数字
    add_text(s, 1.1, 1.35, 4.5, 2.4, num, size=150, bold=True,
             color=RGBColor(0xE0, 0xF2, 0xFE))
    add_text(s, 1.25, 3.5, 4.85, 1.0, title, size=34, bold=True, color=DARK_TEAL)
    add_text(s, 1.28, 4.62, 4.85, 0.5, en, size=15, bold=True,
             color=RGBColor(0x94, 0xA3, 0xB8))
    # 右侧内容卡片
    y = 1.5
    for i, it in enumerate(items):
        add_rect(s, 6.2, y, 6.6, 0.72, fill=LIGHT_TEAL, line=None,
                 shape=MSO_SHAPE.ROUNDED_RECTANGLE, radius=0.18)
        add_text(s, 6.55, y + 0.14, 0.5, 0.45, '%02d' % (i + 1), size=17,
                 bold=True, color=TEAL)
        add_text(s, 7.1, y + 0.15, 5.6, 0.45, it, size=14.5, bold=False, color=DARK)
        y += 0.88
    return s

# ---------------- 内容页数据 ----------------
def bullets_box(slide, x, y, w, items, title=None, size=14.5, gap=7,
                title_color=DARK_TEAL):
    """在一个浅色卡片内放小标题 + 项目符号"""
    add_rect(slide, x, y, w, 0.1 + len(items) * (gap + 4) / 72 + 0.5, fill=WHITE,
             line=BORDER, lw=1.0, shape=MSO_SHAPE.ROUNDED_RECTANGLE, radius=0.06)
    cy = y + 0.18
    if title:
        add_text(slide, x + 0.25, cy, w - 0.5, 0.4, title, size=14, bold=True,
                 color=title_color)
        cy += 0.42
    add_bullets(slide, x + 0.28, cy, w - 0.55, 3.0, items, size=size, gap=gap)
    return cy

# =========================================================
# 开始构建
# =========================================================
prs = Presentation()
prs.slide_width = Inches(13.333)
prs.slide_height = Inches(7.5)

PAGE = 0

def nxt():
    global PAGE
    PAGE += 1
    return PAGE

# ---- 1 封面 ----
slide_cover()
nxt()

# ---- 2 目录 ----
slide_toc(nxt())

# ============ 章节 1 ============
slide_section('01', '项目背景与需求分析', 'BACKGROUND & REQUIREMENTS',
              ['项目背景与意义', '系统简介', '用户角色与权限分析', '功能性需求', '非功能性需求'])
nxt()

# ---- 项目背景与意义 ----
def slide_04():
    s = new_slide()
    content_header(s, '项目背景与意义', '01 · 背景与需求', nxt())
    add_rect(s, 0.55, 1.35, 5.95, 5.45, fill=LIGHT_TEAL,
             shape=MSO_SHAPE.ROUNDED_RECTANGLE, radius=0.05)
    add_text(s, 0.9, 1.62, 5.3, 0.5, '医疗信息化现状', size=17, bold=True, color=DARK_TEAL)
    add_bullets(s, 0.92, 2.22, 5.3, 4.4, [
        ('医疗信息化是医院管理与患者服务的核心支撑', 0),
        ('传统医疗信息咨询痛点：资料分散、检索困难、缺乏个性化', 0),
        ('缺乏面向教学场景的医学知识服务平台', 0),
        ('大模型与 RAG 技术为医学知识服务带来新可能', 0),
    ], size=14, gap=13)
    add_rect(s, 6.85, 1.35, 5.95, 2.55, fill=LIGHT_BLUE,
             shape=MSO_SHAPE.ROUNDED_RECTANGLE, radius=0.06)
    add_text(s, 7.2, 1.62, 5.3, 0.5, '设计思路', size=17, bold=True, color=BLUE)
    add_bullets(s, 7.22, 2.22, 5.3, 1.6, [
        ('以"医学知识库 + 智能问答"为切入点', 0),
        ('参考医院信息系统（HIS）的真实用户角色划分', 0),
    ], size=14, gap=10)
    add_rect(s, 6.85, 4.15, 5.95, 2.65, fill=WHITE, line=BORDER,
             shape=MSO_SHAPE.ROUNDED_RECTANGLE, radius=0.06)
    add_text(s, 7.2, 4.4, 5.3, 0.5, '项目意义', size=17, bold=True, color=AMBER)
    add_bullets(s, 7.22, 5.0, 5.3, 1.7, [
        ('为数据库 / 软件工程课程提供完整工程样例', 0),
        ('面向公众的医学知识科普与辅助理解平台', 0),
    ], size=14, gap=10)
    return s
slide_04()

# ---- 系统简介 ----
def slide_05():
    s = new_slide()
    content_header(s, '系统简介', '01 · 背景与需求', nxt())
    add_text(s, 0.55, 1.3, 12.2, 0.5,
             '医智助手：面向医院信息系统教学场景的医学知识库智能问答平台',
             size=15, color=GRAY)
    stats = [
        ('12', '个疾病知识库'),
        ('240', '篇医学文档（公开 + 私有）'),
        ('5', '种用户角色门户'),
        ('11', '张 MySQL 数据表'),
    ]
    x = 0.55
    for num, label in stats:
        add_rect(s, x, 1.95, 2.93, 1.5, fill=WHITE, line=BORDER,
                 shape=MSO_SHAPE.ROUNDED_RECTANGLE, radius=0.08)
        add_text(s, x, 2.2, 2.93, 0.7, num, size=36, bold=True, color=TEAL,
                 align=PP_ALIGN.CENTER)
        add_text(s, x + 0.1, 2.95, 2.73, 0.45, label, size=11.5, color=GRAY,
                 align=PP_ALIGN.CENTER)
        x += 3.1
    add_rect(s, 0.55, 3.75, 12.23, 3.1, fill=LIGHT,
             shape=MSO_SHAPE.ROUNDED_RECTANGLE, radius=0.04)
    add_text(s, 0.9, 3.98, 11.5, 0.45, '核心能力', size=16, bold=True, color=DARK_TEAL)
    add_bullets(s, 0.92, 4.55, 5.7, 2.2, [
        ('RAG 智能医疗咨询：召回→生成→引用，可追溯', 0),
        ('公开 / 私有双层级权限模型，按角色过滤可见文档', 0),
        ('5 角色统一单页应用门户，差异化导航与权限', 0),
    ], size=13.5, gap=10)
    add_bullets(s, 6.9, 4.55, 5.7, 2.2, [
        ('患者健康档案：住院、消费明细、预约挂号', 0),
        ('医护工作台：患者管理、护理记录、排班', 0),
        ('知识库管理：上传、切分、向量化、检索一站式', 0),
    ], size=13.5, gap=10)
    return s
slide_05()

# ---- 用户角色与权限分析 ----
def slide_06():
    s = new_slide()
    content_header(s, '用户角色与权限分析（RBAC）', '01 · 背景与需求', nxt())
    rows = [
        ('角色', '核心功能', '数据可见范围'),
        ('群众 / 患者', '智能咨询 · 健康资讯 · 预约挂号 · 本人健康档案', '仅公开知识库 + 公开文档'),
        ('医生', '知识库管理 · 上传公开/私有文档 · 患者/住院管理 · 排班', '公开 + 私有文档'),
        ('护士', '患者查看 · 护理记录 · 排班查看', '仅公开知识库 + 公开文档'),
        ('管理员', '用户管理 · 全部知识库 · 全系统数据看板', '全部数据'),
    ]
    t = s.shapes.add_table(5, 3, Inches(0.55), Inches(1.35), Inches(12.23), Inches(3.6)).table
    t.columns[0].width = Inches(2.3)
    t.columns[1].width = Inches(6.2)
    t.columns[2].width = Inches(3.73)
    for r, row in enumerate(rows):
        for c, val in enumerate(row):
            cell = t.cell(r, c)
            cell.margin_left = Inches(0.15)
            cell.margin_right = Inches(0.1)
            cell.margin_top = Inches(0.05)
            cell.margin_bottom = Inches(0.05)
            cell.vertical_anchor = MSO_ANCHOR.MIDDLE
            tf = cell.text_frame
            tf.word_wrap = True
            p = tf.paragraphs[0]
            p.alignment = PP_ALIGN.LEFT if c else PP_ALIGN.LEFT
            run = p.add_run()
            run.text = val
            if r == 0:
                _set_run(run, 13, True, WHITE)
                cell.fill.solid(); cell.fill.fore_color.rgb = TEAL
            else:
                _set_run(run, 12, c == 0, DARK)
                cell.fill.solid()
                cell.fill.fore_color.rgb = LIGHT if r % 2 == 0 else WHITE
    add_text(s, 0.55, 5.25, 12.2, 0.4, '权限控制策略', size=15, bold=True,
             color=DARK_TEAL)
    add_bullets(s, 0.55, 5.75, 12.2, 1.2, [
        ('普通用户（患者/群众/护士）检索时仅保留公开片段，过滤下推到向量库（Milvus expr / Numpy 标量过滤）', 0),
        ('医生可上传私有文档并仅供本人可见；管理员拥有全部权限，实现细粒度 RBAC', 0),
    ], size=12.5, gap=8)
    return s
slide_06()

# ---- 功能性需求 ----
def slide_07():
    s = new_slide()
    content_header(s, '功能性需求', '01 · 背景与需求', nxt())
    feats = [
        ('智能医疗咨询', '自然语言提问 → 知识库召回 → 上下文构建 → 大模型流式回答，前端流式输出并附引用来源'),
        ('公开/私有权限模型', '知识库与文档均可设置公开或私有，查询时按角色自动过滤可见文档'),
        ('多角色门户', '5 种角色登录后呈现不同功能导航与权限，统一单页应用'),
        ('患者健康档案', '最近住院信息、消费明细、预约挂号查询'),
        ('医护工作台', '患者管理、住院信息管理、护理记录、排班管理'),
        ('知识库管理', '创建知识库、上传 txt/md/pdf/docx/pptx、切分、向量化入库与检索'),
        ('系统管理', '用户增删改查、全系统统计看板'),
    ]
    y = 1.35
    for title, desc in feats:
        add_rect(s, 0.55, y, 12.23, 0.72, fill=WHITE, line=BORDER,
                 shape=MSO_SHAPE.ROUNDED_RECTANGLE, radius=0.16)
        add_rect(s, 0.75, y + 0.16, 0.08, 0.4, fill=TEAL, shape=MSO_SHAPE.RECTANGLE)
        add_text(s, 1.05, y + 0.08, 2.6, 0.5, title, size=13.5, bold=True,
                 color=DARK_TEAL)
        add_text(s, 3.75, y + 0.1, 8.85, 0.55, desc, size=12, color=DARK)
        y += 0.78
    return s
slide_07()

# ---- 非功能性需求 ----
def slide_08():
    s = new_slide()
    content_header(s, '非功能性需求', '01 · 背景与需求', nxt())
    cards = [
        ('性能', 'SSE 流式响应，边生成边输出，首字延迟低', BLUE, LIGHT_BLUE),
        ('可用性', '无 API Key 也可运行；Milvus 未启动自动降级 NumpyStore', TEAL, LIGHT_TEAL),
        ('安全性', 'JWT 认证 · 密码哈希存储 · 接口角色校验', DARK_TEAL, PALE_TEAL),
        ('可维护性', 'Blueprint + Service 分层，模块职责清晰', AMBER, LIGHT_AMBER),
    ]
    x, y = 0.55, 1.45
    for i, (t, d, c1, c2) in enumerate(cards):
        cx = x + (i % 2) * 6.3
        cy = y + (i // 2) * 2.6
        add_rect(s, cx, cy, 5.95, 2.3, fill=c2, shape=MSO_SHAPE.ROUNDED_RECTANGLE,
                 radius=0.05)
        add_rect(s, cx + 0.3, cy + 0.3, 0.55, 0.55, fill=c1, shape=MSO_SHAPE.OVAL)
        add_text(s, cx + 0.42, cy + 0.4, 2.0, 0.4, t, size=15, bold=True, color=WHITE)
        add_text(s, cx + 0.32, cy + 1.05, 5.35, 1.1, d, size=13, color=DARK,
                 spacing=1.2)
    add_bullets(s, 0.55, 6.35, 12.2, 0.7, [
        ('可扩展性：向量库可切换（Milvus / NumpyStore）、模型可更换（DeepSeek / OpenAI / 通义 / Ollama）', 0),
    ], size=12.5, gap=6)
    return s
slide_08()

# ============ 章节 2 ============
slide_section('02', '系统总体设计', 'SYSTEM DESIGN',
              ['系统总体架构', '技术栈选型', '数据库设计', '权限与安全设计', '向量检索与 RAG 设计'])
nxt()

def add_arrow(s, x, y, w, direction='down', color=TEAL):
    if direction == 'down':
        add_rect(s, x - 0.09, y, 0.18, w, fill=color, shape=MSO_SHAPE.RECTANGLE)
        add_rect(s, x - 0.14, y + w - 0.12, 0.28, 0.16, fill=color,
                 shape=MSO_SHAPE.ISOSCELES_TRIANGLE)
    else:
        add_rect(s, x, y - 0.09, w, 0.18, fill=color, shape=MSO_SHAPE.RECTANGLE)
        add_rect(s, x + w - 0.12, y - 0.14, 0.16, 0.28, fill=color,
                 shape=MSO_SHAPE.ISOSCELES_TRIANGLE)

# ---- 系统总体架构 ----
def slide_10():
    s = new_slide()
    content_header(s, '系统总体架构', '02 · 总体设计', nxt())
    cx = 0.55
    cw = 12.23
    # 用户层
    roles = ['患者', '医生', '护士', '群众', '管理员']
    rx = cx
    rw = 2.3
    for r in roles:
        add_chip(s, rx, 1.35, rw, 0.55, r, PALE_TEAL, tcolor=DARK_TEAL, size=14,
                 bold=True)
        rx += rw + 0.1575
    add_arrow(s, 6.67, 1.92, 0.06, 'down')
    # 表现层
    add_rect(s, cx, 2.0, cw, 0.7, fill=DARK_TEAL, shape=MSO_SHAPE.ROUNDED_RECTANGLE,
             radius=0.14)
    add_text(s, cx + 0.2, 2.14, cw - 0.4, 0.42,
             '表现层：Vue 3 单页应用（Element Plus · Pinia · Vue Router · ECharts · Axios）',
             size=14, bold=True, color=WHITE, align=PP_ALIGN.CENTER)
    add_arrow(s, 6.67, 2.74, 0.06, 'down')
    # 服务层 两列
    add_rect(s, cx, 2.82, 5.95, 1.62, fill=LIGHT_TEAL, shape=MSO_SHAPE.ROUNDED_RECTANGLE,
             radius=0.05)
    add_text(s, cx + 0.25, 2.95, 5.5, 0.35, 'API 接口层 · Flask Blueprint', size=13,
             bold=True, color=DARK_TEAL)
    add_text(s, cx + 0.25, 3.42, 5.5, 0.9,
             'auth · kb · chat · patient · doctor\nnurse · schedule · dashboard · admin',
             size=11.5, color=DARK, spacing=1.25)
    add_rect(s, cx + 6.28, 2.82, 5.95, 1.62, fill=WHITE, line=BORDER,
             shape=MSO_SHAPE.ROUNDED_RECTANGLE, radius=0.05)
    add_text(s, cx + 6.53, 2.95, 5.5, 0.35, '业务服务层 · Service', size=13,
             bold=True, color=DARK_TEAL)
    add_text(s, cx + 6.53, 3.42, 5.5, 0.9,
             '智能咨询(RAG) · 知识库 · 文档处理 · 检索重排\n患者档案 · 医护排班 · 用户管理',
             size=11.5, color=DARK, spacing=1.25)
    add_arrow(s, 6.67, 4.48, 0.06, 'down')
    # 数据层
    add_rect(s, cx, 4.56, cw, 0.7, fill=DARK_TEAL, shape=MSO_SHAPE.ROUNDED_RECTANGLE,
             radius=0.14)
    add_text(s, cx + 0.2, 4.7, cw - 0.4, 0.42,
             '数据与基础：MySQL 8 业务数据 · Milvus/NumpyStore 向量库 · 本地文件存储 · LLM 接口（DeepSeek）',
             size=13.5, bold=True, color=WHITE, align=PP_ALIGN.CENTER)
    # 底部说明条
    add_rect(s, cx, 5.55, cw, 1.2, fill=LIGHT, shape=MSO_SHAPE.ROUNDED_RECTANGLE,
             radius=0.06)
    add_text(s, cx + 0.3, 5.72, 11.6, 0.4, '关键机制', size=13, bold=True,
             color=DARK_TEAL)
    add_bullets(s, cx + 0.32, 6.18, 11.6, 0.6, [
        ('JWT 认证与会话管理 → 角色鉴权后访问各服务；SSE 流式响应推送到前端', 0),
        ('RAG 全链路：权限过滤 → 向量召回 → 关键词重排 → 上下文构建 → 大模型生成 → 引用来源', 0),
    ], size=11.5, gap=5)
    return s
slide_10()

# ---- 技术栈 ----
def slide_11():
    s = new_slide()
    content_header(s, '技术栈选型', '02 · 总体设计', nxt())
    rows = [
        ('层级', '技术选型', '说明'),
        ('前端', 'Vue 3 · TypeScript · Vite · Element Plus', 'Pinia · Vue Router · ECharts · Axios，单页应用'),
        ('后端', 'Python · Flask · Flask-CORS', 'Blueprint + Service 分层，SSE 流式'),
        ('数据存储', 'MySQL 8 · Milvus 向量库 · 本地文件', 'NumpyStore 纯 Python 兜底，cosine 相似度'),
        ('AI / RAG', 'OpenAI 兼容接口 · bge 向量模型', '文档切分 · 向量检索 · 关键词重排 · 流式响应 · 离线兜底'),
        ('部署', 'Docker Compose', 'MySQL + 前端 Nginx + 后端 gunicorn，一键启动'),
    ]
    t = s.shapes.add_table(6, 3, Inches(0.55), Inches(1.4), Inches(12.23),
                           Inches(4.2)).table
    t.columns[0].width = Inches(1.7)
    t.columns[1].width = Inches(5.3)
    t.columns[2].width = Inches(5.23)
    for r, row in enumerate(rows):
        for c, val in enumerate(row):
            cell = t.cell(r, c)
            cell.margin_left = Inches(0.15)
            cell.margin_right = Inches(0.1)
            cell.margin_top = Inches(0.04)
            cell.margin_bottom = Inches(0.04)
            cell.vertical_anchor = MSO_ANCHOR.MIDDLE
            tf = cell.text_frame
            tf.word_wrap = True
            p = tf.paragraphs[0]
            run = p.add_run(); run.text = val
            if r == 0:
                _set_run(run, 13, True, WHITE)
                cell.fill.solid(); cell.fill.fore_color.rgb = TEAL
            else:
                _set_run(run, 12, c == 0, DARK)
                cell.fill.solid()
                cell.fill.fore_color.rgb = LIGHT if r % 2 == 0 else WHITE
    add_bullets(s, 0.55, 5.85, 12.2, 1.0, [
        ('开源可复用：MySQL 建库建表自动执行、幂等播种演示数据，开箱即用', 0),
        ('全链路可降级：无 LLM 密钥、无 Milvus 也能运行完整 RAG 流程', 0),
    ], size=12.5, gap=6)
    return s
slide_11()

# ---- 数据库设计 ----
def slide_12():
    s = new_slide()
    content_header(s, '数据库设计（MySQL 8）', '02 · 总体设计', nxt())
    add_text(s, 0.55, 1.28, 12.2, 0.4,
             '数据库 medical-assistant-master · utf8mb4 · 启动时自动建库建表、幂等播种',
             size=13, color=GRAY)
    tables = [
        ('users', '用户（5 种角色）', '50'),
        ('knowledge_bases', '知识库（公开/私有）', '50'),
        ('documents', '文档（visibility）', '240'),
        ('conversations', '咨询会话', '50'),
        ('messages', '会话消息（问答对）', '100'),
        ('citations', '回答引用来源', '50'),
        ('hospitalizations', '住院信息', '50'),
        ('bills', '消费明细', '50'),
        ('appointments', '预约挂号', '50'),
        ('nursing_records', '护理记录', '50'),
        ('schedules', '医护排班', '50'),
    ]
    x0, y0 = 0.55, 1.85
    for i, (name, desc, cnt) in enumerate(tables):
        col = i % 2
        row = i // 2
        cx = x0 + col * 6.3
        cy = y0 + row * 0.68
        add_rect(s, cx, cy, 5.95, 0.62, fill=WHITE, line=BORDER,
                 shape=MSO_SHAPE.ROUNDED_RECTANGLE, radius=0.16)
        add_text(s, cx + 0.22, cy + 0.12, 2.3, 0.4, name, size=13, bold=True,
                 color=DARK_TEAL)
        add_text(s, cx + 2.6, cy + 0.13, 2.5, 0.4, desc, size=11.5, color=GRAY)
        add_text(s, cx + 5.0, cy + 0.13, 0.8, 0.4, cnt, size=11.5, bold=True,
                 color=TEAL, align=PP_ALIGN.RIGHT)
    add_rect(s, 0.55, 6.0, 12.23, 0.85, fill=LIGHT_TEAL,
             shape=MSO_SHAPE.ROUNDED_RECTANGLE, radius=0.1)
    add_text(s, 0.9, 6.15, 11.6, 0.6,
             '设计要点：主外键关联业务闭环（用户→会话→消息→引用 / 患者→住院→账单→挂号→护理）；'
             'visibility 字段实现公开/私有双层权限；回答引用独立建表实现"可追溯"',
             size=12.5, color=DARK_TEAL, spacing=1.2)
    return s
slide_12()

# ---- 关键数据表 ----
def slide_13():
    s = new_slide()
    content_header(s, '关键数据表结构', '02 · 总体设计', nxt())
    cards = [
        ('users · 用户表', [
            ('username', 'VARCHAR(32) 唯一', '登录名'),
            ('password_hash', 'VARCHAR(255)', '密码哈希'),
            ('role', 'VARCHAR(16)', 'patient/doctor/nurse/public/admin'),
            ('display_name', 'VARCHAR(64)', '显示名'),
        ]),
        ('knowledge_bases · 知识库表', [
            ('owner_id', 'INT NULL', 'NULL=平台公共库'),
            ('name / description', 'VARCHAR', '库名与描述'),
            ('visibility', 'VARCHAR(16)', 'public / private'),
        ]),
        ('documents · 文档表', [
            ('kb_id', 'INT', '所属知识库'),
            ('file_path / file_type', 'VARCHAR', '落盘路径 · txt/md/pdf/docx/pptx'),
            ('visibility', 'VARCHAR(16)', 'public / private'),
            ('chunk_count · status', 'INT / VARCHAR', '切分块数 · processing/ready/failed'),
        ]),
        ('citations · 引用来源表', [
            ('message_id', 'INT', '关联回答消息'),
            ('document_id', 'INT', '引用文档'),
            ('chunk_index', 'INT', '片段序号'),
            ('similarity', 'DOUBLE', 'cosine 相似度'),
        ]),
    ]
    for i, (tname, fields) in enumerate(cards):
        col = i % 2
        row = i // 2
        cx = 0.55 + col * 6.3
        cy = 1.32 + row * 2.72
        add_rect(s, cx, cy, 5.95, 2.5, fill=WHITE, line=BORDER,
                 shape=MSO_SHAPE.ROUNDED_RECTANGLE, radius=0.05)
        add_rect(s, cx, cy, 0.14, 0.55, fill=TEAL, shape=MSO_SHAPE.RECTANGLE)
        add_text(s, cx + 0.32, cy + 0.12, 5.4, 0.35, tname, size=14, bold=True,
                 color=DARK_TEAL)
        add_rect(s, cx + 0.3, cy + 0.58, 5.35, 0.016, fill=RGBColor(0xE2, 0xE8, 0xF0),
                 shape=MSO_SHAPE.RECTANGLE)
        fy = cy + 0.72
        for fname, ftype, fdesc in fields:
            add_text(s, cx + 0.32, fy, 2.15, 0.3, fname, size=11, bold=True,
                     color=DARK)
            add_text(s, cx + 2.5, fy, 1.55, 0.3, ftype, size=9.5, color=GRAY)
            add_text(s, cx + 4.0, fy, 1.85, 0.3, fdesc, size=9.5, color=GRAY)
            fy += 0.34
    return s
slide_13()

# ---- 权限与安全 ----
def slide_14():
    s = new_slide()
    content_header(s, '权限与安全设计', '02 · 总体设计', nxt())
    # 左：认证流程
    add_rect(s, 0.55, 1.35, 5.95, 2.5, fill=LIGHT_TEAL,
             shape=MSO_SHAPE.ROUNDED_RECTANGLE, radius=0.05)
    add_text(s, 0.9, 1.6, 5.3, 0.45, 'JWT 认证流程', size=16, bold=True,
             color=DARK_TEAL)
    steps = ['用户登录 → 校验用户名 + 密码哈希', '签发 JWT（HS256，24h 过期）',
             '前端携带 Token 访问 /api/*', '装饰器校验角色 → 放行 / 拒绝']
    sy = 2.15
    for i, st in enumerate(steps):
        add_rect(s, 0.85, sy, 0.4, 0.4, fill=TEAL, shape=MSO_SHAPE.OVAL)
        add_text(s, 0.85, sy + 0.045, 0.4, 0.3, str(i + 1), size=13, bold=True,
                 color=WHITE, align=PP_ALIGN.CENTER)
        add_text(s, 1.42, sy + 0.05, 4.9, 0.35, st, size=12, color=DARK)
        sy += 0.47
    # 右：安全与授权
    add_rect(s, 6.85, 1.35, 5.95, 2.5, fill=WHITE, line=BORDER,
             shape=MSO_SHAPE.ROUNDED_RECTANGLE, radius=0.05)
    add_text(s, 7.2, 1.6, 5.3, 0.45, '安全机制', size=16, bold=True, color=DARK_TEAL)
    add_bullets(s, 7.22, 2.15, 5.3, 1.7, [
        ('密码 bcrypt 哈希存储，不存明文', 0),
        ('角色装饰器 @require_role 校验接口权限', 0),
        ('公开/私有过滤下推到向量库查询', 0),
        ('.env 敏感配置不入库、不提交', 0),
    ], size=12, gap=8)
    # 底部 权限矩阵
    add_rect(s, 0.55, 4.15, 12.23, 2.6, fill=LIGHT,
             shape=MSO_SHAPE.ROUNDED_RECTANGLE, radius=0.05)
    add_text(s, 0.9, 4.4, 11.5, 0.45, '核心权限矩阵', size=16, bold=True,
             color=DARK_TEAL)
    rows = [
        ('能力', '患者', '医生', '护士', '群众', '管理员'),
        ('公开知识库 / 文档查询', '✓', '✓', '✓', '✓', '✓'),
        ('私有文档检索', '✗', '✓', '✗', '✗', '✓'),
        ('创建知识库 / 上传文档', '✗', '✓', '✗', '✗', '✓'),
        ('健康档案 / 护理记录 / 排班', '本人', '管理', '护理', '挂号', '全量'),
    ]
    t = s.shapes.add_table(5, 6, Inches(0.85), Inches(4.9), Inches(11.6),
                           Inches(1.7)).table
    widths = [3.5, 1.55, 1.55, 1.55, 1.55, 1.9]
    for c, w in enumerate(widths):
        t.columns[c].width = Inches(w)
    for r, row in enumerate(rows):
        for c, val in enumerate(row):
            cell = t.cell(r, c)
            cell.margin_left = Inches(0.08)
            cell.margin_right = Inches(0.05)
            cell.margin_top = Inches(0.02)
            cell.margin_bottom = Inches(0.02)
            cell.vertical_anchor = MSO_ANCHOR.MIDDLE
            tf = cell.text_frame
            tf.word_wrap = True
            p = tf.paragraphs[0]
            p.alignment = PP_ALIGN.CENTER if c else PP_ALIGN.LEFT
            run = p.add_run(); run.text = val
            if r == 0:
                _set_run(run, 11.5, True, WHITE)
                cell.fill.solid(); cell.fill.fore_color.rgb = TEAL
            else:
                green = val == '✓'
                _set_run(run, 11.5, c == 0, RGBColor(0x0B, 0x8A, 0x55) if green else DARK)
                cell.fill.solid()
                cell.fill.fore_color.rgb = WHITE if r % 2 else LIGHT_TEAL
    return s
slide_14()

# ---- 向量检索与 RAG 设计 ----
def slide_15():
    s = new_slide()
    content_header(s, '向量检索与 RAG 设计', '02 · 总体设计', nxt())
    cols = [
        ('文档切分', ['CHUNK_SIZE=500 字符', 'CHUNK_OVERLAP=80 保证连贯', '支持 txt/md/pdf/docx/pptx']),
        ('向量化模型', ['bge-base-zh-v1.5 · 768 维', 'ModelScope 下载 · 本地推理', '中文语义检索效果好']),
        ('向量存储', ['Milvus：集合 medical_chunks', 'kb_id 分区键 + cosine HNSW', '未启动自动降级 NumpyStore']),
        ('检索与重排', ['over-fetch 取 top10', 'score = 相似度 + α·关键词重叠', 'TOP_K=5 · MIN_SIMILARITY=0.30']),
    ]
    x = 0.55
    for title, items in cols:
        add_rect(s, x, 1.4, 2.95, 3.15, fill=WHITE, line=BORDER,
                 shape=MSO_SHAPE.ROUNDED_RECTANGLE, radius=0.05)
        add_rect(s, x, 1.4, 2.95, 0.52, fill=TEAL, shape=MSO_SHAPE.ROUNDED_RECTANGLE,
                 radius=0.5)
        add_rect(s, x, 1.76, 2.95, 0.16, fill=TEAL, shape=MSO_SHAPE.RECTANGLE)
        add_text(s, x + 0.2, 1.5, 2.55, 0.35, title, size=14, bold=True,
                 color=WHITE, align=PP_ALIGN.CENTER)
        add_bullets(s, x + 0.2, 2.15, 2.55, 2.3, items, size=11.5, gap=9)
        x += 3.1
    add_rect(s, 0.55, 4.85, 12.23, 1.9, fill=LIGHT_TEAL,
             shape=MSO_SHAPE.ROUNDED_RECTANGLE, radius=0.06)
    add_text(s, 0.9, 5.1, 11.5, 0.4, '相似度语义修正', size=15, bold=True,
             color=DARK_TEAL)
    add_bullets(s, 0.92, 5.62, 11.6, 1.1, [
        ('统一 cosine 距离 → similarity = 1 - distance，得到 0~1 的 cosine 相似度（原文命中 ≈ 0.99）', 0),
        ('修复旧实现 1/(1+d) 压分导致的"匹配上但分数仅 0.3~0.5"问题；低于 MIN_SIMILARITY 的片段视为无关不进入上下文', 0),
    ], size=12.5, gap=9)
    return s
slide_15()

# ---- RAG 问答全流程 ----
def slide_16():
    s = new_slide()
    content_header(s, 'RAG 智能问答全流程', '02 · 总体设计', nxt())
    boxes = [
        ('① 用户提问', '自然语言问题'),
        ('② 权限过滤', '公开/私有文档'),
        ('③ 向量化', 'bge-zh 768 维'),
        ('④ 向量召回', 'Milvus top-10'),
        ('⑤ 关键词重排', '相似度+α·重叠'),
        ('⑥ 上下文构建', '编号片段'),
        ('⑦ LLM 生成', 'SSE 流式输出'),
        ('⑧ 返回 + 引用', 'citations 来源'),
    ]
    # 4x2 网格
    x0, y0 = 0.55, 1.5
    bw, bh, gapx, gapy = 2.95, 1.15, 0.14, 0.45
    for i, (t, d) in enumerate(boxes):
        col = i % 4
        row = i // 4
        cx = x0 + col * (bw + gapx)
        cy = y0 + row * (bh + gapy)
        add_rect(s, cx, cy, bw, bh, fill=WHITE, line=TEAL, lw=1.5,
                 shape=MSO_SHAPE.ROUNDED_RECTANGLE, radius=0.1)
        add_text(s, cx + 0.15, cy + 0.18, bw - 0.3, 0.4, t, size=14, bold=True,
                 color=DARK_TEAL, align=PP_ALIGN.CENTER)
        add_text(s, cx + 0.15, cy + 0.6, bw - 0.3, 0.35, d, size=10.5, color=GRAY,
                 align=PP_ALIGN.CENTER)
        if col < 3:
            add_arrow(s, cx + bw + 0.02, cy + bh / 2 - 0.09, gapx - 0.04, 'right')
    # 下行箭头
    add_arrow(s, x0 + bw / 2, y0 + bh + 0.1, gapy - 0.16, 'down')
    add_arrow(s, x0 + 3 * (bw + gapx) + bw / 2, y0 + bh + 0.1, gapy - 0.16, 'down')
    # 兜底说明
    add_rect(s, 0.55, 4.85, 12.23, 1.05, fill=LIGHT_AMBER,
             shape=MSO_SHAPE.ROUNDED_RECTANGLE, radius=0.08)
    add_text(s, 0.9, 5.0, 11.5, 0.4, '离线兜底，全链路始终可用', size=14.5,
             bold=True, color=AMBER)
    add_text(s, 0.9, 5.45, 11.6, 0.4,
             '未配置 API Key / 大模型调用失败 → 自动降级为基于知识库检索的离线合成回答，并保留引用来源',
             size=12.5, color=DARK)
    add_rect(s, 0.55, 6.1, 12.23, 0.75, fill=LIGHT,
             shape=MSO_SHAPE.ROUNDED_RECTANGLE, radius=0.08)
    add_text(s, 0.9, 6.22, 11.6, 0.5,
             '知识库切换：可在多个疾病知识库间选择；咨询历史按会话保存，回答引用可逐条追溯',
             size=12.5, color=DARK)
    return s
slide_16()

# ============ 章节 3 ============
slide_section('03', '系统详细实现', 'IMPLEMENTATION',
              ['后端架构实现', '前端架构实现', '智能咨询功能', '知识库管理功能', '核心业务功能'])
nxt()

# ---- 后端 ----
def slide_18():
    s = new_slide()
    content_header(s, '后端架构实现（Flask）', '03 · 详细实现', nxt())
    # 左：目录
    add_rect(s, 0.55, 1.35, 5.95, 3.4, fill=LIGHT, shape=MSO_SHAPE.ROUNDED_RECTANGLE,
             radius=0.05)
    add_text(s, 0.9, 1.6, 5.3, 0.4, '分层目录结构', size=15, bold=True,
             color=DARK_TEAL)
    code = [
        ('app.py', 'Flask 入口：自动建库建表 + 播种'),
        ('api/', '9 个蓝图：auth kb chat dashboard'),
        ('      ', 'patient doctor nurse schedule admin'),
        ('services/', '咨询 · 知识库 · 检索 · 文档处理 · LLM'),
        ('models/', 'schema_mysql.sql · db.py 数据访问层'),
        ('utils/', '错误处理 · 文件工具 · 文本工具'),
    ]
    cy = 2.1
    for name, desc in code:
        add_rect(s, 0.85, cy, 5.35, 0.44, fill=WHITE, line=RGBColor(0xE2, 0xE8, 0xF0),
                 lw=1, shape=MSO_SHAPE.ROUNDED_RECTANGLE, radius=0.22)
        add_text(s, 1.05, cy + 0.06, 1.55, 0.3, name, size=11, bold=True, color=TEAL)
        add_text(s, 2.7, cy + 0.07, 3.4, 0.3, desc, size=10, color=DARK)
        cy += 0.52
    # 右：要点
    add_rect(s, 6.85, 1.35, 5.95, 3.4, fill=WHITE, line=BORDER,
             shape=MSO_SHAPE.ROUNDED_RECTANGLE, radius=0.05)
    add_text(s, 7.2, 1.6, 5.3, 0.4, '实现要点', size=15, bold=True, color=DARK_TEAL)
    add_bullets(s, 7.22, 2.15, 5.3, 2.5, [
        ('Blueprint 按业务域拆分，接口职责单一', 0),
        ('Service 层隔离业务逻辑，可独立测试', 0),
        ('doc_pipeline：上传 → 切分 → 向量化入库', 0),
        ('retriever：向量召回 + 关键词重排 + 引用构建', 0),
        ('seed.py 幂等播种 5 角色 + 240 篇文档 + 各表 ≥50 条', 0),
    ], size=12.5, gap=8)
    add_rect(s, 0.55, 5.0, 12.23, 1.75, fill=LIGHT_TEAL,
             shape=MSO_SHAPE.ROUNDED_RECTANGLE, radius=0.06)
    add_text(s, 0.9, 5.25, 11.5, 0.4, '数据流示例：文档上传 → 检索', size=15,
             bold=True, color=DARK_TEAL)
    flow = ['上传文档', 'doc_pipeline 切分', 'bge 向量化', 'Milvus 入库', '查询时向量召回']
    fx = 0.6
    for i, f in enumerate(flow):
        add_chip(s, fx, 5.85, 2.05, 0.55, f, TEAL, size=11.5)
        if i < len(flow) - 1:
            add_arrow(s, fx + 2.11, 5.94, 0.36, 'right', color=TEAL)
        fx += 2.47
    add_text(s, 0.9, 6.55, 11.5, 0.35,
             '状态机：processing → ready / failed（失败返回具体原因，如文件格式不支持）', size=11.5,
             color=GRAY)
    return s
slide_18()

# ---- 前端 ----
def slide_19():
    s = new_slide()
    content_header(s, '前端架构实现（Vue 3）', '03 · 详细实现', nxt())
    add_pic(s, '02-患者数据仪表盘.png', 6.85, 1.4, 5.9)
    add_rect(s, 0.55, 1.35, 5.95, 4.15, fill=LIGHT, shape=MSO_SHAPE.ROUNDED_RECTANGLE,
             radius=0.05)
    add_text(s, 0.9, 1.6, 5.3, 0.4, '工程结构', size=15, bold=True, color=DARK_TEAL)
    code = [
        ('layouts/MainLayout', '5 角色导航 + 底部版权'),
        ('pages/', '仪表盘 · 咨询 · 健康档案 · 挂号 · 工作台'),
        ('api/', 'Axios 封装与 /api 端点'),
        ('store/', 'Pinia 状态管理（用户/会话）'),
        ('types/', '角色与业务类型定义'),
    ]
    cy = 2.1
    for name, desc in code:
        add_rect(s, 0.85, cy, 5.35, 0.46, fill=WHITE, line=RGBColor(0xE2, 0xE8, 0xF0),
                 lw=1, shape=MSO_SHAPE.ROUNDED_RECTANGLE, radius=0.2)
        add_text(s, 1.05, cy + 0.08, 1.85, 0.3, name, size=11, bold=True, color=TEAL)
        add_text(s, 3.0, cy + 0.08, 3.1, 0.3, desc, size=10, color=DARK)
        cy += 0.54
    add_rect(s, 0.55, 5.75, 12.23, 1.0, fill=WHITE, line=BORDER,
             shape=MSO_SHAPE.ROUNDED_RECTANGLE, radius=0.08)
    add_bullets(s, 0.9, 5.95, 11.6, 0.7, [
        ('SSE 流式渲染：EventSource 接收回答分片，逐字呈现；知识库/角色权限前端路由守卫', 0),
        ('ECharts 数据看板：管理员全系统统计、患者个人健康数据可视化', 0),
    ], size=12.5, gap=6)
    return s
slide_19()

# ---- 智能咨询 ----
def slide_20():
    s = new_slide()
    content_header(s, '核心功能 · 智能医疗咨询', '03 · 详细实现', nxt())
    add_bullets(s, 0.55, 1.4, 5.9, 3.4, [
        ('自然语言提问，多疾病知识库任选', 0),
        ('RAG 全链路：召回 → 上下文 → 流式生成', 0),
        ('回答附引用来源，支持逐条追溯（citations）', 0),
        ('咨询历史按会话保存，随时回看', 0),
        ('普通用户只能检索公开知识库 + 公开文档', 0),
        ('离线兜底：无密钥也可完整演示', 0),
    ], size=14, gap=12)
    add_pic(s, '03-智能咨询.png', 6.85, 1.4, 5.9)
    add_rect(s, 0.55, 5.15, 12.23, 1.6, fill=LIGHT_TEAL,
             shape=MSO_SHAPE.ROUNDED_RECTANGLE, radius=0.06)
    add_text(s, 0.9, 5.38, 11.5, 0.4, '回答生成逻辑（chat_service）', size=14.5,
             bold=True, color=DARK_TEAL)
    add_text(s, 0.9, 5.85, 11.6, 0.85,
             '权限过滤 → 向量召回(top10) → 相似度+关键词重排(top5) → 构建带编号上下文 → '
             '调用大模型（OpenAI 兼容）→ SSE 流式返回；将片段写入 citations 表用于前端引用展示；'
             '调用失败时降级为离线合成回答。',
             size=12, color=DARK, spacing=1.2)
    return s
slide_20()

# ---- 知识库管理 ----
def slide_21():
    s = new_slide()
    content_header(s, '核心功能 · 知识库管理', '03 · 详细实现', nxt())
    add_pic(s, '13-知识库管理.png', 6.85, 1.4, 5.9)
    add_bullets(s, 0.55, 1.4, 5.9, 3.4, [
        ('12 个疾病知识库：呼吸、心血管、消化、神经……', 0),
        ('知识库 / 文档均可设置公开或私有', 0),
        ('支持上传 txt · md · pdf · docx · pptx', 0),
        ('上传后自动切分、向量化入库，可立即检索', 0),
        ('失败时返回具体原因，状态机清晰', 0),
        ('医生私有库仅本人可见（visibility + owner）', 0),
    ], size=14, gap=12)
    add_rect(s, 0.55, 5.15, 12.23, 1.6, fill=LIGHT,
             shape=MSO_SHAPE.ROUNDED_RECTANGLE, radius=0.06)
    add_text(s, 0.9, 5.38, 11.5, 0.4, '上传管线（doc_pipeline）', size=14.5,
             bold=True, color=DARK_TEAL)
    chips = ['格式校验', '正文抽取', '切分(500+80)', 'bge 向量化', 'Milvus 写入', '状态 ready']
    fx = 0.6
    for i, c in enumerate(chips):
        add_chip(s, fx, 5.92, 1.6, 0.5, c, TEAL, size=11)
        if i < len(chips) - 1:
            add_arrow(s, fx + 1.66, 6.0, 0.34, 'right', color=TEAL)
        fx += 2.0
    return s
slide_21()

# ---- 核心业务 ----
def slide_22():
    s = new_slide()
    content_header(s, '核心业务功能', '03 · 详细实现', nxt())
    cards = [
        ('患者健康档案', '最近住院信息 · 消费明细 · 预约挂号查询', '05-患者健康档案.png'),
        ('在线预约挂号', '科室/时间选择 · 状态流转（booked→visited）', '06-预约挂号.png'),
        ('医护工作台', '患者管理 · 住院信息 · 护理记录 · 排班', '09-医生工作台.png'),
        ('系统管理', '用户增删改查 · 全系统数据看板', '15-系统管理.png'),
    ]
    x = 0.55
    for i, (t, d, img) in enumerate(cards):
        add_rect(s, x, 1.4, 2.95, 3.6, fill=WHITE, line=BORDER,
                 shape=MSO_SHAPE.ROUNDED_RECTANGLE, radius=0.05)
        add_pic(s, img, x + 0.15, 1.55, 2.65, border=False)
        add_text(s, x + 0.15, 4.15, 2.65, 0.35, t, size=13.5, bold=True,
                 color=DARK_TEAL, align=PP_ALIGN.CENTER)
        add_text(s, x + 0.12, 4.52, 2.71, 0.42, d, size=9.5, color=GRAY,
                 align=PP_ALIGN.CENTER)
        x += 3.1
    add_rect(s, 0.55, 5.25, 12.23, 1.5, fill=LIGHT_TEAL,
             shape=MSO_SHAPE.ROUNDED_RECTANGLE, radius=0.06)
    add_text(s, 0.9, 5.48, 11.5, 0.4, '业务闭环', size=14.5, bold=True,
             color=DARK_TEAL)
    add_text(s, 0.9, 5.95, 11.6, 0.7,
             '患者：注册 → 挂号 → 住院 → 消费 → 健康档案查询；'
             '医护：排班 → 接诊 → 护理记录 → 出院管理；'
             '管理员：用户与全系统数据一屏掌握。业务数据贯穿 11 张表，形成完整闭环。',
             size=12.5, color=DARK, spacing=1.2)
    return s
slide_22()

# ============ 章节 4 ============
slide_section('04', '系统运行与测试', 'RUNNING & TESTING',
              ['系统运行效果', '功能测试用例'])
nxt()

# ---- 运行效果 ----
def slide_24():
    s = new_slide()
    content_header(s, '系统运行效果', '04 · 运行与测试', nxt())
    shots = [
        ('01-登录页.png', '登录页 · 五种角色'),
        ('02-患者数据仪表盘.png', '患者数据仪表盘'),
        ('03-智能咨询.png', '智能咨询 · 流式回答 + 引用'),
        ('05-患者健康档案.png', '患者健康档案'),
    ]
    x0, y0, gapx, gapy = 2.45, 1.25, 0.8, 0.42
    w = 3.82  # h = w/1.6 = 2.39
    for i, (img, cap) in enumerate(shots):
        col = i % 2
        row = i // 2
        x = x0 + col * (w + gapx)
        y = y0 + row * (w / 1.6 + gapy)
        add_pic(s, img, x, y, w)
        add_text(s, x, y + w / 1.6 + 0.07, w, 0.3, cap, size=10.5, color=GRAY,
                 align=PP_ALIGN.CENTER)
    return s
slide_24()

# ---- 测试 ----
def slide_25():
    s = new_slide()
    content_header(s, '系统测试', '04 · 运行与测试', nxt())
    rows = [
        ('用例', '测试步骤', '预期结果'),
        ('多角色登录', '5 个演示账号逐一登录', '各自进入对应角色门户，权限正确'),
        ('公开/私有过滤', '患者/群众检索私有文档', '返回空或仅公开结果，拒绝越权'),
        ('RAG 智能问答', '对知识库提问并查看引用', '流式回答 + 引用来源可追溯'),
        ('文档上传', '上传 txt/md/pdf/docx/pptx', '切分向量化成功，检索可用；非法文件报具体原因'),
        ('健康档案/挂号', '患者查看住院消费、预约挂号', '数据与本人一致，状态流转正确'),
        ('兜底降级', '停用 API Key / 关闭 Milvus', '自动降级离线合成回答 / NumpyStore，系统不中断'),
    ]
    t = s.shapes.add_table(7, 3, Inches(0.55), Inches(1.35), Inches(12.23),
                           Inches(4.0)).table
    t.columns[0].width = Inches(2.7)
    t.columns[1].width = Inches(4.9)
    t.columns[2].width = Inches(4.63)
    for r, row in enumerate(rows):
        for c, val in enumerate(row):
            cell = t.cell(r, c)
            cell.margin_left = Inches(0.12)
            cell.margin_right = Inches(0.08)
            cell.margin_top = Inches(0.04)
            cell.margin_bottom = Inches(0.04)
            cell.vertical_anchor = MSO_ANCHOR.MIDDLE
            tf = cell.text_frame
            tf.word_wrap = True
            p = tf.paragraphs[0]
            run = p.add_run(); run.text = val
            if r == 0:
                _set_run(run, 12.5, True, WHITE)
                cell.fill.solid(); cell.fill.fore_color.rgb = TEAL
            else:
                _set_run(run, 11.5, c == 0, DARK)
                cell.fill.solid()
                cell.fill.fore_color.rgb = LIGHT if r % 2 == 0 else WHITE
    add_text(s, 0.55, 5.6, 12.2, 0.4, '说明', size=13.5, bold=True, color=DARK_TEAL)
    add_bullets(s, 0.55, 6.05, 12.2, 0.9, [
        ('本轮以功能用例手工验证为主，配合接口联调与降级演练；项目结构为后续接入 pytest 单元测试预留了 Service 层', 0),
        ('运行截图由 scripts/screenshot.mjs（puppeteer-core + 本机 Chrome）自动生成，可回归验证 UI', 0),
    ], size=11.5, gap=6)
    return s
slide_25()

# ============ 章节 5 ============
slide_section('05', '项目总结', 'SUMMARY',
              ['项目亮点与难点', '总结与展望'])
nxt()

# ---- 亮点与难点 ----
def slide_27():
    s = new_slide()
    content_header(s, '项目亮点与难点', '05 · 总结', nxt())
    add_rect(s, 0.55, 1.35, 5.95, 3.6, fill=LIGHT_TEAL,
             shape=MSO_SHAPE.ROUNDED_RECTANGLE, radius=0.05)
    add_text(s, 0.9, 1.62, 5.3, 0.45, '项目亮点', size=16, bold=True,
             color=DARK_TEAL)
    add_bullets(s, 0.92, 2.2, 5.3, 2.7, [
        ('端到端 RAG：切分→向量化→检索→重排→生成→引用', 0),
        ('公开/私有双层权限，过滤下推到向量库', 0),
        ('全链路降级，离线也完整可用', 0),
        ('知识问答 + 健康档案 + 医护管理三合一', 0),
        ('持续演进：SQLite→MySQL、ChromaDB→Milvus', 0),
    ], size=13, gap=11)
    add_rect(s, 6.85, 1.35, 5.95, 3.6, fill=WHITE, line=BORDER,
             shape=MSO_SHAPE.ROUNDED_RECTANGLE, radius=0.05)
    add_text(s, 7.2, 1.62, 5.3, 0.45, '技术难点与解决', size=16, bold=True,
             color=AMBER)
    add_bullets(s, 7.22, 2.2, 5.3, 2.7, [
        ('中文向量模型下载（HF Xet 不可达）→ 改用 ModelScope', 0),
        ('相似度压分失真（1/(1+d)）→ 改为 cosine 相似度 1-d', 0),
        ('多角色权限矩阵复杂 → 装饰器 + 下推过滤统一实现', 0),
        ('向量库不可用 → Milvus 自动降级 NumpyStore', 0),
    ], size=13, gap=11)
    add_rect(s, 0.55, 5.2, 12.23, 1.55, fill=LIGHT,
             shape=MSO_SHAPE.ROUNDED_RECTANGLE, radius=0.06)
    add_text(s, 0.9, 5.45, 11.5, 0.4, '工程亮点', size=15, bold=True,
             color=DARK_TEAL)
    add_bullets(s, 0.92, 5.95, 11.6, 0.8, [
        ('自动建库建表 + 幂等播种，五角色一键演示；Docker Compose 一键部署（Milvus+MySQL+前后端）', 0),
    ], size=12.5, gap=6)
    return s
slide_27()

# ---- 总结与展望 ----
def slide_28():
    s = new_slide()
    content_header(s, '总结与展望', '05 · 总结', nxt())
    add_rect(s, 0.55, 1.35, 12.23, 2.35, fill=LIGHT_TEAL,
             shape=MSO_SHAPE.ROUNDED_RECTANGLE, radius=0.05)
    add_text(s, 0.9, 1.6, 11.5, 0.4, '项目总结', size=16, bold=True,
             color=DARK_TEAL)
    add_bullets(s, 0.92, 2.12, 11.6, 1.5, [
        ('完成了一个"知识库 + 智能问答 + 多角色业务"的医疗辅助平台，覆盖 12 疾病库 / 240 篇文档 / 5 角色', 0),
        ('基于 RAG 实现可追溯的医学问答，并配套健康档案、挂号、医护、管理全业务闭环', 0),
        ('工程上从数据库、向量检索到前端门户均有完整设计与可运行实现，满足课程设计与教学演示要求', 0),
    ], size=13, gap=9)
    add_rect(s, 0.55, 4.0, 12.23, 2.75, fill=WHITE, line=BORDER,
             shape=MSO_SHAPE.ROUNDED_RECTANGLE, radius=0.05)
    add_text(s, 0.9, 4.25, 11.5, 0.4, '后续展望', size=16, bold=True, color=BLUE)
    items = [
        ('扩充专科知识库与权威医学语料，接入多模态（病历图片、影像报告）', 0),
        ('引入 Agent / 工具调用，对接真实医院信息系统数据', 0),
        ('增加对话记忆与个性化推荐，提升咨询体验', 0),
        ('补充自动化测试（pytest）与 CI/CD，部署公网并接入微信 / App', 0),
    ]
    add_bullets(s, 0.92, 4.8, 11.6, 1.8, items, size=13, gap=9)
    return s
slide_28()

# ---- 结束页 ----
def slide_29():
    s = bg_slide(DEEP_TEAL)
    add_rect(s, -1.2, -1.6, 4.2, 4.2, fill=RGBColor(0x14, 0x84, 0x7B),
             shape=MSO_SHAPE.OVAL)
    add_rect(s, 11.2, 5.4, 4.4, 4.4, fill=RGBColor(0x0E, 0x60, 0x5A),
             shape=MSO_SHAPE.OVAL)
    add_text(s, 1.0, 2.5, 11.33, 1.0, '感谢聆听', size=56, bold=True, color=WHITE,
             align=PP_ALIGN.CENTER)
    add_rect(s, 5.92, 3.75, 1.5, 0.03, fill=MINT, shape=MSO_SHAPE.RECTANGLE)
    add_text(s, 1.0, 4.1, 11.33, 0.5, '敬请各位老师批评指正', size=20,
             color=MINT, align=PP_ALIGN.CENTER)
    add_text(s, 1.0, 5.3, 11.33, 0.5, '医智助手 · 医疗知识库智能问答系统', size=14,
             color=RGBColor(0x9E, 0xC9, 0xC4), align=PP_ALIGN.CENTER)
    nxt()
    return s
slide_29()

prs.save(OUT)
print('Saved:', OUT)
print('Slides:', len(prs.slides._sldIdLst))
