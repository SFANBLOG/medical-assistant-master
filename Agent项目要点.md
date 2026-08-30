# Agent 项目要点

> 目标：把现有「医智助手（medical_assistant）」——一个基于 RAG 的医患问答 Web 应用——演进为真正的 **Agent 项目**：以 LLM 为决策中枢，具备**规划、工具调用、记忆、多角色协作、人工复核（HITL）与可观测**能力的智能体系统。
>
> 本文只阐述要点与设计，不改动任何现有代码。所有路径/模块名均对应本仓库现状，便于后续落地时直接映射。

---

## 0. 现状基线（我们要从什么演进）

| 维度 | 当前实现 | Agent 化目标 |
|------|----------|--------------|
| 交互 | 单轮/流式问答（`Chat.vue` + SSE） | 多轮、**有状态**的对话 Agent |
| 推理 | RAG 检索 + 单次生成（`chat_service.py` + `rag/`） | LLM **编排**：先规划、再调用工具、最后综合 |
| 工具 | 仅有 RAG 检索、天气（Open-Meteo） | 工具箱：检索 / 数据库查询 / 外部 API / 业务动作 |
| 角色 | 单一 AI 回答 | 多角色智能体（导诊、医生、护士、知识库） |
| 记忆 | 会话消息落库（`messages` 表） | 短期（会话）+ 长期（用户档案、病史、偏好） |
| 安全 | HITL 复核字段（`review_status`） | 内置**安全护栏** + 强制 HITL 高危动作 |

关键文件（现状）：
- 后端入口：`backend/app/main.py`（`create_app`），路由在 `backend/routes/*`，服务在 `backend/services/*`
- RAG：`backend/rag/retriever.py`（BM25 + 向量 + Cross-Encoder 重排）、`backend/rag/llm.py`（流式 + 清洗）
- 数据：`backend/utils/db.py`（MySQL/SQLite 双库切换）、`backend/models/schema_mysql.sql`
- 前端：`frontend/src/views/Chat.vue`、`frontend/src/components/ChatMessage.vue`、`frontend/src/utils/richtext.ts`
- 复核：`backend/services/audit_service.py`、`backend/routes/review_bp.py`

---

## 1. 总体架构：从「问答管线」到「Agent 运行时」

```
┌─────────────────────────────────────────────────────────────┐
│                      用户 / 前端 (Chat.vue)                    │
└───────────────────────────┬─────────────────────────────────┘
                             │ SSE 流式
┌───────────────────────────▼─────────────────────────────────┐
│                   Agent Orchestrator（编排层）                  │
│  · 意图识别 / 任务规划（Plan）                                  │
│  · 工具选择（Tool Call / Function Calling）                    │
│  · 执行循环：思考 → 调工具 → 观察 → 再思考 …                   │
│  · 终止判断（给出最终答复 or 转人工）                           │
└──────┬──────────────┬───────────────┬───────────────┬────────┘
       │              │               │               │
┌──────▼─────┐ ┌──────▼──────┐ ┌──────▼──────┐ ┌──────▼──────┐
│ 工具箱      │ │  记忆子系统  │ │ 多角色路由   │ │ 安全护栏     │
│ Tools       │ │ Memory      │ │ Roles       │ │ Guardrails  │
└──────┬─────┘ └──────┬──────┘ └──────┬──────┘ └──────┬──────┘
       │              │               │               │
┌──────▼──────────────▼───────────────▼───────────────▼────────┐
│           基础设施：RAG / DB / 外部API / 审计日志 / 模型网关      │
└───────────────────────────────────────────────────────────────┘
```

**落地建议**：在 `backend/services/` 下新增 `agent/` 包（`planner.py` / `executor.py` / `tools.py` / `memory.py` / `guardrails.py`），对外暴露一个新的蓝图 `agent_bp.py`（`/api/agent/...`），现有 `/api/chat` 可逐步收敛为 Agent 的一种「快速问答」模式，保证平滑迁移。

---

## 2. 核心能力一：工具调用（Tool Use / Function Calling）

Agent 必须能**调用外部能力**，而不是只靠参数记忆。建议抽象统一的 `Tool` 接口：

```python
class Tool:
    name: str
    description: str            # 给 LLM 看的自然语言说明
    parameters: dict            # JSON Schema
    async def run(self, **kwargs) -> str
```

