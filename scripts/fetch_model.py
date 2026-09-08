"""
多线程直链下载 HuggingFace 模型到本地 MODEL_DIR。

与 huggingface_hub 的区别：
- 直连 resolve/main，绕开 hub 缓存层，避免把 .bin 和 .safetensors 两份权重都下下来
- 大文件按 HTTP Range 分段并行下载，在单连接速率不稳的网络上明显更快
- 支持断点续传（分片文件保留，重跑自动跳过已完成的分片）

用法：
    HF_ENDPOINT=https://hf-mirror.com python scripts/fetch_model.py BAAI/bge-reranker-base
    python scripts/fetch_model.py BAAI/bge-reranker-v2-m3 --threads 16
"""
from __future__ import annotations

import argparse
import json
import math
import os
import shutil
import ssl
import sys
import threading
import time
import urllib.request
from pathlib import Path
from typing import List, Optional

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

ssl._create_default_https_context = ssl._create_unverified_context

# 需要下载的小文件（权重文件单独处理，只取 safetensors）
_SMALL_FILES = [
    "config.json",
    "tokenizer.json",
    "tokenizer_config.json",
    "special_tokens_map.json",
    "sentencepiece.bpe.model",
    "vocab.txt",
]

UA = {"User-Agent": "medical-assistant-model-fetcher/1.0"}


def _head(url: str) -> tuple[int, bool]:
    req = urllib.request.Request(url, method="HEAD", headers=UA)
    with urllib.request.urlopen(req, timeout=30) as r:
        return int(r.headers.get("Content-Length", 0)), \
            r.headers.get("Accept-Ranges") == "bytes"


def _download_small(url: str, dest: Path) -> bool:
    try:
        req = urllib.request.Request(url, headers=UA)
        with urllib.request.urlopen(req, timeout=60) as r:
            data = r.read()
        dest.write_bytes(data)
        return True
    except Exception:  # noqa: BLE001
        return False


class _Progress:
    """简单的全局进度计数。"""

    def __init__(self, total: int):
        self.total = total
        self.done = 0
        self.lock = threading.Lock()
        self.t0 = time.time()

    def add(self, n: int):
        with self.lock:
            self.done += n

    def render(self, stop: threading.Event):
        while not stop.is_set():
            with self.lock:
                d, t = self.done, self.total
            pct = d / t * 100 if t else 0
            mb = d / 1024 / 1024
            tot = t / 1024 / 1024
            spd = d / 1024 / 1024 / max(0.1, time.time() - self.t0)
            eta = (t - d) / 1024 / 1024 / spd if spd > 0 else 0
            print(f"\r  {mb:.0f}/{tot:.0f} MB  {pct:5.1f}%  "
                  f"{spd:.2f} MB/s  ETA {eta:.0f}s   ", end="", flush=True)
            time.sleep(1)


def _fetch_range(url: str, start: int, end: int, dest: Path,
                 progress: _Progress, retries: int = 5) -> bool:
    """下载 [start, end] 闭区间字节，支持续传与重试。"""
    exist = dest.stat().st_size if dest.exists() else 0
    expect = end - start + 1
    if exist == expect:
        progress.add(expect)  # 已完成的分片计入总量
        return True
    if exist > expect:
        dest.unlink()
        exist = 0
    cur = start + exist
    progress.add(exist)

    for attempt in range(retries):
        headers = {**UA, "Range": f"bytes={cur}-{end}"}
        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=60) as r:
                with open(dest, "ab" if cur > start else "wb") as f:
                    while True:
                        buf = r.read(256 * 1024)
                        if not buf:
                            break
                        f.write(buf)
                        progress.add(len(buf))
            if dest.stat().st_size == expect:
                return True
            cur = start + dest.stat().st_size  # 未下满，从断点继续
        except Exception as e:  # noqa: BLE001
            if attempt == retries - 1:
                print(f"\n  [warn] 分片 {start}-{end} 失败: {type(e).__name__}: {e}")
                return False
            time.sleep(2 * (attempt + 1))
            cur = start + (dest.stat().st_size if dest.exists() else 0)
    return False


