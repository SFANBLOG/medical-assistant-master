"""LLM / Embedding 提供者抽象。

两种实现：
- OpenAICompatLLM    ：对接任意 OpenAI 兼容接口（/chat/completions 流式、本地embedding）
- OfflineFallbackLLM ：未配置密钥时的离线兜底。embedding 使用确定性哈希词袋向量，
                      chat 由 chat_service 依据检索片段合成答案。
"""
import hashlib
import json
import logging
import os
from abc import ABC, abstractmethod
from typing import Iterator

import numpy as np
import requests

logger = logging.getLogger(__name__)

# 注意：必须用项目自带的分词函数（utils.text_utils.tokenize），
# 而不是 Python 标准库的 tokenize 模块，否则 hash_embed 会调用错误的签名。
from utils.text_utils import tokenize as split_tokens


class LLMProvider(ABC):
    @abstractmethod
    def is_available(self) -> bool:
        """是否可调用真实大模型。"""

    @abstractmethod
    def chat_stream(self, messages: list[dict]) -> Iterator[str]:
        """按 token 流式返回回答增量。"""

    @abstractmethod
    def embed(self, texts: list[str], query: bool = False) -> list[list[float]]:
        """一次调用返回 N 条向量。query=True 表示输入为检索提问（部分模型需指令前缀）。"""


class OpenAICompatLLM(LLMProvider):
    def __init__(self, cfg):
        self.base_url = cfg["OPENAI_BASE_URL"]
        self.api_key = cfg["OPENAI_API_KEY"]
        self.chat_model = cfg["OPENAI_CHAT_MODEL"]
        self.embed_model = cfg["OPENAI_EMBED_MODEL"]
        self.dim = cfg["EMBED_DIM"]
        self.timeout = 120

        self._local_embedder = None
        # 检索提问的指令前缀（query instruction）。
        # ⚠️ bge-*-zh-v1.5 官方说明：v1.5 系列已优化「不加指令」的检索能力，
        # 不加前缀召回更稳定、相似度更高（实测 bge-base-zh-v1.5 无前缀 0.75 vs 有前缀 0.63）。
        # 因此默认关闭前缀，可通过 .env 的 QUERY_PREFIX 显式开启（如 bge-large-zh 老版本）。
        self.query_prefix = cfg.get("QUERY_PREFIX", "") or ""
        # 检索提问的扩展变体：把原始提问再拼上关键词，用于多变体 max-pool 召回
        self.query_expand = cfg.get("QUERY_EXPAND", "1") not in ("0", "false", "False")
        # 判断是否为本地 sentence-transformers 模型（本地目录 或 bge-*/all-* 模型 id）；
        # 加载失败不阻断，后面会走哈希兜底
        local_prefix = ("all-", "bge-", "BAAI/bge-", "sentence-transformers/")
        is_local_dir = self.embed_model and os.path.isdir(self.embed_model)
        if self.embed_model and (is_local_dir or self.embed_model.startswith(local_prefix)):
            try:
                from sentence_transformers import SentenceTransformer

                self._local_embedder = SentenceTransformer(self.embed_model)
                # 兼容新旧 API：sentence-transformers 5.x 将方法改名为 get_embedding_dimension
                _dim_fn = getattr(self._local_embedder, "get_embedding_dimension", None) \
                    or self._local_embedder.get_sentence_embedding_dimension
                logger.info(f"本地向量模型加载成功：{self.embed_model} "
                            f"dim={_dim_fn()}")
            except Exception as e:  # noqa: BLE001 模型下载失败/未安装均降级
                self._local_embedder = None
                logger.warning(
                    f"本地向量模型 {self.embed_model!r} 加载失败，将使用哈希向量兜底"
                    f"（语义检索效果差、匹配分数低）。请检查 .env 中 OPENAI_EMBED_MODEL "
                    f"是否指向真实存在的模型目录，或先运行 python download_model.py。错误：{e}"
                )

    def is_available(self) -> bool:
        return True

    def _headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    def chat_stream(self, messages: list[dict]) -> Iterator[str]:
        url = f"{self.base_url}/chat/completions"
        payload = {"model": self.chat_model, "messages": messages, "stream": True}
        resp = requests.post(url, headers=self._headers(), json=payload,
                             stream=True, timeout=self.timeout)
        resp.raise_for_status()
        for line in resp.iter_lines(decode_unicode=True):
            if not line or not line.startswith("data:"):
                continue
            data = line[5:].strip()
            if data == "[DONE]":
                break
            try:
                chunk = json.loads(data)
            except json.JSONDecodeError:
                continue
            choices = chunk.get("choices") or []
            if choices:
                delta = choices[0].get("delta") or {}
                content = delta.get("content")
                if content:
                    yield content

    def _warn_hash_fallback(self) -> None:
        """哈希向量兜底时发出醒目告警（避免误配置被静默吞掉导致低分检索）。"""
        logger.warning(
            "⚠️ 向量模型 %r 未生效（本地模型加载失败 / 未配置 / 远程 /embeddings 不可用），"
            "已回退确定性哈希向量：语义检索相似度分数会显著偏低（约 0.3~0.5）。"
            "请检查 .env 的 OPENAI_EMBED_MODEL 是否指向真实存在的本地模型目录"
            "（如 data/models/bge-base-zh-v1.5），或改用提供 /embeddings 接口的 OPENAI_BASE_URL。",
            self.embed_model,
        )

    def embed_query_variants(self, question: str) -> list[list[float]]:
        """检索提问的多个向量变体（原始 / 指令前缀 / 关键词扩展）。

        返回与 texts 一一对应的向量列表，供召回时对每个候选片段取最大相似度
        （max-pool over variants），显著提升正确文档的召回分数。
        """
        variants: list[str] = [question]
        if self.query_prefix:
            variants.append(self.query_prefix + question)
        if self.query_expand:
            from utils.text_utils import tokenize

            toks = tokenize(question)
            if toks:
                variants.append(" ".join(toks[:40]))
        return self.embed(variants, query=False)

    def embed(self, texts: list[str], query: bool = False) -> list[list[float]]:
        # 检索提问侧：仅在显式开启指令前缀时追加（bge-*-zh-v1.5 默认不加）
        inputs = texts
        if query and self.query_prefix:
            inputs = [self.query_prefix + t for t in texts]
        # 1) 本地 Embedding 模型（all-*/bge-*）优先；失败则降级哈希向量
        if self._local_embedder is not None:
            try:
                return _normalize_rows(self._local_embedder.encode(inputs).tolist())
            except Exception:  # noqa: BLE001
                self._local_embedder = None
        # 2) 未配置向量模型 -> 使用确定性哈希向量（离线可用，索引/查询维度一致）
        if not self.embed_model:
            self._warn_hash_fallback()
            return [hash_embed(t, self.dim) for t in texts]
        # 3) 远程 /embeddings 接口（OpenAI 等支持者）。任何异常（如 DeepSeek 无此接口）
        #    都回退到哈希向量，保证上传、检索链路始终可用。
        try:
            url = f"{self.base_url}/embeddings"
            payload = {"model": self.embed_model, "input": inputs}
            resp = requests.post(url, headers=self._headers(), json=payload, timeout=self.timeout)
            resp.raise_for_status()
            body = resp.json()
            ranked = sorted(body["data"], key=lambda item: item["index"])
            return _normalize_rows([item["embedding"] for item in ranked])
        except Exception as e:  # noqa: BLE001
            self._warn_hash_fallback()
            logger.warning(f"embedding 接口调用失败，回退哈希向量：{e}")
            return [hash_embed(t, self.dim) for t in texts]