### 2.1 应从现有能力封装的工具
| 工具名 | 来源 | 说明 |
|--------|------|------|
| `search_knowledge` | `rag/retriever.py` | 混合检索（BM25+向量+重排），返回带相关度的片段 |
| `get_weather` | `Chat.vue` 的天气逻辑 + Open-Meteo | 入参经纬度/城市，出参天气 |
| `reverse_geocode` | BigDataCloud | 经纬度 → 城市名 |
| `query_patient_records` | `db.py` + `PatientRecordsPage.vue` | 查询患者病历/检查 |
| `query_hospitalizations` | `PatientHospitals.vue` | 查询在院/住院信息 |
| `list_hospitals` / `list_departments` | 现有 API | 导诊用 |
| `create_appointment` | 现有预约 API | 业务动作（**需 HITL**） |
| `human_review` | `review_bp.py` | 把当前回答/动作提交人工复核 |

### 2.2 工具治理
- **声明式注册**：用装饰器/配置集中注册，便于 LLM 看到「工具清单」。
- **超时与降级**：每个工具设 timeout，失败返回结构化错误让 Agent 自我纠正。
- **权限分级**：只读工具可自动调用；写操作（建预约、发短信）必须 HITL。

---

## 3. 核心能力二：记忆（Memory）

| 类型 | 存储介质 | 内容 | 实现映射 |
|------|----------|------|----------|
| 短期（工作记忆） | 会话上下文 | 当前多轮对话、工具中间结果 | 现有 `messages` 表 + 内存 buffer |
| 长期（用户画像） | 数据库/向量库 | 用户身份、慢病史、过敏史、偏好 | 新增 `user_profile` 表或向量化 |
| 长期（知识） | Milvus/知识库 | 医学文档（已有 RAG） | `documents` 表 + 向量索引 |
| 情景记忆 | 审计/日志 | 历史咨询、复核结论 | `audit_service.py` |

**要点**：
- 短期记忆要做**窗口裁剪**（最近 N 轮 + 关键摘要），避免超长上下文。
- 长期记忆在每次回答前**自动注入**相关用户画像（如「该患者有青霉素过敏」），这是医疗安全的硬需求。
- 提供 `remember` / `recall` 工具，让 Agent 显式读写长期记忆。

---

## 4. 核心能力三：多角色智能体（Multi-Agent）

医疗场景天然多角色。建议**主从（Supervisor–Worker）**模式：

```
                    ┌──────────────┐
   用户问题 ───────▶ │  Supervisor  │  （意图分类 + 派单）
                    └──────┬───────┘
          ┌────────┬───────┼────────┬────────┐
          ▼        ▼       ▼        ▼        ▼
     ┌────────┐┌────────┐┌────────┐┌────────┐┌────────┐
     │ 导诊Agent││ 医生Agent││ 护士Agent││ 知识Agent││ 随访Agent│
     └────────┘└────────┘└────────┘└────────┘└────────┘
```

- **导诊 Agent**：识别症状 → 推荐科室/医院（`list_hospitals`/`list_departments`）。
- **医生 Agent**：结合病历+RAG 给诊断建议、用药提醒（**强制 HITL**）。
- **护士 Agent**：护理、用药指导、康复宣教。
- **知识 Agent**：纯 RAG 问答（复用现有检索）。
- **随访 Agent**：定时/触发式健康跟踪（可对接自动化任务）。

**路由策略**：Supervisor 用 LLM 分类 + 规则兜底（如「挂号/预约」必走导诊）。

---

## 5. 核心能力四：规划与推理（Planning & ReAct）

采用 **ReAct（Reason + Act）** 循环，而非一次性生成：

```
Thought: 用户说「我爸糖尿病最近血糖高」，需先了解近期病历，再给建议。
Action: query_patient_records(patient_id, keyword="血糖")
Observation: 近 3 次空腹血糖 8.2 / 9.1 / 10.4 mmol/L，呈上升趋势。
Thought: 血糖偏高且上升，需检索糖尿病管理知识并提示风险。
Action: search_knowledge("2型糖尿病 空腹血糖控制 饮食运动")
Observation: 片段…（带相关度）
Thought: 综合给出生活方式建议 + 提示复诊，因涉及用药调整需人工复核。
Final Answer: …（结构化输出）
```

**关键点**：
- 每个 Thought/Action 通过 **SSE 流式**推给前端，前端用现有 `richtext.ts` 渲染，可展示「思考过程」折叠区。
- 设定**最大步数/超时**，防止无限循环。
- 规划可分层：先出「任务计划」给用户确认，再逐步执行（Plan-and-Execute）。

---

## 6. 安全护栏（医疗场景重中之重）

医疗 Agent 必须满足合规与安全，建议分层护栏：

1. **输入护栏**：识别自伤/紧急（胸痛、昏迷）→ 立即建议就医/呼叫急救，不走常规流程。
2. **知识护栏**：所有医学结论**必须**来自 `search_knowledge` 的检索片段，禁止模型凭空编造（ grounding / citation）。
3. **输出护栏**：
   - 不提供确定性诊断，只给「建议/参考」并提示「以医生为准」。
   - 用药建议强制 HITL（医生复核后才可展示）。
