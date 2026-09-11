"""
知识智能体（Knowledge Agent）。

职责：纯 RAG 问答，基于医学知识库回答疾病、症状、用药、护理等健康问答。
作为其他智能体的委派目标（delegate target），也是默认兜底智能体。
"""
from backend.agent.base_agent import BaseAgent
from backend.agent.guardrails import DISCLAIMER
from backend.rag.llm import _clean_answer_text
from backend.rag.retriever import build_context


class KnowledgeAgent(BaseAgent):
    name = "knowledge"
    label = "知识智能体"
    allowed_tools = ["search_knowledge"]
    system_prompt = (
        "你是医智助手的【知识智能体】。依据医学知识库回答疾病、症状、用药、护理等健康问答。"
        "必须先调用 search_knowledge 检索，禁止凭空编造；使用中文序号分点，通俗易懂。"
    )

    def can_handle(self, question: str, state: dict) -> float:
        """知识智能体作为兜底，任何非紧急问题都有一定处理能力。"""
        return 0.3  # 基础置信度，其他智能体都不匹配时由它处理

    def plan(self, question: str, state: dict) -> list[dict]:
        return [
            {
                "type": "tool",
                "tool_name": "search_knowledge",
                "args": {"query": question, "top_k": 5},
                "reasoning": "检索医学知识库获取权威资料。",
            },
            {"type": "synthesize", "reasoning": "基于检索结果合成回答。"},
        ]

    def synthesize(self, question: str, state: dict) -> str:
        hits = state.get("last_hits") or []
        context = build_context(hits) if hits else ""
        header = "根据知识库检索结果，为您整理以下信息：\n\n"
        if context:
            body = header + _clean_answer_text(context)[:1500]
        else:
            body = (
                "抱歉，知识库中未检索到与您问题相关的内容。您可以尝试："
                "一，换一种方式描述问题；二，检查对应知识库是否已上传文档；"
                "三，联系医生上传更多相关资料。"
            )
        return body + "\n\n" + DISCLAIMER
