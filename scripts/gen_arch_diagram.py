# -*- coding: utf-8 -*-
"""医智助手 · 系统总体架构图（参考"维智智能维修决策平台"分层架构图风格）。

分层结构（自顶向下）：
  1) 用户与角色（紫）| 统一接入（蓝）| 外部模型依赖（绿）
  2) API 网关层（蓝）
  3) 核心工作流：RAG 智能问答流水线 1-12 步（橙黄区）+ RAG 核心机制侧栏（紫）
  4) 支撑层：知识工程 / 混合检索与重排 / 数据存储（绿）
  5) 基础带：大模型与基础能力 / 观测与评测 / 安全与权限 + 图例

输出：面试准备/0-系统总体架构图.png
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from gen_flowcharts import (  # noqa: E402
    _arrow, FONT_PATH,
)

import matplotlib  # noqa: E402
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.patches import FancyBboxPatch  # noqa: E402
from matplotlib import font_manager  # noqa: E402

if os.path.exists(FONT_PATH):
    font_manager.fontManager.addfont(FONT_PATH)
    _name = font_manager.FontProperties(fname=FONT_PATH).get_name()
    plt.rcParams["font.family"] = _name
plt.rcParams["axes.unicode_minus"] = False

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "面试准备")
os.makedirs(OUT, exist_ok=True)

# ---------- 分区配色（参考图风格） ----------
ZONE_USER = "#f3e8ff"   # 用户/接入 紫
ZONE_EDGE_USER = "#9a5cd6"
ZONE_ENTRY = "#e8f0fe"  # 入口/API 蓝
ZONE_EDGE_ENTRY = "#2f7ed8"
ZONE_CORE = "#fff8e6"   # 核心工作流 橙黄
ZONE_EDGE_CORE = "#e0a800"
ZONE_SUP = "#eafaf1"    # 支撑 绿
ZONE_EDGE_SUP = "#1f9e7a"
ZONE_BASE = "#fdeeee"   # 底部基础带 浅红边
ZONE_EDGE_BASE = "#d84f4f"
LEG_PURPLE = "#9a5cd6"
LEG_BLUE = "#2f7ed8"
LEG_GREEN = "#1f9e7a"
LEG_ORANGE = "#e0a800"
LEG_RED = "#d84f4f"


def _zone(ax, cx, cy, w, h, fc, ec, title=None, fs_title=10, lw=1.6):
    """大分区背景框（圆角、可带标题）。"""
    p = FancyBboxPatch((cx - w / 2, cy - h / 2), w, h,
                       boxstyle="round,pad=0.03,rounding_size=0.6",
                       fc=fc, ec=ec, lw=lw, zorder=1)
    ax.add_patch(p)
    if title:
        ax.text(cx, cy + h / 2 - 1.4, title, ha="center", va="center",
                fontsize=fs_title, color=ec, weight="bold", zorder=3)


def _lines(ax, cx, cy, w, h, lines, fs=8, tc="#222222", lw_ec="#333333", zorder=2):
    """区内多行小文字块（透明底，仅文字）。"""
    n = len(lines)
    ax.text(cx, cy, "\n".join(lines), ha="center", va="center",
            fontsize=fs, color=tc, linespacing=1.65, zorder=zorder)


def _note_box(ax, cx, cy, w, h, lines, fc, ec, fs=8, tc="#222222"):
    """带边框小卡片。"""
    p = FancyBboxPatch((cx - w / 2, cy - h / 2), w, h,
                       boxstyle="round,pad=0.02,rounding_size=0.3",
                       fc=fc, ec=ec, lw=1.2, zorder=2)
    ax.add_patch(p)
    ax.text(cx, cy, "\n".join(lines), ha="center", va="center",
            fontsize=fs, color=tc, linespacing=1.6, zorder=3)


def main():
    fig, ax = plt.subplots(figsize=(16, 12.6))
    ax.set_xlim(0, 100)
    ax.set_ylim(0, 114)
    ax.set_xticks([])
    ax.set_yticks([])
    for s in ax.spines.values():
        s.set_visible(False)

    # ================= 1) 顶带：用户 / 接入 / 外部依赖 =================
    _zone(ax, 16, 108.8, 28, 6.6, ZONE_USER, ZONE_EDGE_USER)
    _lines(ax, 16, 108.8, 0, 0, [
        "① 用户与角色（5 类门户）",
        "患者 · 医生 · 护士 · 群众 · 管理员",
    ], fs=8.2, tc="#6b3fa0")
    _zone(ax, 49, 108.8, 34, 6.6, ZONE_ENTRY, ZONE_EDGE_ENTRY)
    _lines(ax, 49, 108.8, 0, 0, [
        "② 统一接入：Vue 3 单页应用",
        "Element Plus · Pinia · Router · SSE 客户端",
    ], fs=8.2, tc="#1f5aa8")
    _zone(ax, 82, 108.8, 28, 6.6, ZONE_SUP, ZONE_EDGE_SUP)
    _lines(ax, 82, 108.8, 0, 0, [
        "③ 外部模型依赖",
        "OpenAI 兼容 LLM（DeepSeek/通义/Ollama）",
        "BGE 向量模型（本地推理）",
    ], fs=8.2, tc="#14684f")

    # 顶带下箭头 → API 网关带
    _arrow(ax, 16, 105.5, 16, 103.6, color=LEG_PURPLE, lw=1.8)   # 用户输入（紫）
    _arrow(ax, 49, 105.5, 49, 103.6, color=LEG_PURPLE, lw=1.8)   # SPA 请求（紫）
    _arrow(ax, 88, 105.5, 88, 103.6, color="#999999", lw=1.4, ls="dashed")  # LLM 出站

    # ================= 2) API 网关层 =================
    _zone(ax, 50, 100.5, 94, 6.6, ZONE_ENTRY, ZONE_EDGE_ENTRY)
    _lines(ax, 50, 100.5, 0, 0, [
        "API 网关层：Flask Blueprints · JWT 鉴权 · RBAC 角色校验（require_roles）· SSE 流式",
        "/api/auth ｜ /api/chat ｜ /api/kb ｜ /api/medical ｜ /api/dashboard ｜ /api/review",
    ], fs=8.2, tc="#1f5aa8")

    # ================= 3) 核心橙黄区：RAG 问答流水线 12 步 =================
    _zone(ax, 33.25, 68.75, 62.5, 51.5, ZONE_CORE, ZONE_EDGE_CORE,
          title="核心：RAG 智能问答流水线（1-12 步 · chat_service 驱动）", fs_title=10)
    # 主入口箭头（API → 核心）
    _arrow(ax, 11.5, 97.3, 11.5, 92.6, color=LEG_BLUE, lw=2.0)

    # 12 个步骤（蛇形排布）
    steps = [
        # (行, x, 编号文本行1, 行2)
        (1, 11.5, "1. 提问入口", "POST /api/chat/stream"),
        (1, 33.5, "2. 输入护栏", "急危重症状→急救指引"),
        (1, 55.5, "3. 画像注入", "近期病史 · 预约"),
        (2, 55.5, "4. 权限裁剪", "按角色算可见知识库"),
        (2, 33.5, "5. 双路召回", "BM25∪BGE Top-30"),
        (2, 11.5, "6. 融合重排 v4", "实体地板 · 证据分"),
        (3, 11.5, "7. HITL 过滤", "仅 approved&ready"),
        (3, 33.5, "8. 上下文构建", "build_context +引用"),
        (3, 55.5, "9. LLM 流式生成", "无 Key 离线兜底"),
        (4, 55.5, "10. 输出护栏", "ensure_disclaimer"),
        (4, 33.5, "11. 持久化", "messages + citations"),
        (4, 11.5, "12. 复核+审计", "review_status / audit_logs"),
    ]
    row_y = {1: 87, 2: 78, 3: 69, 4: 60}
    for r, x, t1, t2 in steps:
        _note_box(ax, x, row_y[r], 16.2, 6.8, [t1, t2],
                  "#ffffff", ZONE_EDGE_CORE, fs=7.6)

    # 蛇形连线
    _arrow(ax, 19.6, 87, 26.2, 87, color=LEG_ORANGE, lw=1.8)            # 1→2
    _arrow(ax, 41.6, 87, 48.2, 87, color=LEG_ORANGE, lw=1.8)            # 2→3
    _arrow(ax, 55.5, 83.6, 55.5, 81.4, color=LEG_ORANGE, lw=1.8)        # 3→4
    _arrow(ax, 48.2, 78, 41.6, 78, color=LEG_ORANGE, lw=1.8)            # 4→5
    _arrow(ax, 26.2, 78, 19.6, 78, color=LEG_ORANGE, lw=1.8)            # 5→6
    _arrow(ax, 11.5, 74.6, 11.5, 72.4, color=LEG_ORANGE, lw=1.8)        # 6→7
    _arrow(ax, 19.6, 69, 26.2, 69, color=LEG_ORANGE, lw=1.8)            # 7→8
    _arrow(ax, 41.6, 69, 48.2, 69, color=LEG_ORANGE, lw=1.8)            # 8→9
    _arrow(ax, 55.5, 65.6, 55.5, 63.4, color=LEG_ORANGE, lw=1.8)        # 9→10
    _arrow(ax, 48.2, 60, 41.6, 60, color=LEG_ORANGE, lw=1.8)            # 10→11
    _arrow(ax, 26.2, 60, 19.6, 60, color=LEG_ORANGE, lw=1.8)            # 11→12

    # 结果输出带（橙区内底部）
    _note_box(ax, 33.5, 49, 56, 6.2,
              ["结果输出：SSE 扁平帧（citations 引用帧 → content 增量帧 → done 结束帧，异常 error 帧）→ 前端打字机渲染",
               "持久化 messages + citations → 患者/群众回答进入复核队列（医护/admin 默认 approved）"],
              "#ffffff", ZONE_EDGE_CORE, fs=7.4)
    _arrow(ax, 11.5, 56.6, 11.5, 52.3, color=LEG_ORANGE, lw=1.8)        # 12→输出带

    # ================= 4) RAG 核心机制（右紫侧栏） =================
    _zone(ax, 82, 68.75, 30, 51.5, ZONE_USER, ZONE_EDGE_USER,
          title="RAG 核心机制", fs_title=10)
    _arrow(ax, 64.7, 74, 66.9, 74, color=LEG_PURPLE, lw=1.8)            # 核心区→侧栏
    mech = [
        "输入护栏：急危重症关键词命中\n直接返回急救指引（跳过检索与 LLM）",
        "输出护栏：ensure_disclaimer\n每条回答强制附带免责声明",
        "用户画像注入：get_enhanced_user_context\n近期住院诊断 / 预约 / 上次咨询摘要",
        "混合检索：BM25(jieba) ∪ BGE 稠密向量\n融合重排 v4（实体地板 + 证据分）",
        "多级降级：无 Key / 无 Milvus / 无 BGE\n自动走离线规则链路",
        "HITL 与审计：复核三通道（文档/回答/预约）\naudit_logs 全量留痕",
    ]
    mech_y = [88.6, 82.2, 75.8, 69.4, 63.0, 56.6]
    for txt, yy in zip(mech, mech_y):
        _note_box(ax, 82, yy, 26.5, 4.9, txt.split("\n"),
                  "#ffffff", ZONE_EDGE_USER, fs=7.2, tc="#5a2d8a")

    # ================= 5) 支撑层（绿）：知识工程 / 检索重排 / 数据存储 =================
    _zone(ax, 13, 33.2, 20, 14.5, ZONE_SUP, ZONE_EDGE_SUP, title="知识工程", fs_title=9)
    _lines(ax, 13, 32.6, 0, 0, [
        "· 12 个知识库 · 241 篇医学文档",
        "· txt/md/pdf/docx/pptx 解析清洗",
        "· chunk 切分(500/80) → bge 向量化",
        "· 上传默认 pending 待复核",
    ], fs=7.4, tc="#14684f")
    _zone(ax, 36, 33.2, 20, 14.5, ZONE_SUP, ZONE_EDGE_SUP, title="混合检索与重排 v4", fs_title=9)
    _lines(ax, 36, 32.6, 0, 0, [
        "· BM25(jieba) ∪ BGE 双路 Top-30",
        "· 融合重排 0.55/0.30/0.15 + 实体地板",
        "· ≥0.45 → Top-8（仅 approved&ready）",
        "· build_context ≤4000 字符",
    ], fs=7.4, tc="#14684f")
    _zone(ax, 59, 33.2, 20, 14.5, ZONE_SUP, ZONE_EDGE_SUP, title="数据存储", fs_title=9)
    _lines(ax, 59, 32.6, 0, 0, [
        "· MySQL 8：17 表（16 静态 + 动态复核表）",
        "· 向量库：Milvus / NumpyStore 降级",
        "· uploads 本地文件（公开/私有目录）",
        "· 状态机：pending → approved/rejected",
    ], fs=7.4, tc="#14684f")

    # 输出带 → 支撑层（数据流，绿色）
    _arrow(ax, 13, 45.9, 13, 40.7, color=LEG_GREEN, lw=1.8)
    _arrow(ax, 36, 45.9, 36, 40.7, color=LEG_GREEN, lw=1.8)
    _arrow(ax, 59, 45.9, 59, 40.7, color=LEG_GREEN, lw=1.8)

    # ================= 6) 底部基础带 =================
    _zone(ax, 13, 14.5, 20, 13, ZONE_BASE, ZONE_EDGE_BASE, title="大模型与基础能力", fs_title=9)
    _lines(ax, 13, 14.2, 0, 0, [
        "· OpenAI 兼容 LLM（DeepSeek 等）",
        "· 无 API Key → 离线摘要兜底",
        "· bge-base-zh-v1.5 本地推理 768 维",
        "· Milvus 未启动 → NumpyStore 降级",
    ], fs=7.3, tc="#8f2f2f")
    _zone(ax, 36, 14.5, 20, 13, ZONE_BASE, ZONE_EDGE_BASE, title="观测与评测", fs_title=9)
    _lines(ax, 36, 14.2, 0, 0, [
        "· SSE 帧级可观测（citations/content/done）",
        "· citations 引用溯源到文档片段",
        "· 本地 42 问评测：重排 Hit@1=100%",
        "· 平均分 ≈0.94 · 阈值 0.45 干净切分",
    ], fs=7.3, tc="#8f2f2f")
    _zone(ax, 59, 14.5, 20, 13, ZONE_BASE, ZONE_EDGE_BASE, title="安全与权限", fs_title=9)
    _lines(ax, 59, 14.2, 0, 0, [
        "· JWT + RBAC 五角色装饰器校验",
        "· 公开/私有可见性过滤下推检索",
        "· HITL 人工复核：documents/messages",
        "· audit_logs 全量审计（仅 admin 查询）",
    ], fs=7.3, tc="#8f2f2f")

    # 支撑层 → 底部基础带（能力供给，虚线灰）
    for x0 in (13, 36, 59):
        _arrow(ax, x0, 25.9, x0, 21.2, color="#bbbbbb", lw=1.2, ls="dashed")

    # ================= 7) 图例区 =================
    _zone(ax, 82, 14.5, 30, 13, "#fafafa", "#aaaaaa", title="图例", fs_title=9.5)
    legend = [
        (LEG_PURPLE, "紫色箭头：用户输入 / 角色分流"),
        (LEG_BLUE, "蓝色箭头：API 请求 / SSE 返回"),
        (LEG_ORANGE, "橙色箭头：RAG 核心问答流水线"),
        (LEG_GREEN, "绿色箭头：数据流 / 持久化"),
        (LEG_RED, "红框/红线：人工复核干预(HITL)"),
    ]
    for i, (color, txt) in enumerate(legend):
        yy = 20.4 - i * 3.15
        ax.plot([69.5, 73.5], [yy, yy], color=color, lw=2.4, zorder=3)
        ax.text(74.2, yy, txt, fontsize=7.6, ha="left", va="center", color="#333", zorder=3)
    ax.text(82, 5.2,
            "说明：1-12 步为一次 RAG 问答的主干流水线；人工复核（红）贯穿文档入库、AI 回答与写操作三个环节，全部动作留痕审计。",
            fontsize=7.4, ha="center", va="center", color="#666", zorder=3)

    # 底部标题
    ax.text(50, 2.2,
            "医智助手 · 基于 RAG 的医疗知识库智能问答系统 —— 系统总体架构",
            fontsize=11, ha="center", va="center", color="#1a1a1a", weight="bold", zorder=3)

    path = os.path.join(OUT, "0-系统总体架构图.png")
    fig.savefig(path, dpi=180, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    print("saved:", os.path.abspath(path))


if __name__ == "__main__":
    main()
