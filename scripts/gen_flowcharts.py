# -*- coding: utf-8 -*-
"""医智助手业务流程图生成脚本（matplotlib 绘制，输出 PNG）。
参考《面试准备/图片》下的 6 张参考流程图主题，结合本项目实际实现生成。
"""
import os
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch, PathPatch
from matplotlib.path import Path
from matplotlib import font_manager

# ---------- 中文字体 ----------
FONT_PATH = "C:/Windows/Fonts/msyh.ttc"
if os.path.exists(FONT_PATH):
    font_manager.fontManager.addfont(FONT_PATH)
    _name = font_manager.FontProperties(fname=FONT_PATH).get_name()
    plt.rcParams["font.family"] = _name
else:
    plt.rcParams["font.family"] = ["Microsoft YaHei", "SimHei"]
plt.rcParams["axes.unicode_minus"] = False

OUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "面试准备", "流程图")
os.makedirs(OUT_DIR, exist_ok=True)

# ---------- 配色 ----------
C_START = "#2f7ed8"   # 开始/结束 蓝
C_PROC = "#ffffff"    # 处理框 白
C_DEC = "#fff3bf"     # 判断框 浅黄
C_SUB = "#e8f0fe"     # 子流程 浅蓝
C_DATA = "#e6f7ee"    # 数据 浅绿
C_EDGE = "#555555"
C_TITLE = "#1a1a1a"

# ---------- 工具函数 ----------


def _box(ax, cx, cy, w, h, text, fc, ec="#333333", lw=1.4, fs=11, shape="box", tc="#111111"):
    """绘制节点。shape: box|rect|diamond|ellipse|start"""
    if shape in ("box", "rect"):
        p = FancyBboxPatch((cx - w / 2, cy - h / 2), w, h,
                           boxstyle="round,pad=0.02,rounding_size=0.12",
                           fc=fc, ec=ec, lw=lw, zorder=2)
        ax.add_patch(p)
        ax.text(cx, cy, text, ha="center", va="center", fontsize=fs,
                color=tc, zorder=3, linespacing=1.35)
    elif shape == "ellipse":
        from matplotlib.patches import Ellipse
        e = Ellipse((cx, cy), w, h, fc=fc, ec=ec, lw=lw, zorder=2)
        ax.add_patch(e)
        ax.text(cx, cy, text, ha="center", va="center", fontsize=fs,
                color=tc, zorder=3, linespacing=1.35)
    elif shape == "diamond":
        verts = [(cx, cy + h / 2), (cx + w / 2, cy), (cx, cy - h / 2), (cx - w / 2, cy), (cx, cy + h / 2)]
        p = PathPatch(Path(verts), fc=fc, ec=ec, lw=lw, zorder=2)
        ax.add_patch(p)
        ax.text(cx, cy, text, ha="center", va="center", fontsize=fs,
                color=tc, zorder=3, linespacing=1.35)
    return (cx, cy, w, h)


def _arrow(ax, x1, y1, x2, y2, label="", color=C_EDGE, lw=1.6, fs=10,
           offset=(0.05, 0.0), shape="-|>", bend=0.0, ls="solid"):
    """画箭头，支持折线（传入多段点列表）。"""
    if isinstance(x1, list):  # x1,y1 为多段点
        pts = list(zip(x1, y1))
    else:
        pts = [(x1, y1), (x2, y2)]
    verts = pts
    path = Path(verts, [Path.MOVETO] + [Path.LINETO] * (len(verts) - 1))
    a = FancyArrowPatch(path=path, arrowstyle=shape, mutation_scale=16,
                        color=color, lw=lw, linestyle=ls, zorder=4)
    ax.add_patch(a)
    if label:
        # 标签放在中段偏上
        mx = sum(p[0] for p in pts) / len(pts)
        my = sum(p[1] for p in pts) / len(pts)
        ax.text(mx + offset[0], my + offset[1], label, fontsize=fs,
                color=color, ha="center", va="center",
                bbox=dict(boxstyle="round,pad=0.12", fc="white", ec="none", alpha=0.85),
                zorder=5)


