# 项目长期记忆

## ⚠️ .git 安全铁律（2026-09-08 事故）
- 对 `.git` 的高危操作（`git gc --prune=now`、`filter-branch`、`rm -rf .git/<子项>`、`reflog expire`）**必须先整体备份 `.git`**，且不可与 rm 串联在同一条 shell。8-08 一次 gc 后 .git 元数据几乎全灭，靠远端 clone 重建。
- 大文件进 git 的教训：模型下载残留（1.31GB `.incomplete`）曾被误提交，Gitee 单文件 100MB 限制下推送必败。
- 远端：`master` → `git@gitee.com:BLOGSFan/medical_assistant-master.git`（SSH 可用）。

## 架构要点（架构 A，唯一活跃运行时）
- 入口 `backend/app.py`（**不是** `backend/app/main.py`）；`python -m backend`（根目录）或 `gunicorn wsgi:app`。端口 8010。
- 用 `backend.config`（模块级）、`backend.routes.*`、`backend/utils/db.py`（MySQL/SQLite 按 `DB_TYPE` 切换）。
- 蓝图 7 个：auth/chat/kb/medical/dashboard/agent/review，前缀 `/api/<name>`。
- `backend/api/`（架构 B）是未接线死代码，勿以它为准。
- 跨库铁律：`backend/utils/db.py` 导出 `NOW_SQL`，所有 `UPDATE ... updated_at` 必须用 f-string `{NOW_SQL}`，**禁止裸写 `NOW()`**；占位符用 `_placeholder()`（`%s` ↔ `?`）；`INT UNSIGNED`+`COMMENT` 是 MySQL 专属，SQLite 走 `INTEGER NULL`。
- 依赖安装必用 `backend/requirements.txt`（根目录那份是 Anaconda 全量 pip freeze，不可用于安装）。
- `backend/services/cache.py`（Redis）是死代码，勿引用。

## 知识库现状（2026-09-17 实测，此前 241/441/481 口径全部作废）
- `backend/data/uploads/` = **12 个疾病库 ×(公开/私有)，共 150 篇 md**（公开 44 + 私有 106）。
- 9/17 起批量扩写：目标 1000+ 字，统一 7 章节（疾病概述/常见症状/常见病因（诱因与危险因素）/诊断要点/一般处理与就医建议/注意事项/预防与日常管理）。
- **已完成 48 篇，平均 2116 字**；剩余 102 篇因 LLM key 失效暂停。备份 `backend/data/uploads_backup_20260917_155236/`。
- 工具链：
  - `scripts/expand_docs.py` 扩写（并发 + 断点续跑 `.expand_progress.json` + 原子写 + 质量闸门字数≥900/章节齐备）
  - `scripts/sync_docs_from_disk.py` **以磁盘为准重建 documents 映射**（预演/`--apply`）
  - `scripts/reindex_vectors.py` 重建向量（要求 BGE，强制 `MILVUS_ENABLE=0`）
  - `scripts/verify_retrieval.py` 检索验证（`retrieve(q, role, user_id, kb_id, top_k)` 需传 role/user_id）
- ⚠️ **DB 与磁盘脱节是老大难**：知识库重组后 `documents.file_path` 仍指旧路径，9/17 实测 483 条记录只有 2 条能命中文件，向量库仅 4 chunk。同步后可检索 2 → **150 条**，重建后 **411 chunks（BGE-base-zh 768 维）**。
- 删除=逻辑删除：`DELETE /api/kb/<id>` 与 `/api/kb/documents/<doc_id>` **只删向量+DB 记录，绝不删磁盘源文件**。

