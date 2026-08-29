"""
文本嵌入器（Embedder）模块。

支持两种工作模式，按优先级自动选择：

1. BGE 本地模型
   - 配置项：OPENAI_EMBED_MODEL（本地路径 / HF repo_id / 模型别名）
   - 依赖：sentence-transformers
   - 维度由模型自身决定

2. 内置确定性哈希向量（HashEmbedder）
   - 离线可用，零配置
   - 维度由 EMBED_DIM 决定（默认 768）
   - 语义效果弱于 BGE，但可作为兜底方案

路径解析策略（由 _resolve_model_path 实现）：
- 先按字面路径尝试；
- 相对路径会同时以 backend/ 目录为基准解析；
- 若仍未找到，则在 backend/data/models/ 下递归搜索包含 config.json 的目录；
- 兼容 HuggingFace / ModelScope 缓存结构（snapshots/master/）。
"""
import hashlib
import re
from pathlib import Path
from typing import Optional

import numpy as np

from backend import config

# ---- 模块级缓存 ----
# _bge_model: 成功加载的 SentenceTransformer 模型实例
# _bge_failed: 是否已经尝试过且失败（避免重复打印/重复加载拖慢启动）
_bge_model = None
_bge_failed = False

# 判断一个目录是否为可用模型目录的最小文件集合
_REQUIRED_MODEL_FILES = {"config.json", "tokenizer_config.json", "vocab.txt"}


class HashEmbedder:
    """确定性哈希向量嵌入器（离线兜底）。"""

    def __init__(self, dim: int = None):
        """
        Args:
            dim: 输出向量维度，默认读取 config.EMBED_DIM。
        """
        self._dim = dim or config.EMBED_DIM

    def _tokenize(self, text: str) -> list[str]:
        """简易中文分词：英文单词 + 中文字单字 + 中文字 bigram。"""
        tokens = []
        # 英文单词（统一小写）
        for m in re.findall(r"[a-zA-Z]+", text):
            tokens.append(m.lower())
        # 中文字符：单字 + 相邻双字
        chinese = re.findall(r"[\u4e00-\u9fff]+", text)
        for seg in chinese:
            for i in range(len(seg)):
                tokens.append(seg[i])
            for i in range(len(seg) - 1):
                tokens.append(seg[i:i + 2])
        return tokens

    def embed(self, text: str) -> np.ndarray:
        """将文本编码为 L2 归一化的 float32 向量。"""
        vec = np.zeros(self._dim, dtype=np.float32)
        tokens = self._tokenize(text)
        if not tokens:
            return vec
        for token in tokens:
            h = hashlib.md5(token.encode("utf-8")).hexdigest()
            idx = int(h[:8], 16) % self._dim
            sign = 1.0 if int(h[8], 16) % 2 == 0 else -1.0
            # 长 token 给予稍高权重，模拟词频影响
            vec[idx] += sign * (1.0 + len(token) * 0.1)
        norm = np.linalg.norm(vec)
        if norm > 0:
            vec = vec / norm
        return vec

    def embed_batch(self, texts: list[str]) -> list[np.ndarray]:
        """批量编码（当前为顺序实现，数据量小时足够）。"""
        return [self.embed(t) for t in texts]

    @property
    def dim(self) -> int:
        return self._dim


def _is_valid_model_dir(path: Path) -> bool:
    """检查目录是否包含模型最小必需文件。"""
    if not path or not path.is_dir():
        return False
    return all((path / fname).exists() for fname in _REQUIRED_MODEL_FILES)


def _find_model_in_model_dir(model_name: str) -> Optional[Path]:
    """在 config.MODEL_DIR 下递归搜索可用模型目录。

    搜索规则：
    1. 直接子目录：MODEL_DIR / <model_name>
    2. HuggingFace 缓存结构：MODEL_DIR / models / BAAI--<model_name> / snapshots / master
    3. ModelScope 缓存结构：MODEL_DIR / BAAI__<model_name>
    4. 兜底：递归查找任意包含 config.json 的目录（深度受限，避免遍历过大）
    """
    model_dir = config.MODEL_DIR
    if not model_dir.exists():
        return None

    # 规范化模型名：去掉可能的前缀 repo_id
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

    # 兜底：在 MODEL_DIR 下递归搜索包含 config.json 的目录（最多 3 层）
    try:
        for p in model_dir.rglob("config.json"):
            cand = p.parent
            # 只接受相对深度 <= 3 的目录，避免误命中深层缓存
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
    """解析并校验模型路径。

    返回包含 config.json 的目录，若无法解析则返回 None。

    解析顺序：
    1. 字面路径（绝对路径 或 相对当前工作目录）
    2. 相对 backend 目录解析（兼容 .env 中 data/models/xxx 写法）
    3. 在 backend/data/models/ 下自动搜索
    """
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

    # 3) 相对 backend 目录（.env 常见写法：data/models/bge-base-zh-v1.5）
    backend_path = config.BACKEND_DIR / p
    if _is_valid_model_dir(backend_path):
        return backend_path

    # 4) 在 MODEL_DIR 下自动搜索（兼容 HF/ModelScope 缓存结构）
    found = _find_model_in_model_dir(model_path_or_name)
    if found:
        return found

    # 5) 若字面路径指向的目录不存在，但父目录存在且包含模型文件，
    #    可能是 snapshot 路径写错，尝试向上搜索一层
    for base in (cwd_path, backend_path):
        if base.parent.is_dir() and _is_valid_model_dir(base.parent):
            return base.parent

    return None


def _get_embed_dim(model) -> int:
    """获取句向量维度，兼容 sentence-transformers 新 / 旧 API 命名。

    - 新版本（>= 2.3）：get_embedding_dimension
    - 旧版本：         get_sentence_embedding_dimension
    旧方法在 3.x 中已被重命名并触发 FutureWarning，这里优先用新方法并兜底旧方法。
    """
    if hasattr(model, "get_embedding_dimension"):
        return model.get_embedding_dimension()
    return model.get_sentence_embedding_dimension()


def _try_bge_model():
    """尝试加载 BGE 本地模型，失败时回退到 None。"""
    global _bge_model, _bge_failed
    if _bge_failed or _bge_model is not None:
        return _bge_model

    model_path = config.OPENAI_EMBED_MODEL
    resolved = _resolve_model_path(model_path) if model_path else None

    if not resolved:
        # 未配置或无法解析：标记失败，不再重试
        _bge_failed = True
        if model_path:
            print(f"[Embedder] 未找到可用模型目录: {model_path}，回退到哈希向量")
        return None

    try:
        from sentence_transformers import SentenceTransformer
        _bge_model = SentenceTransformer(str(resolved))
        print(
            f"[Embedder] BGE 模型加载成功: {resolved} "
            f"(dim={_get_embed_dim(_bge_model)})")
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
    1. BGE 本地模型（如果 OPENAI_EMBED_MODEL 可解析且 sentence_transformers 已安装）
    2. HashEmbedder（兜底，零配置）
    """
    bge = _try_bge_model()
    if bge is not None:
        return _BGEEmbedder(bge)
    return HashEmbedder()
