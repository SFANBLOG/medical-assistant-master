"""
下载候选 Cross-Encoder 重排模型到本地 MODEL_DIR。

用途：在多个候选模型之间做 A/B 评测，选出对本知识库效果最好的一个。

用法：
    HF_ENDPOINT=https://hf-mirror.com python scripts/download_rerankers.py
    python scripts/download_rerankers.py --only bge-reranker-base
"""
from __future__ import annotations

import argparse
import os
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# 候选模型。按住要评测的顺序排列；体积越小下载越快。
CANDIDATES: dict[str, dict] = {
    "bge-reranker-base": {
        "repo": "BAAI/bge-reranker-base",
        "params": "278M",
        "desc": "中文/英文通用，轻量基线",
    },
    "bge-reranker-v2-m3": {
        "repo": "BAAI/bge-reranker-v2-m3",
        "params": "568M",
        "desc": "多语言 v2 代，效果最强（推荐）",
    },
    "bge-reranker-large": {
        "repo": "BAAI/bge-reranker-large",
        "params": "560M",
        "desc": "v1 代大号版，中文强",
    },
}

# 只下 safetensors 权重 —— .bin 是同一份权重的另一种格式，两者都下会浪费一倍带宽
_ALLOW_PATTERNS = ["*.safetensors", "*.json", "*.txt", "*.model"]

# 默认下载集合：v1 大号版与 v2-m3 能力重叠，默认只取 base(快) + v2-m3(强)
DEFAULT_DOWNLOAD = ["bge-reranker-base", "bge-reranker-v2-m3"]


def _download_one(name: str, info: dict, model_dir: Path) -> bool:
    target = model_dir / name
    if (target / "config.json").exists():
        print(f"[skip] {name} 已存在于 {target}")
        return True

    repo = info["repo"]
    print(f"\n{'=' * 60}")
    print(f"[down] {name}  <-  {repo}  ({info['params']}) {info['desc']}")
    print("=" * 60)

    try:
        from huggingface_hub import snapshot_download
    except ImportError:
        print("[err ] huggingface_hub 未安装，请先 pip install huggingface_hub")
        return False

    target.parent.mkdir(parents=True, exist_ok=True)
    tmp_dir = model_dir / f".tmp_{name}"

    # 启用 hf_transfer（Rust 多线程传输），可用时速度通常提升数倍
    try:
        import hf_transfer  # noqa: F401
        os.environ.setdefault("HF_HUB_ENABLE_HF_TRANSFER", "1")
        print(f"[info] 已启用 hf_transfer 多线程下载")
    except ImportError:
        print("[info] hf_transfer 未安装，使用默认单线程下载（pip install hf_transfer 可加速）")

    patterns = list(_ALLOW_PATTERNS)
    if getattr(_download_one, "allow_bin", False):
        patterns.append("*.bin")

    try:
        snapshot_path = snapshot_download(
            repo_id=repo,
            cache_dir=str(tmp_dir),
            allow_patterns=patterns,
            max_workers=8,
        )
    except Exception as e:  # noqa: BLE001
        print(f"[err ] {name} 下载失败：{type(e).__name__}: {e}")
        shutil.rmtree(tmp_dir, ignore_errors=True)
        return False

    # snapshot_download 返回的是 cache 里的 snapshots/<rev> 目录
    src = Path(snapshot_path)
    if not (src / "config.json").exists():
        print(f"[err ] {name} 快照目录缺少 config.json: {src}")
        return False

    if target.exists():
        shutil.rmtree(target, ignore_errors=True)
    shutil.copytree(src, target)

    weights = list(target.glob("*.safetensors")) + list(target.glob("*.bin"))
    if not weights:
        print(f"[err ] {name} 未下到权重文件（该仓库可能只有 .bin 格式），请加 --allow-bin 重试")
        return False

    size_mb = sum(f.stat().st_size for f in target.rglob("*") if f.is_file()) / 1024 / 1024
    print(f"[ok  ] {name} -> {target}  ({size_mb:.0f} MB, 权重 {len(weights)} 个)")

    # 清理 HF cache 软链目录，避免重复占用磁盘
    shutil.rmtree(tmp_dir, ignore_errors=True)
    return True


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", nargs="*", default=None,
                    help="只下载指定模型（传 key 名）")
    ap.add_argument("--allow-bin", action="store_true",
                    help="同时允许 .bin 权重（仅当仓库没有 safetensors 时使用）")
    args = ap.parse_args()
    _download_one.allow_bin = args.allow_bin

    sys.path.insert(0, ".")
    from backend import config  # noqa: E402

    model_dir: Path = config.MODEL_DIR
    model_dir.mkdir(parents=True, exist_ok=True)

    endpoint = os.getenv("HF_ENDPOINT", "")
    print(f"MODEL_DIR   = {model_dir}")
    print(f"HF_ENDPOINT = {endpoint or '(默认 huggingface.co)'}")

    todo = args.only or DEFAULT_DOWNLOAD
    ok, fail = [], []
    for name in todo:
        if name not in CANDIDATES:
            print(f"[warn] 未知模型 key: {name}")
            continue
        (_ := ok if _download_one(name, CANDIDATES[name], model_dir) else fail).append(name)

    print(f"\n{'=' * 60}")
    print(f"下载完成：成功 {len(ok)} / 失败 {len(fail)}")
    if ok:
        print("  成功:", ", ".join(ok))
    if fail:
        print("  失败:", ", ".join(fail))
    print("=" * 60)
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
