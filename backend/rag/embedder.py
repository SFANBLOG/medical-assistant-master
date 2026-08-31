"""
文本嵌入器（Embedder）模块。

支持三种模式，按优先级自动选择：

1. BGE 本地模型（推荐）
   - 配置项：OPENAI_EMBED_MODEL（"auto" / 本地路径 / HF repo_id）
   - "auto" 时自动在 MODEL_DIR 下搜索已下载模型；找不到则尝试下载 bge-small-zh-v1.5
   - 依赖：sentence-transformers + torch
   - 维度由模型自身决定

2. 内置确定性哈希向量（HashEmbedder）
   - 离线可用，零配置，但**无语义能力**（仅作最后兜底）
   - 维度由 EMBED_DIM 决定（默认 768）

模型下载策略：
- 仅在 OPENAI_EMBED_MODEL="auto" 且 MODEL_DIR 下无任何可用模型时触发
- 默认下载 BAAI/bge-small-zh-v1.5（~100MB，CPU 友好）
- 可通过环境变量 EMBED_MODEL_NAME 指定其他模型（如 bge-base-zh-v1.5 ~400MB）
- 下载失败静默回退到 HashEmbedder，不阻塞启动
"""
import hashlib
import re
from pathlib import Path
from typing import Optional

import numpy as np

from backend import config

# ---- 模块级缓存 ----
_bge_model = None
_bge_failed = False

# 判断一个目录是否为可用模型目录的最小文件集合
_REQUIRED_MODEL_FILES = {"config.json", "tokenizer_config.json", "vocab.txt"}

# 自动检测时的候选模型名（按优先级，小的在前）
_AUTO_DETECT_CANDIDATES = [
    "bge-small-zh-v1.5",
    "bge-base-zh-v1.5",
]

# 默认自动下载的模型（小而快，适合 CPU）
_DEFAULT_DOWNLOAD_MODEL = "BAAI/bge-small-zh-v1.5"


class HashEmbedder:
    """确定性哈希向量嵌入器（离线兜底，无语义能力）。"""

    def __init__(self, dim: int = None):
        self._dim = dim or config.EMBED_DIM

    def _tokenize(self, text: str) -> list[str]:
        tokens = []
        for m in re.findall(r"[a-zA-Z]+", text):
            tokens.append(m.lower())
        chinese = re.findall(r"[\u4e00-\u9fff]+", text)
        for seg in chinese:
            for i in range(len(seg)):
                tokens.append(seg[i])
            for i in range(len(seg) - 1):
                tokens.append(seg[i:i + 2])
        return tokens

    def embed(self, text: str) -> np.ndarray:
        vec = np.zeros(self._dim, dtype=np.float32)
        tokens = self._tokenize(text)
        if not tokens:
            return vec
        for token in tokens:
            h = hashlib.md5(token.encode("utf-8")).hexdigest()
            idx = int(h[:8], 16) % self._dim
            sign = 1.0 if int(h[8], 16) % 2 == 0 else -1.0
            vec[idx] += sign * (1.0 + len(token) * 0.1)
        norm = np.linalg.norm(vec)
        if norm > 0:
            vec = vec / norm
        return vec

    def embed_batch(self, texts: list[str]) -> list[np.ndarray]:
        return [self.embed(t) for t in texts]

    @property
    def dim(self) -> int:
        return self._dim


def _is_valid_model_dir(path: Path) -> bool:
    if not path or not path.is_dir():
        return False
    return all((path / fname).exists() for fname in _REQUIRED_MODEL_FILES)


def _find_model_in_model_dir(model_name: str) -> Optional[Path]:
    """在 config.MODEL_DIR 下递归搜索可用模型目录。"""
    model_dir = config.MODEL_DIR
    if not model_dir.exists():
        return None

    short_name = model_name.split("/")[-1] if "/" in model_name else model_name

    candidates = [
        model_dir / model_name,
        model_dir / short_name,
        model_dir / "models" / f"BAAI--{short_name}" / "snapshots" / "master",
        model_dir / f"BAAI__{short_name}",
        model_dir / "models" / f"BAAI--{short_name}",
    ]

    for cand in candidates:
        if _is_valid_model_dir(cand):
            return cand

    # 兜底：递归查找任意包含 config.json 的目录（最多 3 层）
    try:
        for p in model_dir.rglob("config.json"):
            cand = p.parent
            try:
                depth = len(cand.relative_to(model_dir).parts)
            except ValueError:
                continue
            if depth <= 3 and _is_valid_model_dir(cand):
                return cand
    except OSError:
        pass

    return None


def _resolve_model_path(model_path_or_name: str) -> Optional[Path]:
    """解析并校验模型路径。"""
    if not model_path_or_name:
        return None

    # 1) 字面路径
    p = Path(model_path_or_name).expanduser()
    if p.is_absolute() and _is_valid_model_dir(p):
        return p

    # 2) 相对当前工作目录
    cwd_path = Path.cwd() / p
    if _is_valid_model_dir(cwd_path):
        return cwd_path

    # 3) 相对 backend 目录
    backend_path = config.BACKEND_DIR / p
    if _is_valid_model_dir(backend_path):
        return backend_path

    # 4) 在 MODEL_DIR 下自动搜索
    found = _find_model_in_model_dir(model_path_or_name)
    if found:
        return found

    # 5) 向上搜索一层（snapshot 路径容错）
    for base in (cwd_path, backend_path):
        if base.parent.is_dir() and _is_valid_model_dir(base.parent):
            return base.parent

    return None


