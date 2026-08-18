"""下载本地向量模型（bge-base-zh-v1.5）到 backend/data/models/。

网络说明：
- 优先从 ModelScope 下载（国内 CDN，速度快）；ModelScope 不可用时回退 HuggingFace
  （hf-mirror.com）。若二者均不可用，可手动放置模型目录到 data/models/ 下。
- 如需更强效果可换用 bge-large-zh-v1.5（维度 1024），此时需同步修改 .env 的
  OPENAI_EMBED_MODEL 与 EMBED_DIM。

用法：
    .venv/bin/python download_model.py
"""
import os
import shutil
import sys

BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))
TARGET = os.path.join(BACKEND_DIR, "data", "models", "bge-base-zh-v1.5")
MODEL_ID = "AI-ModelScope/bge-base-zh-v1.5"
HF_ID = "BAAI/bge-base-zh-v1.5"
MODELSCOPE_ARGS = {"ignore_patterns": ["*.safetensors*"]}  # 只需 bin 权重 + 配置


def _download_modelscope() -> bool:
    try:
        from modelscope import snapshot_download

        tmp = snapshot_download(MODEL_ID, **MODELSCOPE_ARGS)
        os.makedirs(TARGET, exist_ok=True)
        for name in os.listdir(tmp):
            src = os.path.join(tmp, name)
            if os.path.isdir(src):
                shutil.copytree(src, os.path.join(TARGET, name), dirs_exist_ok=True)
            else:
                shutil.copy2(src, os.path.join(TARGET, name))
        return True
    except Exception as e:  # noqa: BLE001
        print(f"ModelScope 下载失败：{e}")
        return False


def _download_hf() -> bool:
    try:
        from huggingface_hub import snapshot_download

        snapshot_download(HF_ID, local_dir=TARGET)
        return True
    except Exception as e:  # noqa: BLE001
        print(f"HuggingFace 下载失败：{e}")
        return False


def main() -> int:
    os.makedirs(TARGET, exist_ok=True)
    if os.path.isdir(os.path.join(TARGET, "1_Pooling")):
        print(f"模型已存在：{TARGET}")
        return 0
    print(f"下载向量模型到 {TARGET} ...")
    ok = _download_modelscope() or _download_hf()
    if ok and os.path.isdir(os.path.join(TARGET, "1_Pooling")):
        print("模型下载完成。请确认 .env 中 OPENAI_EMBED_MODEL=data/models/bge-large-zh-v1.5")
        return 0
    print("模型下载失败：请检查网络，或手动将模型放到 data/models/bge-large-zh-v1.5/")
    return 1


if __name__ == "__main__":
    sys.exit(main())