## 环境事实（本机）
- Anaconda python（`C:\huanjing\Anaconda\python.exe`）有 `sentence_transformers 5.6.1` + flask，可用于导入/集成测试与向量重建。
- `backend/.venv` **没有** sentence_transformers → 会走 HashEmbedder（无语义）。
- BGE 模型在 `backend/data/ai_models/`（4.7G，含 bge-base-zh-v1.5 + 2 个 reranker）。
- 本地 MySQL(3306) 通、Milvus(19530) 通常不通 → 实际向量后端是 NumpyStore（`backend/data/numpy_store.pkl`）。
- Ollama 已装但无模型（目录 14K），显卡 RTX 3050 Ti 4GB，不适合批量生成。

## LLM 网关配置（传智 tokenhub）
- **线上/本地统一**：`LLM_BASE_URL=https://tokenhub.itcast.cn/v1`，主力模型 `deepseek-v4-flash`。
- **双命名兼容**：`config.py` 同时认 `LLM_*`（canonical）与 `OPENAI_*`（历史别名）。
  解析优先级 = **真实环境完整对 > .env 完整对 > 真实环境半套 > .env 半套 > 默认**。
  实现要点：必须在 `load_dotenv` **之前**快照 `_ENV_SNAPSHOT`，否则 .env 合并进 `os.environ` 后分不清来源，平台面板配置会被静默忽略。
- **铁律**：BASE_URL / API_KEY / CHAT_MODEL 必须**同一前缀成对**，禁止跨前缀混搭。历史事故：换 key 但 base_url 仍是旧网关 → 401。
- 聊天模型名优先级：`LLM_MODEL > LLM_CHAT_MODEL > OPENAI_CHAT_MODEL`；另有 `LLM_MODEL_MINOR/MAJOR`（记录但未启用）。
- **嵌入模型防误配**（`_resolve_embed_model()`）：只接受 `auto` / 含 `/` 的路径或 repo_id / 含 bge|gte|e5|embedding 关键字的值。**聊天模型名被误配到嵌入位会静默退化成 HashEmbedder（无语义），毁掉 BGE 索引**，故一律丢弃回退 auto 并告警。
- `LLM_MAX_TOKENS=4096` / `LLM_TIMEOUT=180`：推理型模型思考也计 token，给小了会「只思考、不回答」。
- 诊断端点 `GET /api/llm/status`：base_url / chat_model / 掩码 key / online_mode，排 401 先看它。
- tokenhub 实测：`deepseek-v4-flash` 先吐 `reasoning_content` 再吐 `content`，支持 function calling；`pro`/`qwen-*` 常 429。
- **2026-09-17：key `sk-da02…9129` 返回 401 invalid or disabled（持续，非限流）**，旧 DeepSeek key 402 欠费 → 扩写暂停等新 key。
- 验证脚本：`scripts/verify_llm_prefix.py`、`scripts/verify_llm_config.py`。

## Agent 编排层
- `backend/agent/`：orchestrator.py（ReAct，在线最多 6 步 + 离线规则降级）、tools.py（search_knowledge / reverse_geocode / get_weather / query_hospitalizations / query_appointments）、service.py（SSE）。
- 路由：`GET /api/agent/tools`、`POST /api/agent/stream/<conv_id>`。
- SSE 事件：`thought`/`tool_call`/`observation`/`citations`/`message`/`done`/`error`；轨迹存 `messages.agent_steps`。
- 前端 `Chat.vue` 有「智能体模式」开关，`ChatMessage.vue` 渲染可折叠思考时间线。

## 人工复核（HITL）+ 审计
- `review_status ∈ {pending, approved, rejected}`（messages 与 documents）。患者/群众回答→`pending`；医护自答→`approved`；新上传文档→`pending`；播种文档→`approved`。
- 检索只取 `review_status='approved' AND status='ready'`。
- `review_bp`@`/api/review`：待复核列表 + approve/reject（doctor/admin）；`/audit` 仅 admin。审计旁路静默，失败不阻断业务。
- 关键文件：`backend/services/audit_service.py`、`backend/routes/review_bp.py`、`backend/services/chat_service.py`、`backend/services/kb_service.py`、`backend/rag/retriever.py`。

