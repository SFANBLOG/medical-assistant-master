"""Agent 包：工具抽象、ReAct 编排器、Agent 服务。

设计目标（见《Agent项目要点.md》P0/P1）：
- 把现有 RAG 检索、天气、业务查询等能力封装为统一 Tool 接口；
- 编排层以 LLM 为决策中枢（在线函数调用 / 离线规则兜底）做 Think-Act-Observe 循环；
- 通过 SSE 把「思考 / 工具调用 / 观察 / 最终回答」逐步推送给前端，并把轨迹存库（可观测）。
"""
from backend.agent import tools, orchestrator, service

__all__ = ["tools", "orchestrator", "service"]
