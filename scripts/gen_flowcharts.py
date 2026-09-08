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
    _box(ax, 50, 16, 62, 7.5, "数据服务层：MySQL(17 表) ｜ Milvus向量 ｜ uploads 医学文档(241篇)\nRAG 混合检索重排 v4 + Agent 多智能体(Skills/MCP) / 离线兜底", C_DATA, fs=10.5)
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
# 图3 RAG 智能问答业务流程（chat 模式）
# =====================================================================
def fig_rag_chat():
    fig, ax = plt.subplots(figsize=(13, 10.5))
    _frame(ax, (0, 100), (0, 100), "医智助手 · RAG 智能问答业务流程（chat 模式）")

    # 1) 发起流式问答请求
    _box(ax, 50, 95.5, 20, 5, "用户在会话页提问", C_START, shape="ellipse", fs=11)
    _arrow(ax, 50, 93.0, 50, 91.6)
    _box(ax, 50, 88.5, 40, 6, "POST /api/chat/stream/<conv_id> (JWT)\nbody: {question, kb_id}", C_PROC, fs=10)
    _arrow(ax, 50, 85.5, 50, 85.1)

    # 2) 知识库范围选择
    _box(ax, 50, 80.5, 22, 9, "指定知识库?", C_DEC, shape="diamond", fs=11)
    _arrow(ax, 39, 80.5, 25.2, 80.5)
    _arrow(ax, 61, 80.5, 74.8, 80.5)
    _box(ax, 15, 80.5, 20, 5.5, "kb_id>0: 校验可见性\n(get_kb)", C_SUB, fs=9.5)
    _box(ax, 85, 80.5, 20, 5.5, "kb_id=0/未指定: 跨全部\n可见知识库检索", C_SUB, fs=9.5)

    # 3) 混合召回：角色过滤 + 双路检索
    _box(ax, 50, 68.5, 60, 9,
         "混合召回 retrieve() —— 按角色过滤可见 KB（公开库 + 医生/管理员私有库）\n"
         "① BM25 稀疏检索 Top-30（jieba 分词 + 医学同义词扩展查询）\n"
         "② BGE 稠密向量检索 Top-30（768 维真实语义嵌入）",
         C_SUB, fs=9.5)
    _arrow(ax, 15, 77.8, 41, 73.1)   # 左分支汇入
    _arrow(ax, 85, 77.8, 59, 73.1)   # 右分支汇入
    _arrow(ax, 50, 64.0, 50, 60.1)

    # 4) 并集去重 + 融合重排 v4
    _box(ax, 50, 55.5, 60, 9,
         "并集去重 (doc_id+chunk_index) → 候选集（约 40-60 条）\n"
         "融合重排 v4：score = 0.55·稠密 + 0.30·BM25 + 0.15·词法重叠\n"
         "实体/疾病名命中 → 地板 0.90 + 0.10×证据分 ｜ CE 增强(可选)",
         C_PROC, fs=9.5)
    _arrow(ax, 50, 51.0, 50, 48.9)

    # 5) 相关性 + HITL 复核过滤
    _box(ax, 50, 45.0, 52, 7.5,
         "过滤：score ≥ 0.45 且文档已复核通过(approved & ready)\n"
         "（未复核/驳回/处理中的文档不进上下文）→ 截取 Top-8",
         C_PROC, fs=9.5)
    _arrow(ax, 50, 41.2, 50, 38.7)

    # 6) 构建上下文
    _box(ax, 50, 35.5, 40, 6, "build_context（≤4000 字符）\n引用 → citations（可追溯）", C_PROC, fs=10)
    _arrow(ax, 50, 32.5, 50, 30.1)

    # 7) 大模型可用性分支
    _box(ax, 50, 25.5, 22, 9, "大模型可用?", C_DEC, shape="diamond", fs=11)
    _arrow(ax, 39, 25.5, 24.3, 25.5, label="是")
    _arrow(ax, 61, 25.5, 75.7, 25.5, label="否", color="#d84f4f")
    _box(ax, 15, 25.5, 18, 6.5, "LLM 流式生成\n(chat_stream)", C_SUB, fs=9.5)
    _box(ax, 85, 25.5, 18, 6.5, "离线摘要式回答\n(无 API Key 兜底)", C_SUB, fs=9.5)

    # 8) 持久化 + SSE 输出
    _box(ax, 50, 14.5, 54, 7,
         "① 先发 citations 引用帧 → ② LLM 增量内容流\n"
         "持久化 messages + citations（首问自动更新会话标题）",
         C_DATA, fs=9.5)
    _arrow(ax, 15, 22.2, 41, 18.2)
    _arrow(ax, 85, 22.2, 59, 18.2)

    # 9) 结束
    _box(ax, 50, 7.0, 24, 5.5, "SSE 流结束\n前端完整渲染 + 引用卡片", C_START, shape="ellipse", fs=10.5)
    _arrow(ax, 50, 11.0, 50, 9.85)

    ax.text(50, 1.1,
            "说明：RAG 模式帧 = citations 引用帧 + 增量内容 data 帧；Agent 智能体模式走 POST /api/agent/stream/<conv_id>，\n"
            "事件含 meta / thought / tool_call / observation / message / done，并调用工具（详见 9-Agent 多智能体流程图）",
            fontsize=8.6, ha="center", va="center", color="#666", linespacing=1.5)

    save(fig, "3-RAG智能问答业务流程图.png")


