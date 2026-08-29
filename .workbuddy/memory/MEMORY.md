# 项目长期记忆

## 医智助手（medical_assistant）后端架构要点
- 活跃运行时 = 「架构 A」：`python -m backend` / `gunicorn wsgi:app` → `backend.app.main` → `create_app()`，用 `backend.config`（模块级配置）、`backend.routes.*`、`backend.utils.db`（双库 MySQL/SQLite 自动切换，按 `DB_TYPE`）。
- `backend/api/`（架构 B）是未接线死代码，不要以它为准。
- 数据库默认 `DB_TYPE=mysql`；切 `sqlite` 已验证可用。跨库时间表达式统一用 `_NOW_SQL = "NOW()" if mysql else "datetime('now','localtime')"`，禁止裸写 `NOW()`。

## 人工复核（HITL）+ 审计日志（2026-08-29 加入）
- `review_status ∈ {pending, approved, rejected}` 在 `messages`（AI 回答）与 `documents`（知识库）。
- 默认：患者/群众回答→`pending`；医护/admin 自答→`approved`；新上传文档→`pending`；历史/播种文档→`approved`（默认可检索）。
- 检索只取 `review_status='approved' AND status='ready'`，未复核文档不参与 RAG 上下文。
- 路由蓝图 `review_bp`@`/api/review`：列表待复核 + approve/reject（doctor/admin）；`/audit` 仅 admin。审计写入为旁路静默，失败不阻断业务。
- 关键文件：`backend/services/audit_service.py`、`backend/routes/review_bp.py`、`backend/services/chat_service.py`、`backend/services/kb_service.py`、`backend/rag/retriever.py`、`backend/models/schema_mysql.sql`、`backend/models/schema.sql`。

## 启动/验证
- 依赖环境：本机 anaconda python（`C:\huanjing\Anaconda\python.exe`，含 flask 3.1.3）可用于导入/集成测试；managed python 需自建 venv 装 requirements。
- 改完 DB 相关后：`git add` 已解冲突文件；启动即 `init_schema()`+自动播种（空库时），随后可用 `/api/health`、`/api/review/*` 验证。
