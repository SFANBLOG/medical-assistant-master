"""
大语言模型接口：OpenAI 兼容 API + 离线兜底。

- 在线模式：调用 DeepSeek / OpenAI / 通义千问 / Ollama 等 OpenAI 兼容接口
- 离线模式：基于检索到的知识库片段合成回答（全链路始终可用）

输出规范化：流式产出的 content 会被 `_clean_answer_text` 统一处理，
统一去除 ** 加粗、列表标记、多余空行等 markdown 格式，让回答尽量接近自然语言。
"""
import json
import re
from typing import Generator

import requests

from backend import config


def _build_messages(question: str, context: str, history: list[dict] = None) -> list[dict]:
    """构建 LLM 的 messages 数组。"""
    system_prompt = (
        "你是医智助手，一个专业的医疗知识助手。请根据下方检索到的医学知识库内容回答用户问题。\n"
        "回答要求：\n"
        "1. 仅基于提供的知识库内容作答，不要编造信息；\n"
        "2. 知识库内容不足以回答时，礼貌说明'现有资料无法回答该问题'；\n"
        "3. 回答专业准确、语气温和、通俗易懂；\n"
        "4. 不要使用任何 Markdown 符号：禁止 ** 加粗、禁止 # 标题、禁止以数字加英文句点开头的列表、"
        "禁止以英文短横线 - 或星号 * 开头的项目符号；\n"
        "5. 如需分点，请用中文序号（一、二、三 或 第一、第二）或换行分隔；\n"
        "6. 不要重复输出'以下是回答'之类的标题，直接给出内容；\n"
        "7. 不要在回答正文中添加'参考来源'、'引用'、'出处'等来源说明，系统会在回答下方以独立面板展示所有相关文档及相似度；\n"
        "8. 提醒一句：本回答仅用于健康知识辅助理解，不能替代专业医生的诊断与治疗建议。"
    )
    if context:
        system_prompt += f"\n\n—— 以下为知识库检索到的参考内容 ——\n{context}\n—— 参考内容结束 ——"

    messages = [{"role": "system", "content": system_prompt}]
    if history:
        messages.extend(history[-6:])  # 保留最近 3 轮对话
    messages.append({"role": "user", "content": question})
    return messages


# 用于流式输出后处理的统一清洗规则
_RE_BOLD = re.compile(r"\*\*(.+?)\*\*", re.DOTALL)
_RE_EM = re.compile(r"(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)", re.DOTALL)
_RE_UNDERSCORE_BOLD = re.compile(r"__(.+?)__", re.DOTALL)
_RE_TRIPLE_FENCE = re.compile(r"```.*?```", re.DOTALL)
_RE_INLINE_CODE = re.compile(r"`([^`]+)`")
_RE_HEADING = re.compile(r"(?m)^\s{0,3}#{1,6}\s*")
_RE_HEADING_ANYWHERE = re.compile(r"(?:#{1,6}\s*)+")  # chunk 断裂产生的行内 ## 团
_RE_LIST_DASH_STAR = re.compile(r"(?m)^\s*[-*•]\s+")
_RE_LIST_NUMBER = re.compile(r"(?m)^\s*\d{1,3}\.\s+")
_RE_BRACKET_CITE = re.compile(r"\[(\d{1,3})\]")  # LLM 偶发的 [1] [2] 引用标记
_RE_MULTI_BLANK = re.compile(r"\n{3,}")


def _clean_answer_text(text: str) -> str:
    """统一清洗 LLM 输出，去除 markdown 符号与多余空白。"""
    if not text:
        return text
    s = text
    # 围栏代码块优先移除
    s = _RE_TRIPLE_FENCE.sub("", s)
    s = _RE_INLINE_CODE.sub(r"\1", s)
    # 加粗/斜体统一为正文
    s = _RE_BOLD.sub(r"\1", s)
    s = _RE_UNDERSCORE_BOLD.sub(r"\1", s)
    s = _RE_EM.sub(r"\1", s)
    # 整行标题去掉井号
    s = _RE_HEADING.sub("", s)
    # 行内残留的 ## 团（chunk 边界断裂导致）替换为换行，
    # 保留文档原有的章节分隔，避免标题与正文粘连成“脂肪肝概述脂肪肝是…”
    s = _RE_HEADING_ANYWHERE.sub("\n", s)
    # 列表项目符号归一到中文顿号分隔：把 "- " 替换成 "·" 形式（保留可读性）
    s = _RE_LIST_DASH_STAR.sub("", s)
    # 数字列表去掉 "1. " 等
    s = _RE_LIST_NUMBER.sub("", s)
    # LLM 自创的 [1] [2] 这种引用标记——交给前端的真实 citations 来展示
    s = _RE_BRACKET_CITE.sub("", s)
    # 收敛连续空行
    s = _RE_MULTI_BLANK.sub("\n\n", s)
    return s.strip()