# =====================================================================
# 图4 文档上传入库流程（doc_pipeline）
# =====================================================================
def fig_doc_upload():
    # 整体重写：原图存在三处与代码不符（llm.embed → embedder.embed_batch、
    # vector_store.upsert → vectorstore.insert_batch、缺 HITL 复核链）。
    # 新版加入 documents.review_status=pending → 医生复核 approve/reject 的完整 HITL 链。
    fig, ax = plt.subplots(figsize=(11, 11.5))
    _frame(ax, (0, 100), (0, 108), "医智助手 · 文档上传入库与人工复核（HITL）流程")

    # 主线：上传 → 向量化 → 待复核
    _box(ax, 50, 102.5, 22, 5, "医生/管理员上传文档", C_START, shape="ellipse", fs=11)
    _arrow(ax, 50, 100.0, 50, 98.3)
    _box(ax, 50, 95.5, 40, 5.5, "POST /api/kb/<kb_id>/documents (multipart)\n扩展名白名单 / 64MB 限制", C_PROC, fs=9.5)
    _arrow(ax, 50, 92.7, 50, 91.3)
    _box(ax, 50, 88.5, 40, 5.5, "_extract_document_text 解析文本\n(PDF 分页+页眉页脚清洗) → chunk_document 切分", C_PROC, fs=9.5)
    _arrow(ax, 50, 85.7, 50, 84.3)
    _box(ax, 50, 81.5, 40, 5.5, "embedder.embed_batch 向量化（bge 768维）\nINSERT documents → status=ready", C_PROC, fs=9.5)
    _arrow(ax, 50, 78.7, 50, 77.3)
    _box(ax, 50, 74.5, 40, 5.5, "vectorstore.insert_batch 写入向量库\n(Milvus / NumpyStore 自动降级)", C_PROC, fs=9.5)
    _arrow(ax, 50, 71.7, 50, 69.2)

    # 待复核状态（documents.review_status 默认 pending）
    _box(ax, 50, 65.5, 46, 7,
         "进入待复核：review_status = pending（默认）\n"
         "向量虽已入库，未审核文档不参与检索\n"
         "（检索元数据门控：approved & ready）",
         C_DEC, fs=9.5)
    _arrow(ax, 50, 62.0, 50, 59.2)

    # 医生复核
    _box(ax, 50, 55.5, 44, 7, "医生 / 管理员复核（review_bp · /api/review）\napprove 通过 ｜ reject 驳回（附 review_note）", C_SUB, fs=9.5)
    _arrow(ax, 50, 52.0, 36, 48.9, label="approve", fs=8.5)
    _arrow(ax, 50, 52.0, 64, 48.9, label="reject", fs=8.5)

    # 复核结果
    _box(ax, 26, 44, 28, 9, "review_status = approved\n状态机生效：可被 RAG 检索\n(须同时 status=ready)", C_DATA, fs=9)
    _box(ax, 74, 44, 28, 9, "review_status = rejected\n检索永不命中\n可删除 / 修复后重新上传", "#ffe3e3", ec="#d84f4f", fs=9)
    _arrow(ax, 26, 39.5, 41, 36.9)
    _arrow(ax, 74, 39.5, 59, 36.9)

    # 审计留痕
    _box(ax, 50, 33.5, 88, 6, "动作留痕：write_audit → audit_logs（actor · role · action=doc_approved/rejected · target · note · 时间）", "#eef4ff", ec="#aac4ff", fs=9)
    _arrow(ax, 50, 30.5, 50, 28.9)
    _box(ax, 50, 26, 60, 5.5, "管理员审计查询：GET /api/review/audit（action / target_type 过滤 + 分页）", "#eef4ff", ec="#aac4ff", fs=9)

    # 底部设计要点
    ax.text(50, 18.5,
            "要点：\n"
            "① 复核状态机 pending → approved / rejected；已决记录重复复核返回 409；\n"
            "② documents / messages / appointment_requests 三表统一 review_status 字段；\n"
            "③ HITL 价值：AI 先生成入库、人工确认后生效，未审内容绝不进入 RAG 上下文；\n"
            "④ 回答复核与预约建单复核的同构流程见 10-人工复核与审计流程图。",
            fontsize=9, ha="center", va="center", color="#555", linespacing=1.65)

    save(fig, "4-文档上传入库流程图.png")