def _auto_detect_model() -> Optional[Path]:
    """在 MODEL_DIR 下按优先级搜索已下载的 BGE 模型。"""
    for name in _AUTO_DETECT_CANDIDATES:
        path = _find_model_in_model_dir(name)
        if path:
            print(f"[Embedder] 自动检测到模型: {path}")
            return path
    return None


def _download_model(model_name: str) -> Optional[Path]:
    """
    从 HuggingFace 下载 embedding 模型到 MODEL_DIR。

    返回模型目录路径，失败返回 None。
    """
    print(f"[Embedder] 正在下载模型 {model_name} …（首次使用，可能需要几分钟）")
    try:
        from sentence_transformers import SentenceTransformer
        save_path = config.MODEL_DIR / model_name.replace("/", "--")
        save_path.mkdir(parents=True, exist_ok=True)

        # 先用 cache_dir 下载到 HF 缓存目录
        model = SentenceTransformer(
            model_name,
            trust_remote_code=False,
        )

        # 保存到我们的 models 目录以便后续快速加载
        model.save(str(save_path))
        print(f"[Embedder] 模型下载并保存到: {save_path}")

        # 验证保存结果
        if _is_valid_model_dir(save_path):
            return save_path
        # 如果保存格式不完全匹配 _REQUIRED_MODEL_FILES，尝试找子目录
        for p in save_path.rglob("config.json"):
            cand = p.parent
            if _is_valid_model_dir(cand):
                return cand
        return save_path

    except ImportError:
        print("[Embedder] sentence_transformers 未安装，无法下载模型")
        return None
    except Exception as e:
        print(f"[Embedder] 模型下载失败: {e}")
        return None


def _get_embed_dim(model) -> int:
    if hasattr(model, "get_embedding_dimension"):
        return model.get_embedding_dimension()
    return model.get_sentence_embedding_dimension()


def _try_bge_model():
    """尝试加载 BGE 模型。支持 'auto' 自动检测/下载、显式路径、repo_id。"""
    global _bge_model, _bge_failed
    if _bge_failed or _bge_model is not None:
        return _bge_model

    model_config = config.OPENAI_EMBED_MODEL
    resolved = None

    if model_config == "auto":
        # 自动检测已有模型
        resolved = _auto_detect_model()
        if not resolved:
            # 尝试下载默认小模型
            download_name = os.getenv("EMBED_MODEL_NAME", _DEFAULT_DOWNLOAD_MODEL)
            resolved = _download_model(download_name)
    else:
        resolved = _resolve_model_path(model_config)
        # 如果显式配置了 repo_id 格式（如 "BAAI/bge-small-zh-v1.5"）且本地没有，
        # 尝试当作 HF repo_id 直接加载（sentence_transformers 会自行处理缓存）
        if not resolved and "/" in model_config:
            resolved = Path(model_config)  # 传给 SentenceTransformer 让它自己处理

    if not resolved:
        _bge_failed = True
        if model_config and model_config != "auto":
            print(f"[Embedder] 未找到可用模型: {model_config}，回退到哈希向量")
        else:
            print("[Embedder] 未找到且未配置 BGE 模型，使用哈希向量（无语义能力，相关度会很低）")
            print("[Embedder] 提示: 设 OPENAI_EMBED_MODEL=auto 可自动下载 bge-small-zh-v1.5")
        return None

    try:
        from sentence_transformers import SentenceTransformer
        # resolved 可能是 Path 或字符串 repo_id
        model_str = str(resolved) if isinstance(resolved, Path) else resolved
        _bge_model = SentenceTransformer(model_str)
        dim = _get_embed_dim(_bge_model)
        print(f"[Embedder] BGE 模型加载成功: {resolved} (dim={dim})")
        return _bge_model
    except ImportError:
        print("[Embedder] sentence_transformers 未安装，回退到哈希向量")
        _bge_failed = True
        return None
    except Exception as e:
        print(f"[Embedder] BGE 模型加载失败: {e}，回退到哈希向量")
        _bge_failed = True
        return None


class _BGEEmbedder:
    """BGE 模型包装器，对外接口与 HashEmbedder 保持一致。"""

    def __init__(self, model):
        self._model = model
        self._dim = _get_embed_dim(model)

    def embed(self, text: str) -> np.ndarray:
        vec = self._model.encode(text, normalize_embeddings=True)
        return np.array(vec, dtype=np.float32)

    def embed_batch(self, texts: list[str]) -> list[np.ndarray]:
        vecs = self._model.encode(texts, normalize_embeddings=True, batch_size=32)
        return [np.array(v, dtype=np.float32) for v in vecs]

    @property
    def dim(self) -> int:
        return self._dim


def get_embedder():
    """
    获取嵌入器实例。

    优先级：
    1. BGE 本地模型（auto-detect / auto-download / 显式配置）
    2. HashEmbedder（兜底，零语义能力）
    """
    bge = _try_bge_model()
    if bge is not None:
        return _BGEEmbedder(bge)
    return HashEmbedder()

# 补充 import
import os
