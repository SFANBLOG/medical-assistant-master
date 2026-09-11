"""
健康教育技能（Health Education Skill）。

生成健康教育内容，用于护理指导与康复宣教。
"""
from backend.agent import tools as toolmod
from backend.agent.skills.base_skill import BaseSkill
from backend.rag.llm import _clean_answer_text
from backend.rag.retriever import build_context


class HealthEducationSkill(BaseSkill):
    name = "health_education"
    description = "基于知识库生成健康教育内容，用于护理指导、康复宣教。"
    required_tools = ["search_knowledge"]

    _EDUCATION_KEYWORDS = [
        "健康教育", "健康宣教", "饮食注意", "日常注意", "生活方式",
        "运动建议", "生活习惯", "保健", "预防", "养生",
    ]

    def execute(self, state: dict, topic: str = "") -> dict:
        """生成健康教育内容。

        Returns:
            dict: {
                "content": str,          # 健康教育内容
                "citations": list,       # 引用列表
                "topic": str,            # 主题
            }
        """
        # 检索相关知识
        toolmod.run_tool(state, "search_knowledge", query=topic, top_k=5)
        hits = state.get("last_hits") or []
        context = build_context(hits) if hits else ""

        citations = []
        for h in hits:
            citations.append({
                "doc_id": h["doc_id"],
                "title": h.get("filename", ""),
                "similarity": h["similarity"],
            })

        return {
            "content": _clean_answer_text(context)[:1500] if context else "",
            "citations": citations,
            "topic": topic,
            "has_content": len(hits) > 0,
        }

    def is_applicable(self, question: str, state: dict) -> bool:
        return any(k in question for k in self._EDUCATION_KEYWORDS)
