"""
Supervisor 智能路由（调度中心）。

替代原有 roles.py 的关键字路由，实现：
  - 在线模式：LLM 意图分类 → 选择最合适的子智能体
  - 离线模式：关键字 + can_handle() 置信度路由（降级兜底）

Supervisor 是 orchestrator.py 的核心组件，负责：
  1. 接收用户问题
  2. 分类意图（在线 LLM / 离线关键字）
  3. 选择子智能体
  4. 委派执行并产出事件流
"""
import json
from typing import Generator, Optional

import requests

from backend import config
from backend.agent.roles import classify_role  # 离线降级
from backend.agent.sub_agents import get_agent, AGENT_REGISTRY

# Supervisor 的 LLM 意图分类提示模板
_CLASSIFY_PROMPT = """你是医智助手的调度中心。根据用户问题和身份，选择最合适的智能体处理。

可选智能体：
- triage: 导诊分诊，症状→科室推荐（关键词：挂哪个科、看什么科、分诊）
- doctor: 诊断参考，用药建议，病历分析（关键词：怎么治、吃什么药、诊断）
- nurse: 护理指导，康复宣教，用药指导（关键词：怎么护理、注意事项、康复）
- knowledge: 纯知识库问答，疾病/症状/健康知识（默认兜底）
- schedule: 排班查询，预约管理（关键词：排班、预约、挂号、出诊时间）
- followup: 复诊随访，慢病管理，术后跟踪（关键词：复诊、复查、随访、慢病）

用户身份：{user_role}
用户问题：{question}

请以 JSON 返回（不要包含其他文字）：
{{"agent": "智能体key", "confidence": 0.0到1.0, "intent": "意图简述"}}"""


class Supervisor:
    """Supervisor 调度中心：意图分类 + 子智能体路由。"""

    def __init__(self):
        self.agents = {k: cls() for k, cls in AGENT_REGISTRY.items()}

    def classify_intent(
        self, question: str, user_role: str, history: Optional[list] = None
    ) -> dict:
        """分类用户意图，返回目标智能体信息。

        在线模式：调用 LLM 做意图分类
        离线降级：调用 can_handle() + 关键字规则
        """
        if config.OPENAI_API_KEY and config.OPENAI_API_KEY not in ("", "sk-xxx"):
            try:
                return self._classify_online(question, user_role, history)
            except Exception:
                pass  # 降级到离线

        return self._classify_offline(question, user_role)

    def _classify_online(
        self, question: str, user_role: str, history: Optional[list]
    ) -> dict:
        """在线模式：LLM 意图分类。"""
        url = f"{config.OPENAI_BASE_URL.rstrip('/')}/chat/completions"
        headers = {
            "Authorization": f"Bearer {config.OPENAI_API_KEY}",
            "Content-Type": "application/json",
        }
        prompt = _CLASSIFY_PROMPT.format(user_role=user_role, question=question)
        payload = {
            "model": config.OPENAI_CHAT_MODEL,
            "messages": [
                {"role": "system", "content": "你是意图分类器，只返回 JSON，不返回其他内容。"},
                {"role": "user", "content": prompt},
            ],
            "temperature": 0.1,
            "max_tokens": 100,
        }
        resp = requests.post(url, headers=headers, json=payload, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        content = data["choices"][0]["message"].get("content", "").strip()

        # 解析 JSON（兼容 markdown code block 包裹）
        if content.startswith("```"):
            content = content.split("\n", 1)[-1].rsplit("```", 1)[0].strip()
        result = json.loads(content)

        agent_key = result.get("agent", "knowledge")
        if agent_key not in AGENT_REGISTRY:
            agent_key = "knowledge"

        return {
            "agent": agent_key,
            "confidence": float(result.get("confidence", 0.8)),
            "intent": result.get("intent", ""),
            "reasoning": f"LLM 分类 → {agent_key}",
        }

    def _classify_offline(self, question: str, user_role: str) -> dict:
        """离线降级：关键字 + can_handle() 置信度路由。"""
        state = {"role": user_role}

        # 先用 can_handle() 遍历所有智能体
        best_key = "knowledge"
        best_score = 0.0
        for key, agent in self.agents.items():
            score = agent.can_handle(question, state)
            if score > best_score:
                best_score = score
                best_key = key

        # 如果所有 can_handle() 都低，用原有关键字路由兜底
        if best_score < 0.3:
            best_key = classify_role(question, user_role)

        return {
            "agent": best_key,
            "confidence": best_score,
            "intent": f"离线分类 → {best_key}",
            "reasoning": f"关键字路由 → {best_key} (score={best_score:.2f})",
        }

    def route(
        self,
        question: str,
        state: dict,
        history: Optional[list] = None,
        memory_ctx: str = "",
    ) -> Generator[dict, None, None]:
        """主入口：分类 → 选择智能体 → 执行 → 产出事件流。"""
        user_role = state.get("role", "public")

        # 1. 意图分类
        classification = self.classify_intent(question, user_role, history)
        agent_key = classification["agent"]
        agent = get_agent(agent_key)

        # 2. 产出路由元信息
        yield {"type": "meta", "role": agent.name, "role_label": agent.label}
        yield {
            "type": "thought",
            "content": f"意图分类：{classification.get('intent', '')}（{classification.get('reasoning', '')}）",
        }

        # 3. 委派给目标子智能体执行
        yield from agent.run(question, state, history, memory_ctx)
