"""
大模型服务（LLMService）
==================================================================
- 在线：OpenAI 兼容接口（DeepSeek / OpenAI / 通义千问 / Ollama 均可），
  SSE 流式生成；
- 离线兜底：未配置密钥或调用失败时，基于检索到的知识库片段合成结构化回答，
  保证「全链路始终可用」。
"""
import config as cfg


SYSTEM_PROMPT = (
    "你是「医智助手」，一个面向医院信息系统教学场景的医学知识库智能问答助手。"
    "请严格依据下方【参考材料】回答用户问题，做到准确、通俗易懂、不编造。"
    "若材料中无相关内容，请如实说明无法回答，并建议咨询专业医生。"
    "回答末尾必须附上「参考来源」（材料标题）。"
    "重要声明：本回答仅用于医疗健康信息辅助理解，不构成诊断、处方或治疗建议；"
    "实际医疗问题应咨询专业医生。"
)


class LLMService:
    _client = None

    @classmethod
    def client(cls):
        if cls._client is None:
            if cfg.OPENAI_API_KEY:
                try:
                    from openai import OpenAI
                    cls._client = OpenAI(base_url=cfg.OPENAI_BASE_URL, api_key=cfg.OPENAI_API_KEY)
                except Exception:
                    cls._client = False
            else:
                cls._client = False
        return cls._client if cls._client else None

    def stream(self, question: str, chunks: list[dict]):
        context = self._build_context(chunks)
        if self.client() is None:
            yield from self._offline(question, chunks)
            return
        try:
            messages = [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": f"【参考材料】\n{context}\n\n【用户问题】\n{question}"},
            ]
            resp = self.client().chat.completions.create(
                model=cfg.OPENAI_CHAT_MODEL, messages=messages, stream=True, temperature=0.3,
            )
            for part in resp:
                delta = part.choices[0].delta.content
                if delta:
                    yield delta
        except Exception as e:  # noqa
            print(f"[LLM] 在线生成失败，回退离线合成：{e}")
            yield from self._offline(question, chunks)

    def _build_context(self, chunks: list[dict]) -> str:
        lines = []
        for i, c in enumerate(chunks, 1):
            lines.append(f"[{i}] 《{c.get('title','')}》\n{c.get('text','')}")
        return "\n\n".join(lines)

    def _offline(self, question: str, chunks: list[dict]):
        """离线合成：基于检索片段，给出结构化、可追溯的回答。"""
        yield f"（离线模式·基于知识库检索）\n\n"
        yield f"关于您咨询的「{question}」，知识库中相关的内容如下：\n\n"
        for i, c in enumerate(chunks, 1):
            snippet = c.get("text", "").strip()
            if len(snippet) > 400:
                snippet = snippet[:400] + "……"
            yield f"{i}. 来源《{c.get('title','')}》（相似度 {c.get('similarity', 0):.2f}）：\n{snippet}\n\n"
        yield ("\n⚠️ 提示：当前为离线合成回答，仅作信息辅助；如需更精准解读，"
               "请配置大模型接口或咨询专业医生。")