# =====================================================================
# 图5 混合召回与检索重排流程
# =====================================================================
def fig_retriever():
    # 整体重写：旧图函数名与公式均已过时（normalize_synonyms/extract_disease/
    # embed_query_variants 不存在），新版按 retriever.py + reranker.py v4 实测流程绘制。
    fig, ax = plt.subplots(figsize=(13, 10))
    _frame(ax, (0, 100), (0, 95), "医智助手 · 混合召回与融合重排 v4 流程")

    # 入口
    _box(ax, 50, 91, 22, 5, "用户问题 + 角色(可见KB)", C_START, shape="ellipse", fs=10.5)
    _arrow(ax, 50, 88.5, 32, 87.6)
    _arrow(ax, 50, 88.5, 68, 87.6)

    # 双路召回
    _box(ax, 27, 84, 26, 6.5, "① BM25 稀疏检索 Top-30\njieba 分词 + _expand_query\n医学同义词扩展", C_SUB, fs=9.5)
    _box(ax, 73, 84, 26, 6.5, "② BGE 稠密向量检索 Top-30\n768 维真实语义嵌入\n(权限过滤下推到向量库)", C_SUB, fs=9.5)
    _arrow(ax, 27, 80.7, 41, 77.7)
    _arrow(ax, 73, 80.7, 59, 77.7)

    # 合并去重
    _box(ax, 50, 74.5, 34, 5.5, "并集去重 (doc_id, chunk_index)\n→ 候选集（约 40-60 条）", C_PROC, fs=9.5)
    _arrow(ax, 50, 71.7, 50, 70.5)

    # 融合重排 v4
    _box(ax, 50, 65.5, 62, 10.5,
         "融合重排 v4（reranker.rerank）：\n"
         "score = 0.55·稠密余弦 + 0.30·BM25归一化 + 0.15·词法重叠\n"
         "实体/疾病名命中 → 地板 0.90 + 0.10×证据分 ｜ 标题命中加分 ｜ 泛化词降权\n"
         "Cross-Encoder(bge-reranker) 为可选增强信号（默认 auto 融合）",
         C_PROC, fs=9.5)
    _arrow(ax, 50, 60.2, 50, 56.6)

    # 质量 + HITL 过滤
    _box(ax, 50, 52.5, 56, 7.5,
         "质量 + HITL 过滤：score ≥ 0.45 才保留；文档须 approved(复核通过) & ready\n"
         "（未复核/驳回/处理中的文档剔除）→ 截取 Top-8",
         C_PROC, fs=9.5)
    _arrow(ax, 50, 48.7, 50, 46.2)

    # 上下文
    _box(ax, 50, 43, 36, 5.5, "build_context 拼装（≤4000 字符）\n携带 filename/kb_name 元数据", C_PROC, fs=9.5)
    _arrow(ax, 50, 40.2, 50, 37.9)

    # 结束
    _box(ax, 50, 34.5, 24, 6, "返回 Top-8 hits\n→ 生成回答 + 引用卡片", C_START, shape="ellipse", fs=10)

    # 底部：v4 实测要点
    ax.text(50, 20.5,
            "实测要点（本地 42 问评测）：融合重排 v4 Hit@1 = 100%，Top-8 平均分 ≈ 0.94，优于单路召回；\n"
            "0.45 阈值可干净切分：医学相关片段普遍 ≥ 0.90、不相关片段 < 0.45；\n"
            "实体地板分保证“问感冒答肺炎”这类同义改写提问仍保持高相关。",
            fontsize=9, ha="center", va="center", color="#555", linespacing=1.7)
    ax.text(50, 6.5,
            "HITL 复核门控：新上传文档 review_status=pending，医生 approve 后才可能出现在本流程结果中（见 10-人工复核与审计流程图）",
            fontsize=9, ha="center", va="center", color="#666",
            bbox=dict(boxstyle="round,pad=0.4", fc="#eef4ff", ec="#aac4ff"), zorder=6)

    save(fig, "5-混合召回与检索重排流程图.png")