## Docker 全栈
- 启动：`gunicorn -c /app/gunicorn.conf.py wsgi:app`（`preload_app=True` + `timeout=300` + `post_fork` 重置 `backend.rag.vectorstore._store=None`）。
- **fork 安全铁律**：`wsgi.py` 模块级向量库 warmup **必须 `t.join()` 等完再 fork**，否则 worker 继承半初始化 torch 状态，SSE 检索在 `embedder.encode` 挂起 90s+；`--preload` 下 master 的 pymilvus 连接不可被 worker 共享。
- SSE 经 nginx 必须 `proxy_buffering off; proxy_cache off; chunked_transfer_encoding on;`。
- 验证 docker 栈走 :3000（frontend nginx）或容器内 exec，勿用宿主机 8010（常被本地 python 抢占）。
- 脚本：`scripts/e2e_container_test.py`、`scripts/index_kb12.py`。

## PocketBay 部署（已上线 ✅）
- 目标 https://medical-assistant-204c.pocketbay.app（slug `medical-assistant-204c`，deployment 7667）。
- 平台约束：**仅 SQLite + NumpyStore**（无 MySQL/Milvus/Redis）；入口 `gunicorn app:app`（cwd=/app/backend，需 sys.path 注入项目根）；bind 须读 `PORT`/`BACKEND_PORT`（只健康检查 8080）。
- **autosleep**：HTTP 唤醒只返 204；真实唤醒靠 `agent-browser` 点外壳上的「唤醒并继续」（**不在 iframe 内**）。**休眠窗口极短**，唤醒/登录/提问必须在同一次调用内完成。
- 最稳验证路径：浏览器只负责点唤醒，随后立刻用 `C:\Users\23187\pb_tmp\pb_e2e_http3.py` 跑 HTTP E2E。
- `scripts/pack_pocketbay.py`：排除 `backend/data/ai_models`(4.7G)/venv/.git/*.db/numpy_store.pkl；仅 `backend/.env` 允许作为敏感配置；**打包时生成 platform 专用 .env**（`DB_TYPE=sqlite`、`MILVUS_ENABLE=0`、剥 `MYSQL_*`/`MILVUS_*`），不动本地 .env。
- 凭据 `~/.pocketbay/credentials.json` = `{"https://pocketbay.com": {"_device": {"token": "pb_..."}}}`；API host 是 `https://pocketbay.com/api/ai/...`（**非** `api.pocketbay.com`，后者 308）。Cloudflare 拦裸 urllib → 需 Chrome UA。

## agent-browser 铁律
- **`open <url>` 会卡死守护进程**（页面挂休眠实例时 load 不触发）→ 改用 `open`(about:blank) + `eval "location.href='<url>'"`。
- **`find` 不穿透 iframe，`snapshot` 会** → 先 snapshot 拿 ref 再操作 `@eN`；ref 跨命令不可靠，脚本里需动态解析。
- 截图路径必须 Windows 格式（`C:/...`），`/c/...` 报 `os error 3`。
- 卡死恢复：删 `~/.agent-browser/default.*` + `taskkill /F /IM agent-browser-win32-x64.exe`；清遗留 Chromium 须按命令行含 `*agent-browser-chrome*` 精确匹配，**勿误杀用户自己的 Chrome**。

## 演示账号
- patientdemo / doctordemo / nursedemo / publicdemo / admindemo，密码统一 `demo123`；另有 doctor01~16、nurse01~08、patient01~30、public01~05。

## 文档现状
- `README.md`（2026-08-30 重写）按代码实测校准，可信。
- **`部署说明.md` 已过时勿照搬**（写了不存在的 Redis、版本号不符、篇数错误）。
- `.env.example` 多个变量已失效（`JWT_EXPIRES_HOURS`、`DATABASE_PATH`、`QUERY_PREFIX`、`QUERY_EXPAND`、`MILVUS_DB` 均未被 config 读取）。