def _title(ax, text, size=16):
    ax.text(0.5, 1.02, text, transform=ax.transAxes, fontsize=size,
            ha="center", va="bottom", color=C_TITLE, weight="bold")


def _frame(ax, xlim, ylim, title):
    ax.set_xlim(*xlim)
    ax.set_ylim(*ylim)
    ax.set_xticks([])
    ax.set_yticks([])
    for s in ax.spines.values():
        s.set_visible(False)
    _title(ax, title)


def save(fig, name):
    path = os.path.join(OUT_DIR, name)
    fig.savefig(path, dpi=170, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    print("saved:", os.path.abspath(path))


# =====================================================================
# 图1 系统总体业务流程图（主流程业务梳理）
# =====================================================================
def fig_system_main():
    fig, ax = plt.subplots(figsize=(13.5, 9))
    _frame(ax, (0, 100), (0, 78), "医智助手 · 系统总体业务流程图（主流程梳理）")

    # 顶部：用户 -> 登录 -> 路由
    _box(ax, 50, 72, 18, 5, "用户访问系统", C_START, shape="ellipse", fs=12)
    _arrow(ax, 50, 69.5, 50, 66.2)
    _box(ax, 50, 64, 22, 4.5, "登录 / 注册 (JWT 认证)", C_PROC)
    _arrow(ax, 50, 61.7, 50, 58.2)
    _box(ax, 50, 56, 22, 4.5, "路由守卫按角色分发 (meta.roles)", C_SUB)
    _arrow(ax, 50, 53.7, 50, 50.5)

    # 角色判断
    _box(ax, 50, 47, 20, 8, "判断登录角色", C_DEC, shape="diamond", fs=12)

    # 5 个角色列
    roles = [
        ("患者", 16, "智能咨询(公开)\n健康档案/挂号", "本人住院/消费"),
        ("医生", 34, "智能咨询(含私有)\n知识库管理", "患者/住院/排班"),
        ("护士", 50, "护理工作台\n排班查看", "智能咨询(公开)"),
        ("群众", 66, "智能咨询(公开)\n健康资讯/指南", "预约挂号"),
        ("管理员", 84, "全系统看板\n知识库/文档管理", "系统用户管理"),
    ]
    y_top, y_mid, y_low = 40, 32, 24
    for i, (name, cx, t1, t2) in enumerate(roles):
        color = ["#2f7ed8", "#1f9e7a", "#d8872f", "#9a5cd6", "#d84f4f"][i]
        _box(ax, cx, y_top, 11.5, 5, name, color, ec=color, shape="ellipse", tc="white", fs=12)
        _arrow(ax, 50, 43, cx, y_top + 2.7, label="")
        _box(ax, cx, y_mid, 11.5, 6, t1, C_SUB, fs=10)
        _arrow(ax, cx, y_top - 2.7, cx, y_mid + 3.1)
        _box(ax, cx, y_low, 11.5, 5, t2, C_SUB, fs=10)
        _arrow(ax, cx, y_mid - 3.1, cx, y_low + 2.6)

    # 底部数据层
    _box(ax, 50, 15, 60, 7, "数据服务层：MySQL(11表) ｜ Milvus向量 ｜ uploads文档\nRAG混合检索 + 大模型 / 离线兜底", C_DATA, fs=11)
    for i, (name, cx, t1, t2) in enumerate(roles):
        _arrow(ax, cx, y_low - 2.6, cx, 19)

    save(fig, "1-系统总体业务流程图.png")


# =====================================================================
# 图2 登录与角色权限流程
# =====================================================================
def fig_login_role():
    fig, ax = plt.subplots(figsize=(11, 9))
    _frame(ax, (0, 100), (0, 90), "医智助手 · 登录与角色权限流程图")

    _box(ax, 30, 84, 20, 5, "打开登录页", C_START, shape="ellipse")
    _arrow(ax, 30, 81.5, 30, 77)
    _box(ax, 30, 74, 22, 4.5, "输入账号 / 密码", C_PROC)
    _arrow(ax, 30, 71.7, 30, 67)
    _box(ax, 30, 64, 24, 4.5, "POST /api/auth/login\n校验密码哈希 (werkzeug)", C_PROC)
    _arrow(ax, 30, 61.7, 30, 57.5)

    _box(ax, 30, 54, 20, 8, "校验通过?", C_DEC, shape="diamond")
    _arrow(ax, 30, 50, 30, 45.5, label="是")
    _box(ax, 30, 42, 24, 4.5, "签发 JWT(HS256,24h)\n返回 token+user", C_SUB)
    _arrow(ax, 40, 54, 58, 54, label="否", color="#d84f4f")
    _box(ax, 66, 54, 22, 4.5, "返回 401\n提示用户名或密码错误", "#ffe3e3", ec="#d84f4f")
    _arrow(ax, 66, 51.7, 30, 71.5, color="#d84f4f", shape="-|>")

    _arrow(ax, 30, 39.7, 30, 35.5)
    _box(ax, 30, 32, 26, 4.5, "前端存 localStorage\n请求带 Authorization Bearer", C_PROC)
    _arrow(ax, 30, 29.7, 30, 25.5)
    _box(ax, 30, 22, 28, 4.5, "路由守卫 + require_auth\nrequire_roles 校验角色", C_SUB)
    _arrow(ax, 30, 19.7, 30, 15.5)
    _box(ax, 30, 12, 24, 4.5, "按角色渲染 MainLayout 导航", C_DATA)
    _arrow(ax, 30, 9.7, 30, 6.2)
    _box(ax, 30, 3.5, 18, 5, "进入系统", C_START, shape="ellipse")

    save(fig, "2-登录与角色权限流程图.png")


# =====================================================================
# 图3 RAG 智能问答业务流程
# =====================================================================
def fig_rag_chat():
    fig, ax = plt.subplots(figsize=(13, 10))
    _frame(ax, (0, 100), (0, 100), "医智助手 · RAG 智能问答业务流程")

    _box(ax, 50, 95, 20, 5, "用户提问", C_START, shape="ellipse")
    _arrow(ax, 50, 92.5, 50, 88)
    _box(ax, 50, 85, 30, 4.5, "POST /api/chat/ask (question, kb_id)", C_PROC)
    _arrow(ax, 50, 82.7, 50, 78.5)

    _box(ax, 50, 75, 26, 8, "选择知识库？", C_DEC, shape="diamond")
    _arrow(ax, 37, 75, 20, 75, label="指定", fs=10)
    _box(ax, 14, 75, 12, 4.5, "get_kb + 校验可见性", C_SUB, fs=9)
    _arrow(ax, 63, 75, 80, 75, label="全部/未选", fs=10)
    _box(ax, 86, 75, 12, 4.5, "跨全部可见知识库检索", C_SUB, fs=9)
    _arrow(ax, 20, 72.7, 50, 68.5, offset=(0, 0.3))
    _arrow(ax, 80, 72.7, 50, 68.5, offset=(0, 0.3))

    _box(ax, 50, 65, 32, 4.5, "按角色确定检索范围 (公开/私有可见性)", C_PROC)
    _arrow(ax, 50, 62.7, 50, 58.5)

    # 混合召回三路
    _box(ax, 50, 55, 22, 4.5, "混合召回 retrieve()", C_SUB, fs=12)
    _arrow(ax, 34, 52.8, 22, 49.5, offset=(-0.3, 0.3))
    _arrow(ax, 50, 52.8, 50, 49.5, offset=(0, 0.3))
    _arrow(ax, 66, 52.8, 78, 49.5, offset=(0.3, 0.3))
    _box(ax, 18, 47, 12, 6.5, "①关键词/字符扫描", C_SUB, fs=9)
    _box(ax, 50, 47, 12, 6.5, "②疾病名-标题匹配", C_SUB, fs=9)
    _box(ax, 82, 47, 12, 6.5, "③向量语义召回\n(max-pool)", C_SUB, fs=9)
    _arrow(ax, 18, 43.7, 50, 40.5, offset=(0, 0.3))
    _arrow(ax, 50, 43.7, 50, 40.5, offset=(0, 0.3))
    _arrow(ax, 82, 43.7, 50, 40.5, offset=(0, 0.3))

    _box(ax, 50, 37, 30, 4.5, "候选融合 + 打分重排 (TOP_K=6)", C_PROC)
    _arrow(ax, 50, 34.7, 50, 30.5)
    _box(ax, 50, 27, 34, 4.5, "构建上下文 + 引用 citations", C_PROC)
    _arrow(ax, 50, 24.7, 50, 20.5)

    _box(ax, 50, 17, 26, 8, "大模型可用？", C_DEC, shape="diamond")
    _arrow(ax, 36, 17, 22, 17, label="是")
    _box(ax, 16, 17, 12, 6, "流式生成\n(SSE delta)", C_SUB, fs=9)
    _arrow(ax, 64, 17, 78, 17, label="否")
    _box(ax, 84, 17, 12, 6, "离线摘要式回答", C_SUB, fs=9)
    _arrow(ax, 22, 14.5, 50, 11.5, offset=(0, 0.3))
    _arrow(ax, 78, 14.5, 50, 11.5, offset=(0, 0.3))

    _box(ax, 50, 8, 34, 4.5, "持久化 messages + citations → SSE 返回", C_DATA)
    _arrow(ax, 50, 5.7, 50, 2.3)
    _box(ax, 50, 0.0, 20, 5, "前端流式渲染 + 引用卡片", C_START, shape="ellipse")

    save(fig, "3-RAG智能问答业务流程图.png")


# =====================================================================
# 图4 文档上传入库流程（doc_pipeline）
# =====================================================================
def fig_doc_upload():
    fig, ax = plt.subplots(figsize=(11, 10))
    _frame(ax, (0, 100), (0, 100), "医智助手 · 文档上传与知识库入库流程")

    _box(ax, 50, 95, 22, 5, "医生/管理员上传文档", C_START, shape="ellipse")
    _arrow(ax, 50, 92.5, 50, 88)
    _box(ax, 50, 85, 28, 4.5, "权限校验 can_upload_doc", C_PROC)
    _arrow(ax, 50, 82.7, 50, 78.5)
    _box(ax, 50, 75, 28, 4.5, "格式/大小校验 (txt/md/pdf/docx/pptx)", C_PROC)
    _arrow(ax, 50, 72.7, 50, 68.5)

    _box(ax, 50, 65, 22, 8, "校验通过？", C_DEC, shape="diamond")
    _arrow(ax, 38, 65, 24, 65, label="否")
    _box(ax, 18, 65, 12, 5, "返回400\n具体原因", "#ffe3e3", ec="#d84f4f", fs=9)
    _arrow(ax, 62, 65, 76, 65, label="是")
    _box(ax, 82, 65, 12, 5, "落盘 uploads/<库>/公开|私有", C_SUB, fs=9)
    _arrow(ax, 76, 62.7, 50, 58.5, offset=(0, 0.3))

    _box(ax, 50, 55, 28, 4.5, "INSERT documents → status=processing", C_PROC)
    _arrow(ax, 50, 52.7, 50, 48.5)
    _box(ax, 50, 45, 26, 4.5, "抽取文本 extract_text", C_PROC)
    _arrow(ax, 50, 42.7, 50, 38.5)
    _box(ax, 50, 35, 26, 4.5, "切分 chunk_text (段落→句→字符)", C_PROC)
    _arrow(ax, 50, 32.7, 50, 28.5)
    _box(ax, 50, 25, 26, 4.5, "向量化 llm.embed (bge-768维)", C_PROC)
    _arrow(ax, 50, 22.7, 50, 18.5)
    _box(ax, 50, 15, 26, 4.5, "vector_store.upsert (Milvus/Numpy)", C_DATA)
    _arrow(ax, 50, 12.7, 50, 8.5)

    _box(ax, 50, 5, 22, 8, "处理成功？", C_DEC, shape="diamond")
    _arrow(ax, 38, 5, 24, 5, label="是")
    _box(ax, 18, 5, 12, 5, "status=ready\nchunk_count=N", C_DATA, fs=9)
    _arrow(ax, 62, 5, 76, 5, label="否")
    _box(ax, 82, 5, 12, 5, "status=failed+error\n可删除重传", "#ffe3e3", ec="#d84f4f", fs=9)

    save(fig, "4-文档上传入库流程图.png")


# =====================================================================
# 图5 混合召回与检索重排流程
# =====================================================================
def fig_retriever():
    fig, ax = plt.subplots(figsize=(13, 9))
    _frame(ax, (0, 100), (0, 80), "医智助手 · 混合召回与检索重排流程")

    _box(ax, 50, 74, 20, 5, "用户问题 + 可见文档集", C_START, shape="ellipse")
    _arrow(ax, 50, 71.5, 50, 67)

    # 预处理
    _box(ax, 30, 63, 18, 5.5, "同义词归一化\nnormalize_synonyms", C_SUB, fs=10)
    _box(ax, 50, 63, 18, 5.5, "提取疾病名\nextract_disease", C_SUB, fs=10)
    _box(ax, 70, 63, 18, 5.5, "查询多向量变体\nembed_query_variants", C_SUB, fs=10)
    for cx in (30, 50, 70):
        _arrow(ax, 50, 71.2, cx, 66)
        _arrow(ax, cx, 60.2, cx, 55.5)

    # 三路召回
    _box(ax, 24, 50, 14, 6.5, "①内容关键词扫描\nkeyword+char overlap", C_PROC, fs=9)
    _box(ax, 50, 50, 14, 6.5, "②疾病名-标题匹配\n标题命中强加权", C_PROC, fs=9)
    _box(ax, 76, 50, 14, 6.5, "③向量语义召回\ncosine max-pool", C_PROC, fs=9)
    _arrow(ax, 24, 46.7, 50, 42.5, offset=(0, 0.3))
    _arrow(ax, 50, 46.7, 50, 42.5, offset=(0, 0.3))
    _arrow(ax, 76, 46.7, 50, 42.5, offset=(0, 0.3))

    _box(ax, 50, 39, 40, 4.5, "候选融合 + 打分重排 score = 0.35语义+1.1关键词+0.6字符+标题加权", C_PROC, fs=10)
    _arrow(ax, 50, 36.7, 50, 32.5)
    _box(ax, 50, 29, 30, 4.5, "过滤 MIN_SIMILARITY → TOP_K 切片", C_PROC)
    _arrow(ax, 50, 26.7, 50, 22.5)
    _box(ax, 50, 19, 30, 4.5, "build_context + build_citations", C_DATA)
    _arrow(ax, 50, 16.7, 50, 12.5)
    _box(ax, 50, 9, 20, 4.5, "进入大模型 / 离线回答", C_START, shape="ellipse")

    save(fig, "5-混合召回与检索重排流程图.png")


# =====================================================================
# 图6 前后端交互与 SSE 流式问答时序流程（标准泳道时序图）
# =====================================================================
def fig_sse_seq():
    fig, ax = plt.subplots(figsize=(13, 10))
    _frame(ax, (0, 100), (0, 100), "医智助手 · 前端问答与 SSE 流式交互时序图")

    # 三条泳道（参与者）顶部标题框 + 生命线
    lanes = [
        ("Vue 前端\n(fetch/ReadableStream)", 20, "#2f7ed8"),
        ("Flask 后端\n(chat_service/retriever)", 50, "#1f9e7a"),
        ("MySQL / Milvus / LLM", 80, "#9a5cd6"),
    ]
    for name, cx, color in lanes:
        _box(ax, cx, 95, 26, 6, name, color, ec=color, tc="white", fs=11)
        # 生命线（虚线）
        ax.plot([cx, cx], [91, 4], color="#bbbbbb", lw=1, ls="--", zorder=1)

    # 交互序列（时间自上而下）
    seq = [
        (20, 88, 50, 88, "① 用户提问 + JWT", "→"),
        (50, 80, 20, 80, "② 响应会话ID + 存user消息", "←"),
        (50, 72, 80, 72, "③ 鉴权 + 混合召回检索", "→"),
        (80, 64, 50, 64, "④ 返回切片 + 引用", "←"),
        (50, 56, 20, 56, "⑤ SSE: meta 帧开始", "←"),
        (20, 48, 50, 48, "⑥ 请求流式生成", "→"),
        (50, 40, 80, 40, "⑦ 大模型 chat_stream", "→"),
        (80, 32, 50, 32, "⑧ delta token 流", "←"),
        (50, 24, 20, 24, "⑨ SSE 逐帧推送 delta", "←"),
        (20, 16, 50, 16, "⑩ 收到 done + citations", "→"),
        (50, 8, 80, 8, "11. 持久化 messages+citations", "→"),
    ]
    for x1, y1, x2, y2, label, _dir in seq:
        col = "#1f9e7a" if _dir == "→" else "#2f7ed8"
        _arrow(ax, x1, y1, x2, y2, label="", color=col)
        # 标签放在箭头起点一侧，避免与生命线重叠
        lx = (x1 + x2) / 2
        ly = (y1 + y2) / 2 + 2.2
        ax.text(lx, ly, label, fontsize=9.5, ha="center", va="center",
                bbox=dict(boxstyle="round,pad=0.15", fc="white", ec="#aaaaaa", alpha=0.95), zorder=6)

    # 底部说明
    ax.text(50, 0.5, "SSE 帧类型：meta（模式/知识库）→ delta（增量token）→ done（会话ID + 引用）",
            fontsize=10, ha="center", va="center", color="#555",
            bbox=dict(boxstyle="round,pad=0.3", fc="#eef4ff", ec="#aac4ff"), zorder=6)

    save(fig, "6-前端问答SSE交互时序图.png")


# =====================================================================
# 图7 系统部署与启动流程
# =====================================================================
def fig_deploy():
    fig, ax = plt.subplots(figsize=(12, 9))
    _frame(ax, (0, 100), (0, 88), "医智助手 · 部署与启动流程")

    _box(ax, 50, 84, 22, 5, "准备环境", C_START, shape="ellipse")
    _arrow(ax, 50, 81.5, 50, 77)
    _box(ax, 50, 74, 30, 5.5, "① 安装 MySQL8 / Milvus\nPython3.11 / Node18", C_SUB, fs=10)
    _arrow(ax, 50, 71.2, 50, 66.5)
    _box(ax, 50, 63.5, 30, 5.5, "② 安装依赖 + 配置 .env\n(DB/Milvus/OpenAI/RAG参数)", C_SUB, fs=10)
    _arrow(ax, 50, 60.7, 50, 56)

    # 本地 / Docker 分支
    _box(ax, 50, 52, 22, 8, "部署方式？", C_DEC, shape="diamond")
    _arrow(ax, 38, 52, 24, 52, label="本地")
    _box(ax, 18, 52, 12, 6, "python app.py\n+ npm run dev", C_SUB, fs=9)
    _arrow(ax, 62, 52, 76, 52, label="Docker")
    _box(ax, 82, 52, 12, 6, "docker compose up\n--build", C_SUB, fs=9)
    _arrow(ax, 24, 49.5, 50, 44.5, offset=(0, 0.3))
    _arrow(ax, 76, 49.5, 50, 44.5, offset=(0, 0.3))

    _box(ax, 50, 41, 34, 4.5, "后端启动：自动建库建表 + 播种(幂等)", C_PROC)
    _arrow(ax, 50, 38.7, 50, 34.5)
    _box(ax, 50, 31, 30, 4.5, "前端启动：/api 代理到 8010", C_PROC)
    _arrow(ax, 50, 28.7, 50, 24.5)
    _box(ax, 50, 21, 34, 4.5, "（可选）下载向量模型 bge + 配 key", C_SUB)
    _arrow(ax, 50, 18.7, 50, 14.5)
    _box(ax, 50, 11, 26, 4.5, "演示账号登录验证", C_DATA)
    _arrow(ax, 50, 8.7, 50, 4.5)
    _box(ax, 50, 1.8, 20, 5, "验收交付", C_START, shape="ellipse")

    save(fig, "7-部署与启动流程图.png")


# =====================================================================
# 图8 项目生命周期总览（从开始到结束）
# =====================================================================
def fig_lifecycle():
    fig, ax = plt.subplots(figsize=(13.5, 8))
    _frame(ax, (0, 100), (0, 60), "医智助手 · 项目完整生命周期（从开始到结束）")

    phases = [
        ("① 需求分析", "背景调研\n角色划分", "#2f7ed8"),
        ("② 系统设计", "架构/数据库\n知识库/权限", "#2f7ed8"),
        ("③ 环境准备", "MySQL/Milvus\nPython/Node", "#1f9e7a"),
        ("④ 数据准备", "12库240篇文档\n种子数据", "#1f9e7a"),
        ("⑤ 后端开发", "Blueprint/Service\n+RAG 全链路", "#d8872f"),
        ("⑥ 前端开发", "Vue3 SPA\n角色路由", "#d8872f"),
        ("⑦ 部署启动", "本地 / Docker\nCompose", "#9a5cd6"),
        ("⑧ 运行使用", "5角色登录\n业务+问答", "#9a5cd6"),
        ("⑨ 测试验收", "检索≥0.95\n权限/健壮性", "#d84f4f"),
        ("⑩ 迭代改进", "检索优化\n异步化/加固", "#d84f4f"),
    ]
    n = len(phases)
    y = 40
    for i, (title, sub, color) in enumerate(phases):
        cx = (i + 0.5) * (100 / n)
        _box(ax, cx, y, 8.5, 7, f"{title}\n{sub}", color, ec=color, tc="white", fs=9)
        if i < n - 1:
            nx = (i + 1.5) * (100 / n)
            _arrow(ax, cx + 4.2, y, nx - 4.2, y)

    # 说明
    ax.text(50, 18, "闭环：需求 → 设计 → 环境 → 数据 → 后端 → 前端 → 部署 → 运行 → 验收 → 迭代",
            fontsize=12, ha="center", va="center", color="#333",
            bbox=dict(boxstyle="round,pad=0.4", fc="#eef4ff", ec="#aac4ff"), zorder=6)
    ax.text(50, 9, "各阶段可回环：验收/运行中发现的问题回到相应阶段迭代改进",
            fontsize=11, ha="center", va="center", color="#666")

    save(fig, "8-项目生命周期总览图.png")


if __name__ == "__main__":
    fig_system_main()
    fig_login_role()
    fig_rag_chat()
    fig_doc_upload()
    fig_retriever()
    fig_sse_seq()
    fig_deploy()
    fig_lifecycle()
    print("全部流程图生成完成 ->", os.path.abspath(OUT_DIR))