# =====================================================================
# 图6 前后端交互与 SSE 流式问答时序流程（标准泳道时序图）
# =====================================================================
def fig_sse_seq():
    # 整体重写：旧图采用「两次请求 + delta 帧」，与现状不符（chat 模式为一次 POST 全流程；
    # 帧为 citations + 增量 data，无 delta/done 命名；Agent 模式事件见 agent_bp 注释）。
    fig, ax = plt.subplots(figsize=(13.5, 10.5))
    _frame(ax, (0, 100), (0, 100), "医智助手 · 前端问答 SSE 流式交互时序图（chat 模式全流程）")

    # 三条泳道（参与者）顶部标题框 + 生命线
    lanes = [
        ("Vue 前端\n(SSE 客户端)", 20, "#2f7ed8"),
        ("Flask 后端\n(chat_service / retriever)", 50, "#1f9e7a"),
        ("MySQL · Milvus/BM25 · LLM", 80, "#9a5cd6"),
    ]
    for name, cx, color in lanes:
        _box(ax, cx, 95.5, 26, 6, name, color, ec=color, tc="white", fs=11)
        # 生命线（虚线）
        ax.plot([cx, cx], [91.5, 4], color="#bbbbbb", lw=1, ls="--", zorder=1)

    # 交互序列（时间自上而下；→ 绿为请求，← 蓝为返回）
    seq = [
        (20, 87, 50, 87, "① POST /api/chat/stream/<conv_id>\n{question, kb_id} + JWT", "→"),
        (50, 80, 80, 80, "② 保存 user 消息\n(首问自动更新会话标题)", "→"),
        (80, 73, 50, 73, "③ 返回会话上下文\n(最近 6 条历史)", "←"),
        (50, 66, 80, 66, "④ 角色过滤 + retrieve()\nBM25∪BGE → 融合重排 v4 → Top-8", "→"),
        (80, 59, 50, 59, "⑤ 返回 Top-8 片段\n(仅 approved & ready 文档)", "←"),
        (50, 52, 20, 52, "⑥ SSE：先发 data {citations:[…]}\n引用帧（可追溯）", "←"),
        (20, 45, 50, 45, "⑦ 前端收到引用帧\n开始接收内容", "→"),
        (50, 38, 80, 38, "⑧ 大模型 chat_stream\n流式生成", "→"),
        (80, 31, 50, 31, "⑨ data {content: 增量}\n逐块回流", "←"),
        (50, 24, 20, 24, "⑩ SSE 逐块转发\n→ 前端打字机式渲染", "←"),
        (80, 17, 50, 17, "11. 保存 assistant 消息\n+ citations", "→"),
        (50, 10.5, 20, 10.5, "12. 流结束\n→ 引用卡片展示", "←"),
    ]
    for x1, y1, x2, y2, label, _dir in seq:
        col = "#1f9e7a" if _dir == "→" else "#2f7ed8"
        _arrow(ax, x1, y1, x2, y2, label="", color=col)
        # 标签放线上方（含白底，避免与生命线重叠）
        lx = (x1 + x2) / 2
        ly = y1 + 3.4
        ax.text(lx, ly, label, fontsize=8.8, ha="center", va="center",
                bbox=dict(boxstyle="round,pad=0.15", fc="white", ec="#aaaaaa", alpha=0.95), zorder=6)

    # 底部帧说明
    ax.text(50, 6.8,
            "帧说明（chat 模式）：无独立事件名 —— citations 以 data JSON 先发，随后 data {content} 增量块透传 LLM 流；",
            fontsize=8.8, ha="center", va="center", color="#555",
            bbox=dict(boxstyle="round,pad=0.3", fc="#eef4ff", ec="#aac4ff"), zorder=6)
    ax.text(50, 3.4,
            "Agent 模式（POST /api/agent/stream）：事件含 meta / thought / tool_call / observation / citations / message / done / error，轨迹存 agent_steps（可观测）",
            fontsize=8.8, ha="center", va="center", color="#555",
            bbox=dict(boxstyle="round,pad=0.3", fc="#f5f0ff", ec="#c9b8ff"), zorder=6)

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
    _box(ax, 18, 52, 12, 6, "python -m backend\n+ npm run dev", C_SUB, fs=9)
    _arrow(ax, 62, 52, 76, 52, label="Docker")
    _box(ax, 82, 52, 12, 6, "docker compose up\n--build", C_SUB, fs=9)
    _arrow(ax, 24, 49.5, 50, 44.5, offset=(0, 0.3))
    _arrow(ax, 76, 49.5, 50, 44.5, offset=(0, 0.3))

    _box(ax, 50, 41, 34, 4.5, "后端启动：自动建库建表 + 播种(幂等)", C_PROC)
    _arrow(ax, 50, 38.7, 50, 34.5)
    _box(ax, 50, 31, 30, 4.5, "前端启动：/api 代理到 8010", C_PROC)
    _arrow(ax, 50, 28.7, 50, 24.5)
    _box(ax, 50, 21, 32, 5.2, "(可选) 下载 BGE 模型\n+ 配置 OPENAI_API_KEY", C_SUB, fs=9.5)
    _arrow(ax, 50, 18.3, 50, 14.5)
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
        ("④ 数据准备", "12库241篇文档\n种子数据", "#1f9e7a"),
        ("⑤ 后端开发", "Blueprint/Service\nRAG+Agent 编排层", "#d8872f"),
        ("⑥ 前端开发", "Vue3 SPA\n角色路由", "#d8872f"),
        ("⑦ 部署启动", "本地 / Docker\nCompose", "#9a5cd6"),
        ("⑧ 运行使用", "5角色登录\n业务+问答", "#9a5cd6"),
        ("⑨ 测试验收", "重排 Hit@1=100%\nAgent 离线评测", "#d84f4f"),
        ("⑩ 迭代改进", "融合重排 v4\nAgent v2(MCP/Skills)", "#d84f4f"),
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