class OfflineFallbackLLM(LLMProvider):
    def __init__(self, cfg):
        self.dim = cfg["EMBED_DIM"]
        self.query_prefix = cfg.get("QUERY_PREFIX", "") or ""
        self.query_expand = cfg.get("QUERY_EXPAND", "1") not in ("0", "false", "False")

    def is_available(self) -> bool:
        return False

    def chat_stream(self, messages: list[dict]) -> Iterator[str]:
        # 不直接使用；离线模式由 chat_service 合成回答。
        return iter(())

    def embed(self, texts: list[str], query: bool = False) -> list[list[float]]:
        return [hash_embed(t, self.dim) for t in texts]

    def embed_query_variants(self, question: str) -> list[list[float]]:
        """离线兜底：原始提问 + 关键词扩展两个变体（哈希向量）。"""
        variants: list[str] = [question]
        if self.query_expand:
            from utils.text_utils import tokenize

            toks = tokenize(question)
            if toks:
                variants.append(" ".join(toks[:40]))
        return self.embed(variants, query=False)


def hash_embed(text: str, dim: int = 256) -> list[float]:
    """确定性哈希向量（CJK 按字符二元组）。索引与查询必须使用相同 dim 与 tokenize。"""
    vec = np.zeros(dim, dtype=np.float32)
    for tok in split_tokens(text):
        h = int(hashlib.md5(tok.encode("utf-8")).hexdigest(), 16)
        vec[h % dim] += 1.0 if (h & 1) else -1.0
    n = np.linalg.norm(vec)
    if n > 0:
        vec = vec / n
    return vec.tolist()


def _normalize_rows(rows: list[list[float]]) -> list[list[float]]:
    """对一批向量做 L2 归一化，保证 cosine 相似度可直接比较（= 点积）。"""
    arr = np.asarray(rows, dtype=np.float32)
    norms = np.linalg.norm(arr, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    arr = arr / norms
    return arr.tolist()