def download_file(url: str, dest: Path, threads: int = 8) -> bool:
    """分段并行下载大文件。"""
    size, accept_ranges = _head(url)
    if size == 0:
        print(f"  [err ] 无法获取文件大小: {url}")
        return False
    print(f"  大小 {size/1024/1024:.0f} MB  Range支持={accept_ranges}")

    if dest.exists() and dest.stat().st_size == size:
        print(f"  [skip] 已完整存在")
        return True

    if not accept_ranges or size < 4 * 1024 * 1024 or threads <= 1:
        tmp = dest.with_suffix(dest.suffix + ".part")
        pg = _Progress(size)
        ok = _fetch_range(url, 0, size - 1, tmp, pg, retries=8)
        if ok:
            tmp.replace(dest)
        print()
        return ok

    parts_dir = dest.parent / f".parts_{dest.name}"
    parts_dir.mkdir(parents=True, exist_ok=True)

    chunk = math.ceil(size / threads)
    spans = [(i * chunk, min(size - 1, (i + 1) * chunk - 1))
             for i in range(threads)]
    spans = [s for s in spans if s[0] <= s[1]]

    pg = _Progress(size)
    stop = threading.Event()
    t = threading.Thread(target=pg.render, args=(stop,), daemon=True)
    t.start()

    results: List[bool] = [False] * len(spans)

    def worker(idx: int, s: int, e: int):
        results[idx] = _fetch_range(
            url, s, e, parts_dir / f"part{idx:03d}", pg)

    workers = [threading.Thread(target=worker, args=(i, s, e))
               for i, (s, e) in enumerate(spans)]
    for w in workers:
        w.start()
    for w in workers:
        w.join()
    stop.set()
    t.join(timeout=2)
    print()

    if not all(results):
        print(f"  [err ] 有分片下载失败，保留分片以便重跑续传")
        return False

    with open(dest, "wb") as out:
        for i in range(len(spans)):
            p = parts_dir / f"part{i:03d}"
            out.write(p.read_bytes())
    shutil.rmtree(parts_dir, ignore_errors=True)
    return True


def fetch(repo: str, out_dir: Path, threads: int, prefer: str = "safetensors") -> bool:
    endpoint = os.getenv("HF_ENDPOINT", "https://huggingface.co").rstrip("/")
    out_dir.mkdir(parents=True, exist_ok=True)

    print(f"仓库   : {repo}")
    print(f"源站   : {endpoint}")
    print(f"目标   : {out_dir}")
    print(f"线程   : {threads}")

    # 1. 小配置文件
    for name in _SMALL_FILES:
        dest = out_dir / name
        if dest.exists() and dest.stat().st_size > 0:
            continue
        if _download_small(f"{endpoint}/{repo}/resolve/main/{name}", dest):
            print(f"  [ok  ] {name} ({dest.stat().st_size/1024:.0f} KB)")

    if not (out_dir / "config.json").exists():
        print("  [err ] config.json 下载失败")
        return False

    # 2. 权重文件
    candidates = ["model.safetensors", "pytorch_model.bin"]
    if prefer == "bin":
        candidates.reverse()

    for wname in candidates:
        dest = out_dir / wname
        if dest.exists() and dest.stat().st_size > 0:
            # 已存在权重就不再下另一种格式
            print(f"  [skip] 权重已存在: {wname} ({dest.stat().st_size/1024/1024:.0f} MB)")
            return True
        print(f"下载权重: {wname}")
        try:
            if download_file(f"{endpoint}/{repo}/resolve/main/{wname}", dest, threads):
                print(f"  [ok  ] {wname}")
                return True
        except Exception as e:  # noqa: BLE001
            print(f"  [warn] {wname} 下载失败: {type(e).__name__}: {e}")
            continue
    return False


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("repo", nargs="?", default="BAAI/bge-reranker-base")
    ap.add_argument("--name", default=None,
                    help="本地目录名，默认取 repo 的最后一段")
    ap.add_argument("--threads", type=int, default=8)
    ap.add_argument("--prefer", choices=["safetensors", "bin"],
                    default="safetensors")
    args = ap.parse_args()

    sys.path.insert(0, ".")
    from backend import config  # noqa: E402

    name = args.name or args.repo.split("/")[-1]
    out_dir: Path = config.MODEL_DIR / name

    t0 = time.time()
    ok = fetch(args.repo, out_dir, args.threads, args.prefer)
    print(f"\n{'完成' if ok else '失败'}，耗时 {time.time()-t0:.0f}s -> {out_dir}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