# =====================================================================
# 图9 Agent v2 多智能体问答流程（Supervisor + 子智能体 + 技能/工具）
# =====================================================================
def fig_agent_qa():
    fig, ax = plt.subplots(figsize=(14.5, 11))
    _frame(ax, (0, 100), (0, 100), "医智助手 · Agent v2 多智能体问答流程（Supervisor + 子智能体 + 技能/工具）")

    # 1) 请求入口
    _box(ax, 50, 97.5, 22, 5, "用户提问（Agent 模式）", C_START, shape="ellipse", fs=11)
    _arrow(ax, 50, 95.0, 50, 93.4)
    _box(ax, 50, 90.5, 42, 5.5, "POST /api/agent/stream/<conv_id> (JWT)\n{question, kb_id}", C_PROC, fs=9.5)
    _arrow(ax, 50, 87.7, 50, 87.1)

    # 2) 安全护栏
    _box(ax, 50, 82.0, 26, 10, "安全护栏\n紧急/危重症状?", C_DEC, shape="diamond", fs=10)
    _arrow(ax, 63, 82.0, 75.5, 82.0, label="是", fs=8.5)
    _box(ax, 84, 82.0, 16, 8, "护栏触发\n直接输出急救指引\n(跳过 Agent 编排)", "#ffe3e3", ec="#d84f4f", fs=8.5)
    ax.text(84, 72.5, "该分支同样保存消息并\n按角色进入复核队列", fontsize=7.6, ha="center", va="center", color="#999")
    _arrow(ax, 50, 77.0, 50, 76.4)

    # 3) 记忆注入
    _box(ax, 50, 73.5, 44, 5.5, "记忆注入：get_enhanced_user_context\n(用户画像 / 历史偏好 / 随访提醒)", C_SUB, fs=9)
    _arrow(ax, 50, 70.7, 50, 69.4)

    # 4) Supervisor 路由
    _box(ax, 50, 66.0, 52, 6.5, "Supervisor 意图分类：LLM JSON {agent, confidence, intent}\n离线降级：can_handle() 置信度路由 + classify_role 关键字兜底", C_SUB, fs=9)
    _arrow(ax, 50, 62.7, 20, 60.6)
    _arrow(ax, 50, 62.7, 50, 60.6)
    _arrow(ax, 50, 62.7, 80, 60.6)

    # 5) 6 个子智能体（两排）
    agents1 = [("导诊 triage\n症状→科室推荐", 20), ("医生 doctor\n诊断/用药参考", 50), ("护士 nurse\n护理/康复指导", 80)]
    agents2 = [("知识 knowledge\n库问答(默认兜底)", 20), ("排班 schedule\n出诊/预约管理", 50), ("随访 followup\n复诊/慢病跟踪", 80)]
    for text, cx in agents1:
        _box(ax, cx, 57.5, 18, 6, text, C_SUB, fs=8.8)
    for text, cx in agents2:
        _box(ax, cx, 50.0, 18, 6, text, C_SUB, fs=8.8)
    for cx in (20, 50, 80):
        _arrow(ax, cx, 54.4, cx, 53.2)
    _arrow(ax, 20, 46.9, 20, 45.9)
    _arrow(ax, 50, 46.9, 50, 45.9)
    _arrow(ax, 80, 46.9, 80, 45.9)

    # 6) ReAct 推理
    _box(ax, 50, 42.5, 58, 6, "子智能体 ReAct 推理循环：thought → tool_call → observation\n技能/工具按角色白名单执行；知识问答内部复用 RAG v4 检索", C_PROC, fs=9)
    _arrow(ax, 50, 39.4, 26, 37.0)
    _arrow(ax, 50, 39.4, 74, 37.0)

    # 7) 技能 / 工具
    _box(ax, 26, 32.5, 26, 8.5,
         "5 项技能 Skill（多步能力组合）\nmedical_qa 医学问答 ｜ triage 分诊\nappointment 预约 ｜ patient_records\nhealth_education 健教",
         "#eef4ff", ec="#aac4ff", fs=8.3)
    _box(ax, 74, 32.5, 26, 8.5,
         "9 个工具 Tool（角色白名单过滤）\nsearch_knowledge → RAG v4 检索\ntriage_departments 分诊 ｜ 预约建单\n排班/病历/住院/天气/逆地理查询",
         "#eef4ff", ec="#aac4ff", fs=8.3)
    _arrow(ax, 26, 28.2, 41, 27.4)
    _arrow(ax, 74, 28.2, 59, 27.4)

    # 8) 写操作分支
    _box(ax, 50, 22.5, 24, 9.5, "需要写操作?\n(预约/挂号)", C_DEC, shape="diamond", fs=10)
    _arrow(ax, 62, 22.5, 73.5, 22.5, label="是", fs=8.5)
    _box(ax, 85, 22.5, 22, 8.5, "create_appointment\n→ appointment_requests\n(pending) 医生复核后建单", C_DATA, fs=8.3)
    _arrow(ax, 50, 17.7, 50, 15.9, label="否：常规问答", offset=(-5.5, 0), fs=8.5)
    _arrow(ax, 85, 18.2, 76, 15.95)

    # 9) SSE 事件流 + 持久化
    _box(ax, 50, 12.5, 58, 6.5,
         "SSE 事件流：meta / thought / tool_call / observation / citations\n/ message / done（异常 error）→ 前端逐条展示",
         C_PROC, fs=8.8)
    _arrow(ax, 50, 9.2, 50, 8.4)
    _box(ax, 50, 4.8, 62, 6.5,
         "持久化：messages + agent_steps(ReAct 轨迹) + citations\n患者/群众回答 → pending 医生复核队列 ｜ 医护/admin → approved",
         C_DATA, fs=8.8)

    save(fig, "9-Agent多智能体问答流程图.png")


