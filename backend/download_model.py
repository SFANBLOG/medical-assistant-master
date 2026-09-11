"""
下载 BGE 中文语义检索模型（bge-base-zh-v1.5，768 维）。
用法:
    cd backend && python download_model.py
优先从 ModelScope 下载；失败时自动回退 HuggingFace（hf-mirror）。
下载完成后在 .env 中设置:
    OPENAI_EMBED_MODEL=data/models/bge-base-zh-v1.5
"""
import os
import shutil
import subprocess
import sys
from pathlib import Path

# 确保 backend 目录加入搜索路径
BASE_DIR = Path(__file__).resolve().parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from backend import config
MODEL_NAME = "bge-base-zh-v1.5"
TARGET_DIR: Path = (config.MODEL_DIR / MODEL_NAME).resolve()
REQUIRED_FILES = {"config.json", "tokenizer_config.json", "vocab.txt"}
LOCK_FILE = TARGET_DIR / ".download_lock"
ESTIMATE_SIZE_MB = 450


def run_pip_install(package: str) -> tuple[int, str]:
    """安全执行pip安装，返回返回码+stdout输出，替代os.system"""
    proc = subprocess.run(
        [sys.executable, "-m", "pip", "install", package],
        capture_output=True,
        text=True,
    )
    return proc.returncode, proc.stdout + proc.stderr


def check_dir_has_required_files(folder: Path) -> bool:
    """校验目录是否具备模型最小必须文件"""
    if not folder.exists() or not folder.is_dir():
        return False
    for fname in REQUIRED_FILES:
        if not (folder / fname).exists():
            return False
    return True


def check_disk_space(path: Path, need_mb: int):
    """简单磁盘空间检查"""
    statvfs = os.statvfs(path.parent)
    free_mb = statvfs.f_frsize * statvfs.f_bavail / (1024 * 1024)
    if free_mb < need_mb:
        print(f"⚠️ 警告：磁盘剩余空间 {free_mb:.1f}MB，预估需要 {need_mb}MB，可能下载失败")


def download_from_modelscope() -> Path | None:
    """从 ModelScope 下载模型，返回缓存目录Path；失败返回None"""
    try:
        from modelscope import snapshot_download
    except ImportError:
        print("[ModelScope] modelscope 库未安装，自动安装...")
        ret, out = run_pip_install("modelscope")
        if ret != 0:
            print(f"[ModelScope] modelscope 安装失败:\n{out}")
            return None
        try:
            from modelscope import snapshot_download
        except Exception as e:
            print(f"[ModelScope] 导入失败: {e}")
            return None

    try:
        print("[ModelScope] 开始下载 BAAI/bge-base-zh-v1.5 ...")
        snapshot_download(
            f"BAAI/{MODEL_NAME}",
            cache_dir=str(config.MODEL_DIR.resolve()),
            resume_download=True,
        )
        cache_root = (config.MODEL_DIR / f"BAAI__{MODEL_NAME}").resolve()
        if not check_dir_has_required_files(cache_root):
            print(f"[ModelScope] 缓存目录 {cache_root} 文件不全，下载中断")
            return None
        return cache_root
    except Exception as e:
        print(f"[ModelScope] 下载异常: {e}")
        return None


def download_from_hf() -> Path | None:
    """从 HuggingFace镜像下载，直接下载到TARGET_DIR，返回Path；失败返回None"""
    try:
        from huggingface_hub import snapshot_download
    except ImportError:
        print("[HuggingFace] huggingface_hub 未安装，自动安装...")
        ret, out = run_pip_install("huggingface_hub")
        if ret != 0:
            print(f"[HuggingFace] huggingface_hub 安装失败:\n{out}")
            return None
        from huggingface_hub import snapshot_download

    try:
        env = os.environ.copy()
        env["HF_ENDPOINT"] = "https://hf-mirror.com"
        print("[HuggingFace(hf‑mirror)] 开始下载 BAAI/bge-base-zh-v1.5 ...")
        path = snapshot_download(
            repo_id=f"BAAI/{MODEL_NAME}",
            local_dir=str(TARGET_DIR),
            local_dir_use_symlinks=False,
            resume_download=True,
        )
        res_path = Path(path).resolve()
        if not check_dir_has_required_files(res_path):
            print("[HuggingFace] 下载后文件缺失")
            return None
        return res_path
    except Exception as e:
        print(f"[HuggingFace] 下载异常: {e}")
        return None


def copy_model_files(src: Path, dst: Path):
    """把src模型文件复制到dst，先清空dst，仅过滤README.md"""
    src = src.resolve()
    dst = dst.resolve()
    if src == dst:
        print("[Copy] 源目录与目标目录一致，跳过拷贝")
        return

    if dst.exists():
        shutil.rmtree(dst)
    dst.mkdir(parents=True, exist_ok=True)

    for item in src.iterdir():
        if item.name == "README.md":
            continue
        dst_item = dst / item.name
        try:
            if item.is_dir():
                shutil.copytree(item, dst_item)
            else:
                shutil.copy2(item, dst_item)
        except Exception as e:
            print(f"[Copy] 文件拷贝失败 {item.name}: {e}")
            raise


def main():
    TARGET_DIR.mkdir(parents=True, exist_ok=True)

    # 锁文件检测，防止并发执行
    if LOCK_FILE.exists():
        print(f"⚠️ 检测到锁文件 {LOCK_FILE}，可能另一个下载进程正在运行，请稍后重试")
        return

    # 检测已存在完整模型（手动放置 / 已下载完成）
    if check_dir_has_required_files(TARGET_DIR):
        print(f"[Model] ✅ 模型已就绪: {TARGET_DIR}")
        print("请在 .env 中设置 OPENAI_EMBED_MODEL=data/models/bge-base-zh-v1.5 启用")
        return

    check_disk_space(TARGET_DIR, ESTIMATE_SIZE_MB)
    # 创建锁
    LOCK_FILE.touch(exist_ok=False)

    print("=" * 60)
    print("  下载 BGE 中文语义检索模型（约 400MB）")
    print("=" * 60)

    result: Path | None = None
    try:
        # 优先 ModelScope，失败回退HF镜像
        result = download_from_modelscope()
        if result is None or not check_dir_has_required_files(result):
            print("[Notice] ModelScope不可用，切换HuggingFace镜像源")
            result = download_from_hf()

        if result is not None and check_dir_has_required_files(result):
            src_path = Path(result).resolve()
            if src_path != TARGET_DIR:
                copy_model_files(src_path, TARGET_DIR)

            print(f"\n✅ [Model] 下载&整理完成: {TARGET_DIR}")
            print("请在 .env 文件配置：")
            print("OPENAI_EMBED_MODEL=data/models/bge-base-zh-v1.5\n")
        else:
            print("\n❌ [Model] 全部下载源失败！")
            print("备选方案：")
            print("1.手动下载模型，放到 data/ai_models/bge-base-zh-v1.5")
            print("2.临时使用内置哈希向量，不需要embedding模型\n")
    finally:
        # 无论成功失败，清除锁文件
        if LOCK_FILE.exists():
            LOCK_FILE.unlink()


if __name__ == "__main__":
    main()