def chat_stream(
    question: str,
    context: str = "",
    history: list[dict] = None,
) -> Generator[str, None, None]:
    """
    流式聊天（SSE 格式）。

    生成器产出: {"content": "..."} 或 {"done": true} 格式的 JSON 字符串行。
    """
    if config.OPENAI_API_KEY and config.OPENAI_API_KEY != "sk-xxx":
        yield from _chat_stream_api(question, context, history)
    else:
        yield from _chat_offline(question, context, history)


def _chat_stream_api(
    question: str,
    context: str,
    history: list[dict],
) -> Generator[str, None, None]:
    """调用 OpenAI 兼容 API 的流式聊天。"""
    messages = _build_messages(question, context, history)
    url = f"{config.OPENAI_BASE_URL.rstrip('/')}/chat/completions"
    headers = {
        "Authorization": f"Bearer {config.OPENAI_API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": config.OPENAI_CHAT_MODEL,
        "messages": messages,
        "stream": True,
        "max_tokens": 2048,
        "temperature": 0.7,
    }

    try:
        resp = requests.post(url, headers=headers, json=payload, stream=True, timeout=60)
        if resp.status_code != 200:
            err = resp.text[:500]
            yield _sse({"error": f"API 返回 {resp.status_code}: {err}"})
            yield from _chat_offline(question, context, history)
            return

        # 累积原始 content，在完整文本边界做清洗，再输出「新增」的干净文本。
        # 避免 Markdown 符号（如 ##、**）被 chunk 边界切断，导致逐 chunk 清洗失效。
        raw_buffer = ""
        clean_buffer = ""
        for line in resp.iter_lines():
            if not line:
                continue
            line = line.decode("utf-8", errors="ignore")
            if not line.startswith("data: "):
                continue
            data = line[6:]
            if data.strip() == "[DONE]":
                break
            try:
                chunk = json.loads(data)
                delta = chunk.get("choices", [{}])[0].get("delta", {})
                content = delta.get("content", "")
                if not content:
                    continue
                raw_buffer += content
                new_clean = _clean_answer_text(raw_buffer)
                if len(new_clean) > len(clean_buffer):
                    delta_clean = new_clean[len(clean_buffer):]
                    clean_buffer = new_clean
                    if delta_clean:
                        yield _sse({"content": delta_clean})
            except json.JSONDecodeError:
                continue

        # 流结束后再整体清洗一次，确保无残留
        final_clean = _clean_answer_text(raw_buffer)
        if len(final_clean) > len(clean_buffer):
            yield _sse({"content": final_clean[len(clean_buffer):]})

        yield _sse({"done": True})

    except requests.exceptions.ConnectionError:
        yield _sse({"error": "无法连接到大模型 API，使用离线兜底回答"})
        yield from _chat_offline(question, context, history)
    except Exception as e:
        yield _sse({"error": f"调用大模型异常: {str(e)}"})
        yield from _chat_offline(question, context, history)


def _chat_offline(
    question: str,
    context: str,
    history: list[dict],
) -> Generator[str, None, None]:
    """离线兜底：基于检索结果合成回答（已应用 markdown 清洗）。"""
    if context:
        answer = (
            "根据知识库检索结果，为您整理以下信息：\n\n"
            f"{context}\n\n"
            "以上内容来自医智助手知识库检索，仅供健康参考，"
            "不能替代专业医生的诊断与治疗建议。如症状持续或加重，请尽快就医。"
        )
    else:
        answer = (
            "抱歉，知识库中未检索到与您问题相关的内容。"
            "您可以尝试：一，换一种方式描述问题；"
            "二，检查对应知识库是否已上传文档；"
            "三，联系医生上传更多相关资料。"
            "本回答仅用于健康参考，不能替代专业医疗诊断。"
        )

    answer = _clean_answer_text(answer)

    # 模拟逐字输出
    for i in range(0, len(answer), 2):
        yield _sse({"content": answer[i:i + 2]})
    yield _sse({"done": True})


def _sse(data: dict) -> str:
    """将 dict 序列化为 SSE data 行。"""
    return f"data: {json.dumps(data, ensure_ascii=False)}"