4. **动作护栏**：任何写操作（建预约、发消息）需 `human_review` 工具 + 审计落库（`audit_service.py`）。
5. **可观测**：每次 Agent 轨迹（Thought/Action/Observation）写入审计日志，便于追溯与复诊。

> 现有 `review_status`（`pending/approved/rejected`）与 `audit_service` 已是良好底座，Agent 应**复用并增强**为「每步可审计」。

---

## 7. 前端适配要点（Chat.vue 演进）

现有 `Chat.vue` 已具备：流式输出、建议问题、天气（动态城市）、相关文档区（`ChatMessage.vue`）。Agent 化需增强：

- **步骤可视化**：新增「思考/工具调用」时间线组件（区别于最终回答）。
- **工具调用卡片**：展示 Agent 调用了哪个工具、参数与结果（可折叠）。
- **结构化富文本**：复用 `richtext.ts`（中文序号→有序列表、bullet→无序列表），并扩展「警示框/引用来源」样式。
- **HITL 交互**：在前端增加「医生复核」入口，对接 `review_bp.py`。
- **多 Agent 标识**：消息气泡显示来自哪个 Agent（导诊/医生/护士）。

---

## 8. 数据与模型要点

- **双库兼容**：沿用 `db.py` 的 `DB_TYPE` 切换（MySQL/SQLite），Agent 表（如 `agent_sessions`、`agent_traces`、`user_profile`）加入 `schema_mysql.sql` 与 `schema.sql`，并在 `_run_hitl_migrations()` 同级加迁移函数。
- **模型网关**：在 `backend/rag/llm.py` 基础上抽象 `LLMClient`（支持 Function Calling 的模型），便于切换供应商。
- **检索增强**：RAG 已是核心，Agent 的 `search_knowledge` 直接复用 `retriever.py` 的重排结果，保证答案有据可依。

---

## 9. 评测与迭代

- **离线评测集**：构造医疗问答 + 工具调用轨迹样例，验证规划正确性。
- **答案质量**：引用覆盖率（结论是否都有检索支撑）、HITL 触发准确率。
- **安全红队**：故意输入危险/诱导问题，验证护栏不失效。
- **人工抽检**：复用 `review_bp.py` 的待复核列表做质量抽样。

---

## 10. 落地路线（建议分阶段）

| 阶段 | 目标 | 关键交付 |
|------|------|----------|
| P0 | 工具化 | 抽象 `Tool` 接口，封装 `search_knowledge`/`get_weather`/`query_*` 为工具；新增 `agent_bp.py` | 
| P1 | 单 Agent ReAct | Orchestrator + 规划循环 + SSE 推送思考过程；复用现有 RAG | 
| P2 | 记忆 + 护栏 | 短期裁剪、长期用户画像注入；输入/输出/动作三层护栏 + 强制 HITL | 
| P3 | 多角色 | Supervisor 路由 + 导诊/医生/护士/知识 Agent | 
| P4 | 可观测与评测 | 轨迹落库、评测集、前端步骤可视化与复核 UI | 

---

## 11. 风险与注意

- **幻觉**：医疗场景零容忍，必须 grounding + citation + HITL。
- **隐私**：病历/画像属敏感数据，传输与存储需脱敏与最小化。
- **合规**：AI 不得替代执业医师诊断，输出需明确免责声明。
- **成本/时延**：ReAct 多步调用增加延迟，需并发工具调用与缓存。
- **平滑迁移**：保留现有 `/api/chat` 作为「快速问答」降级路径，避免断服。

---

## 附：与现有代码映射速查

| Agent 概念 | 现有位置 |
|-----------|----------|
| 检索工具 | `backend/rag/retriever.py` |
| 生成/清洗 | `backend/rag/llm.py`（`_clean_answer_text`） |
| 会话/消息 | `backend/services/chat_service.py`、`messages` 表 |
| 复核/HITL | `backend/routes/review_bp.py`、`backend/services/audit_service.py` |
| 数据访问 | `backend/utils/db.py`、双库迁移 |
| 前端渲染 | `frontend/src/components/ChatMessage.vue`、`frontend/src/utils/richtext.ts` |
| 天气/定位 | `frontend/src/views/Chat.vue`（`reverseGeocode` + Open-Meteo） |
| 业务页面 | `frontend/src/pages/*`（患者/预约/排班/知识库等，可作工具后端） |

> 结论：本工程已有 RAG、HITL、双库、流式、天气工具等**良好底座**，向 Agent 演进主要是「加编排层 + 工具化封装 + 记忆/护栏/多角色」，无需推倒重来。
