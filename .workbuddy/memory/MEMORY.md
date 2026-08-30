# 项目长期记忆

## 医智助手（medical_assistant）后端架构要点
- 活跃运行时 = 「架构 A」：`python -m backend`（根目录执行）/`gunicorn wsgi:app` → **入口文件是 `backend/app.py`**（不是 `backend/app/main.py`），用 `backend.config`（模块级配置）、`backend.routes.*`、`backend/utils/db.py`（双库 MySQL/SQLite，按 `DB_TYPE` 切换）。端口 8010。
- 蓝图共 7 个：auth/chat/kb/medical/dashboard/agent/review，前缀均为 `/api/<name>`。
- `backend/api/`（架构 B）是未接线死代码，不要以它为准。
- 跨库时间表达式统一用 `_NOW_SQL = "NOW()" if mysql else "datetime('now','localtime')"`，禁止裸写 `NOW()`；占位符用 `_placeholder()`（`%s` ↔ `?`）。

## Agent 编排层（已落地，非设想）
- `backend/agent/`：orchestrator.py（ReAct，在线最多 6 步 + 离线规则式降级）、tools.py（5 工具：search_knowledge / reverse_geocode / get_weather / query_hospitalizations / query_appointments）、service.py（SSE 封装）。
- `agent_bp` 路由：`GET /api/agent/tools`、`POST /api/agent/stream/<conv_id>`。
- SSE 事件协议：`thought` / `tool_call` / `observation` / `citations` / `message` / `done` / `error`。轨迹存 `messages.agent_steps`。
- 前端已接线：`Chat.vue` 有「智能体模式」开关（`agentMode`），`ChatMessage.vue` 渲染可折叠思考时间线。

## 依赖安装（坑）
- **必须用 `backend/requirements.txt`**。根目录 `requirements.txt` 是本机 Anaconda 全量 `pip freeze` 产物（几百行、含本地 file:// 路径），不可用于安装。
- `backend/services/cache.py`（Redis 缓存）是死代码：无任何模块 import，且首行 `from config import Config` 在架构 A 下必然 ImportError。不要引用它。

## 人工复核（HITL）+ 审计日志（2026-08-29 加入）
- `review_status ∈ {pending, approved, rejected}` 在 `messages`（AI 回答）与 `documents`（知识库）。
- 默认：患者/群众回答→`pending`；医护/admin 自答→`approved`；新上传文档→`pending`；历史/播种文档→`approved`（默认可检索）。
- 检索只取 `review_status='approved' AND status='ready'`，未复核文档不参与 RAG 上下文。
- 路由蓝图 `review_bp`@`/api/review`：列表待复核 + approve/reject（doctor/admin）；`/audit` 仅 admin。审计写入为旁路静默，失败不阻断业务。
- 关键文件：`backend/services/audit_service.py`、`backend/routes/review_bp.py`、`backend/services/chat_service.py`、`backend/services/kb_service.py`、`backend/rag/retriever.py`、`backend/models/schema_mysql.sql`、`backend/models/schema.sql`。

## 启动/验证
- 依赖环境：本机 anaconda python（`C:\huanjing\Anaconda\python.exe`，含 flask 3.1.3）可用于导入/集成测试；managed python 需自建 venv 装 requirements。
- 启动即 `init_schema()`+自动播种（空库时），随后可用 `/api/health`、`/api/vector/status`、`/api/review/*` 验证。
- 前端：`vite.config.ts` 已配 `/api` → `http://127.0.0.1:8010` 代理，dev 端口 5173。

## 数据规模 / 演示账号
- 12 个疾病知识库（公开）+ 医生私有库（我的临床笔记/疑难病例讨论/用药经验总结/手术记录集/科研文献整理）+ 平台公共私有库 + admin 私有库。
- 文档实际数量 **241 篇**（`backend/data/uploads/<知识库>/公开|私有/`，公开 121 / 私有 120），不是 240 也不是 242。
- 演示账号 patientdemo/doctordemo/nursedemo/publicdemo/admindemo，密码统一 `demo123`；另有 doctor01~16、nurse01~08、patient01~30、public01~05。

## 文档现状
- `README.md`（2026-08-30 重写）：架构图 + RAG 链路 + Agent 协议 + HITL + 角色矩阵 + 部署 + 环境变量 + 排错，全部按代码实测校准。
- **`部署说明.md` 已过时，勿直接照搬**：写了 Redis 服务（docker-compose.yml 里根本没有）、mysql 8.0.40/etcd v3.5.18/milvus v2.5.4 版本号与 compose 实际（8.0 / v3.5.12 / v2.5.6）不符、称 242 篇文档、引用不存在的 `backend/data/kb_docs_src/`。
- `.env.example` 部分变量已失效：`JWT_EXPIRES_HOURS`（config 实际是 `JWT_EXP_HOURS`）、`DATABASE_PATH`、`QUERY_PREFIX`、`QUERY_EXPAND`、`MILVUS_DB` 均未被 config.py 读取。