# =====================================================================
# 图10 人工复核与审计流程（HITL 三通道）
# =====================================================================
def fig_hitl_review():
    fig, ax = plt.subplots(figsize=(14.5, 10.5))
    _frame(ax, (0, 100), (0, 100), "医智助手 · 人工复核与审计流程（HITL 三通道）")

    # 入口
    _box(ax, 50, 96.5, 36, 5, "医生 / 管理员 复核台（HITL · /api/review）", C_START, shape="ellipse", fs=10.5)

    # 三个复核通道
    cols = [
        (20, "① 文档复核 documents", "#2f7ed8"),
        (50, "② AI 回答复核 messages", "#1f9e7a"),
        (80, "③ 预约建单复核 appointment_requests", "#9a5cd6"),
    ]
    for cx, title, color in cols:
        _arrow(ax, 50, 94.0, cx, 91.7)
        _box(ax, cx, 88.5, 30, 6, title, color, ec=color, tc="white", fs=9)
    
    # 待复核来源
    srcs = [
        (20, "上传后自动 pending\n未复核文档不参与检索"),
        (50, "患者/群众 Agent 回答\n自动进入待复核"),
        (80, "Agent 调用预约工具\ncreate_appointment 后待审"),
    ]
    for (cx, text), _ in zip(srcs, cols):
        _box(ax, cx, 81.0, 28, 6.5, text, C_PROC, fs=8.5)
        _arrow(ax, cx, 85.5, cx, 84.3)

    # 待办队列接口
    apis = [
        (20, "GET /api/review/documents?status=pending"),
        (50, "GET /api/review/answers?status=pending"),
        (80, "GET /api/review/appointments?status=pending"),
    ]
    for (cx, text), _ in zip(apis, cols):
        _box(ax, cx, 74.5, 28, 5, text, C_SUB, fs=7.6)
        _arrow(ax, cx, 77.7, cx, 77.1)

    # 复核决策
    for cx, _, _ in cols:
        _box(ax, cx, 66.5, 28, 7, "复核动作：approve 通过 ｜ reject 驳回\n(附 review_note 备注)", C_DEC, fs=8.5)
        _arrow(ax, cx, 74.0, cx, 70.1)
        _arrow(ax, cx, 63.0, cx - 7, 59.9)
        _arrow(ax, cx, 63.0, cx + 7, 59.9)

    # approve / reject 生效效果
    ok = [
        (20, "approve\nreview_status=approved\n→ 参与 RAG 检索\n(须 status=ready)"),
        (50, "approve\n→ 回答可信展示\n可追溯 trace 查询"),
        (80, "approve\n→ INSERT appointments\n建单(booked, fee=20)"),
    ]
    no = [
        (20, "reject\nreview_status=rejected\n→ 检索永不命中\n可删除/修复重传"),
        (50, "reject\n→ 隐藏/标记不可信\n不对外展示"),
        (80, "reject\n→ 不建单\n用户可重新提交"),
    ]
    for (cx, text), _ in zip(ok, cols):
        _box(ax, cx - 7, 55.5, 13, 9.5, text, C_DATA, fs=8)
    for (cx, text), _ in zip(no, cols):
        _box(ax, cx + 7, 55.5, 13, 9.5, text, "#ffe3e3", ec="#d84f4f", fs=8)

    # 效果 → 审计带
    for cx in (20, 50, 80):
        _arrow(ax, cx - 7, 50.7, cx - 4, 44.5)
        _arrow(ax, cx + 7, 50.7, cx + 4, 44.5)

    # 审计留痕带
    _box(ax, 50, 41.0, 94, 6, "write_audit → audit_logs：动作全量留痕（操作者 / 角色 / action=doc_approved、ai_answer_rejected、appointment_request_approved… / 对象 / 备注 / 时间）", "#eef4ff", ec="#aac4ff", fs=8.8)
    _arrow(ax, 50, 38.0, 50, 36.6)
    _box(ax, 50, 33.5, 70, 5.5, "仅管理员：GET /api/review/audit?action=&target_type=（按动作/对象过滤 + 分页查询）", "#eef4ff", ec="#aac4ff", fs=8.8)

    # 底部说明
    ax.text(50, 18.5,
            "状态机：pending → approved / rejected；已决记录重复复核返回 409；messages / documents / appointment_requests 三表统一 review_status 字段。\n"
            "权限：复核动作仅 doctor / admin 可执行；审计查询仅 admin；reject 必须给出理由，作为责任追溯依据。\n"
            "设计价值：① 知识入库把关——未审核文档不进 RAG 上下文；② 医疗建议把关——AI 回答先审后示；\n"
            "③ 写操作把关——预约单由医生人工确认后建单，杜绝 AI 越权动作。",
            fontsize=8.6, ha="center", va="center", color="#555", linespacing=1.75)
    ax.text(50, 3.2,
            "图例：主线流程 ▼ ｜ 绿/红卡 = approve/reject 生效结果 ｜ 蓝带 = 审计链路（与 4-文档上传入库、9-Agent 流程衔接）",
            fontsize=8.2, ha="center", va="center", color="#888")

    save(fig, "10-人工复核与审计流程图.png")


if __name__ == "__main__":
    fig_system_main()
    fig_login_role()
    fig_rag_chat()
    fig_doc_upload()
    fig_retriever()
    fig_sse_seq()
    fig_deploy()
    fig_lifecycle()
    fig_agent_qa()
    fig_hitl_review()
    print("全部流程图生成完成 ->", os.path.abspath(OUT_DIR))
