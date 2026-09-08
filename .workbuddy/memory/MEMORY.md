# 项目长期记忆

## ⚠️ .git 安全铁律（2026-09-08 事故）
- 对 `.git` 的任何高危操作（`git gc --prune=now`、`git filter-branch`、`rm -rf .git/<子项>`、`git reflog expire`）**必须先整体备份 `.git`**（如 `tar -cf` 或复制到 /tmp），且**不要与 rm/清理命令在同一条 shell 串联**。8-08 一次 gc+清理后 .git 元数据几乎全灭（仅剩 info/objects 空壳），靠远端 clone 重建，8/31~9/8 的 30 个提交历史丢失粒度（合并为单提交 3f4a354），内容零丢失。
- 模型权重/大文件进 git 历史的教训：fetch_model 下载残留（`.tmp_*/...*.incomplete`，1.31GB）曾被误提交，Gitee 单文件 100MB 限制下推送必败，需 filter-branch 剔除。
- 远端：`master` → `git@gitee.com:BLOGSFan/medical_assistant-master.git`（SSH 认证可用）。恢复方法：clone 远端 → 取其 .git 移入项目 → `git add -A` 单提交重建。

## 知识库现状（2026-09-08 更新）
- 用户 9/6~9/8 重组知识库：`backend/data/uploads/` 现 **441 篇 md**（多疾病库 × 公开/私有 各 20 篇），旧 241 篇结构（含妇儿疾病库）已被替换删除。
- 工作树已无 `nginx.conf`、`Dockerfile.backend/frontend`（用户删除并提交）；`docker-compose.yml` 仍在。

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

## Docker 全栈（gunicorn --preload 关键）
- **启动命令**：`gunicorn -c /app/gunicorn.conf.py wsgi:app`（项目根 `gunicorn.conf.py`：`preload_app=True` + `timeout=300` + `post_fork` 钩子把 `backend.rag.vectorstore._store` 重置为 None）。
- **⚠️ fork 安全铁律（2026-08-31 血泪修复）**：`wsgi.py` 模块级 `init_database()` 里的向量库 warmup **必须 `t.join()` 等完成后再 fork**（否则 worker 继承半初始化 torch 状态，SSE 检索在 `embedder.encode` 挂起 90s+ 无响应）；`--preload` 下 master 建立的 pymilvus gRPC 连接绝不能被 4 worker 共享（post_fork 重置单例，各 worker 自建连接）。
- **验证 docker 栈只能走 :3000（frontend nginx）或容器内 exec**：宿主机 `0.0.0.0:8010` 被本地 python（跑 `backend\__main__.py`）抢占，`curl 127.0.0.1:8010` 打到宿主旧库（222 篇无妇儿疾病）。3000 端口属主是 docker 转发器（`::` PID 9340），无本地抢占。
- SSE 经 nginx 必须 `proxy_buffering off; proxy_cache off; chunked_transfer_encoding on;`（`nginx.conf` + `frontend/nginx.conf` 已加），否则 EventSource 收不到增量。
- 容器内 SSE E2E 复验脚本：`scripts/e2e_container_test.py`（登录→建会话 kb_id=12→SSE 流式，统计 data 行/citations）。
- 知识库增量索引脚本：`scripts/index_kb12.py`（只处理 kb_id=12 妇儿疾病，20 篇→20 chunks）。

## 数据规模 / 演示账号
- 12 个疾病知识库（公开）+ 医生私有库（我的临床笔记/疑难病例讨论/用药经验总结/手术记录集/科研文献整理）+ 平台公共私有库 + admin 私有库。
- 文档实际数量 **241 篇**（`backend/data/uploads/<知识库>/公开|私有/`，公开 121 / 私有 120），不是 240 也不是 242。
- 演示账号 patientdemo/doctordemo/nursedemo/publicdemo/admindemo，密码统一 `demo123`；另有 doctor01~16、nurse01~08、patient01~30、public01~05。

## 文档现状
- `README.md`（2026-08-30 重写）：架构图 + RAG 链路 + Agent 协议 + HITL + 角色矩阵 + 部署 + 环境变量 + 排错，全部按代码实测校准。
- **`部署说明.md` 已过时，勿直接照搬**：写了 Redis 服务（docker-compose.yml 里根本没有）、mysql 8.0.40/etcd v3.5.18/milvus v2.5.4 版本号与 compose 实际（8.0 / v3.5.12 / v2.5.6）不符、称 242 篇文档、引用不存在的 `backend/data/kb_docs_src/`。
- `.env.example` 部分变量已失效：`JWT_EXPIRES_HOURS`（config 实际是 `JWT_EXP_HOURS`）、`DATABASE_PATH`、`QUERY_PREFIX`、`QUERY_EXPAND`、`MILVUS_DB` 均未被 config.py 读取。

## 知识库上传（关键点）
- 单文件 `POST /api/kb/<id>/documents` + 批量 `POST /api/kb/<id>/documents/batch`（`files` 字段可重复，最多 200/次；每个失败独立返回不阻塞）。
- `kb_service.upload_document` 写向量前 **必须** `vs = get_vectorstore()`（2026-08-31 修复，之前引用未定义 `vs` 直接 NameError，UI 通道实际上从来不能上传，全靠 `seed_all()` 播种）。
- 前端：单文件 `<el-upload>` 已弃用，`KnowledgeBase.vue` 改用隐藏 `<input type="file" multiple>` + 队列面板（按文件显示状态：上传中/成功N分片/失败悬停看错误）。
- 单请求总大小：`MAX_CONTENT_LENGTH` = 64 MB（`backend/app.py`）。
- 集成验证脚本：`scripts/test_batch_upload.py`（Flask test_client，无需 MySQL），覆盖 happy path + 空文件 + 不存在 KB 三种情形。

## 删除 = 逻辑删除（2026-09-08 约定）
- `DELETE /api/kb/<id>`（`delete_knowledge_base`）与 `DELETE /api/kb/documents/<doc_id>`（`delete_document`）**只删向量 + DB 记录，绝不删 `backend/data/uploads/` 磁盘目录/文件**（用户铁律：前端删文档/知识库不得动本地磁盘源文件，便于重新导入与溯源）。
- 修改点：`backend/services/kb_service.py` 移除 `shutil.rmtree`/`file_path.unlink()` 两段，`import shutil` 已删。
