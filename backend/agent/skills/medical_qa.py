"""
医学知识问答技能（Medical QA Skill）。

基于 RAG 的医学知识问答，被多个智能体复用。
"""
from backend.agent.skills.base_skill import BaseSkill
from backend.agent import tools as toolmod
from backend.rag.retriever import build_context
from backend.rag.llm import _clean_answer_text


class MedicalQASkill(BaseSkill):
    name = "medical_qa"
    description = "基于 RAG 的医学知识问答，检索知识库并返回带引用的回答上下文。"
    required_tools = ["search_knowledge"]

    def execute(self, state: dict, query: str = "", top_k: int = 5) -> dict:
        """执行 RAG 检索问答。

        Returns:
            dict: {
                "context": str,          # 检索到的上下文文本
                "citations": list,       # 引用列表
                "has_results": bool,     # 是否有检索结果
                "hit_count": int,        # 命中条数
            }
        """
        if not query:
            query = state.get("_current_question", "")

        obs = toolmod.run_tool(state, "search_knowledge", query=query, top_k=top_k)
        hits = state.get("last_hits") or []
        context = build_context(hits) if hits else ""

        citations = []
        for h in hits:
            citations.append({
                "doc_id": h["doc_id"],
                "chunk_index": h.get("chunk_index", 0),
                "source_text": _clean_answer_text(h["text"])[:200],
                "title": h.get("filename", ""),
                "similarity": h["similarity"],
            })

        return {
            "context": context,
            "citations": citations,
            "has_results": len(hits) > 0,
            "hit_count": len(hits),
            "raw_observation": obs,
        }

    def is_applicable(self, question: str, state: dict) -> bool:
        """医学知识问答适用于大多数医学相关问题。"""
        # 排除纯业务查询（预约/排班等由其他技能处理）
        non_qa_keywords = ["帮我预约", "帮我挂号", "查排班", "查预约"]
        if any(k in question for k in non_qa_keywords):
            return False
        return True
