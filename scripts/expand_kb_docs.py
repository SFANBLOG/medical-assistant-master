# -*- coding: utf-8 -*-
"""
知识库文档扩写工具：调用 OpenAI 兼容 LLM（DeepSeek，读 backend/.env 或 .env），
把 backend/data/uploads/<库>/<公开|私有>/*.md 逐篇扩写为目标字数（默认 1000-1400 汉字），
保留 markdown 标题体系（# 一级 + ## 二级小节），覆盖该文件名主题的完整介绍。

用法:
    python scripts/expand_kb_docs.py --kb 妇儿疾病              # 只扩写一个库（试点）
    python scripts/expand_kb_docs.py --all                      # 扩写全部库
    python scripts/expand_kb_docs.py --kb 妇儿疾病 --min-chars 800 --max-chars 1200
    python scripts/expand_kb_docs.py --all --force              # 忽略断点状态，全部重跑

特性:
    - 断点续跑：scripts/.expand_state.json 记录已完成 (库/子目录/文件)，重跑自动跳过
    - 每篇失败自动重试 2 次（指数退避），仍失败记录到末尾汇总
    - 完成后强制把 H1 标题改写为「文件名主题」，防止 LLM 跑题改名
"""
import argparse
import json
import os
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import requests

PROJECT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_DIR))

import backend.config as config  # noqa: E402  会自动加载 backend/.env

UPLOADS = PROJECT_DIR / "backend" / "data" / "uploads"
STATE_FILE = PROJECT_DIR / "scripts" / ".expand_state.json"
API_URL = config.OPENAI_BASE_URL.rstrip("/") + "/chat/completions"
HEADERS = {
    "Authorization": f"Bearer {config.OPENAI_API_KEY}",
    "Content-Type": "application/json",
}

# 明显非医学主题的占位/测试文件（全量扫描时跳过）
SKIP_NAME_RE = re.compile(r"^(test|tmp|temp|example|readme|说明|模板|_|\.)", re.I)


def doc_position(subdir: str) -> str:
    """公开/私有 -> 写作定位描述。"""
    return "面向患者/家属的健康科普：通俗易懂、谨慎负责、不吓人；治疗仅讲通用原则与就医指引，不列处方剂量。要求：语言亲切平实，多用比喻帮助理解，强调何时必须就医。" if subdir == "公开" else "面向医护人员/专业人员的临床参考：术语专业、内容硬核；包含诊断路径、鉴别诊断、治疗与用药要点（可涉及剂量区间与临床决策）、操作/管理细节。要求：条理分明、可直接辅助临床工作。"


def system_prompt(position: str) -> str:
    return (
        "你是资深医学内容主编，医学知识准确、写作严谨。任务：把给定主题的医学短文档扩写为内容完整、深度足够的详细介绍。\n"
        "硬性要求：\n"
        "1. 只输出纯 Markdown 全文，禁止任何前言、解释、后记或“以下是”字样；\n"
        "2. 第一行必须是 `# 主题名`（与给定主题完全一致）；\n"
        "3. 正文用 `## 小节` 组织，小节覆盖但不限于：概述、病因与危险因素、发病机制、分类分型、临床表现、并发症、诊断、鉴别诊断、治疗、预防、预后与随访、注意事项/就医提示，按主题实际需要取舍合并；\n"
        "4. 正文总字数（不含标题行）控制在约 1000-1400 个汉字；\n"
        "5. 内容必须只围绕该主题，基于公认医学知识，不得编造具体药名剂量以外的细节；\n"
        "6. 写作定位：" + position + "\n"
        "7. 使用标准 Markdown：`#` 一级标题、`##` 二级小节标题，正文为普通段落或少量有序中文分点（一、二、…），不要使用加粗、表格、代码块。"
    )


def user_prompt(topic: str, original: str) -> str:
    return (
        f"主题：{topic}\n\n"
        "该主题现有文档内容如下（扩写时必须完整覆盖并大幅充实其中所有要点，同时补足其它重要知识）：\n\n"
        "-------- 原文开始 --------\n"
        f"{original}\n"
        "-------- 原文结束 --------\n\n"
        "请输出扩写后的完整 Markdown 文档。"
    )


def clean_output(text: str, topic: str) -> str:
    """截取 markdown 主体并把 H1 强制改为主题名。"""
    # 去掉可能的开头解释文字：定位第一个 '# ' 行
    lines = text.split("\n")
    start = 0
    for i, ln in enumerate(lines):
        if ln.startswith("# "):
            start = i
            break
    body = "\n".join(lines[start:]).strip()
    # H1 替换为主题名
    lines = body.split("\n")
    for i, ln in enumerate(lines):
        if ln.startswith("# "):
            lines[i] = f"# {topic}"
            break
    return "\n".join(lines).strip() + "\n"


def count_body_chars(md: str) -> int:
    """统计正文字符数：去掉标题行与空白后的可见字符数。"""
    out = []
    for ln in md.split("\n"):
        s = ln.strip()
        if not s or re.match(r"^#{1,6}\s", s):
            continue
        out.append(s)
    return len("".join(out))


def call_llm(topic: str, original: str, position: str, max_tokens: int = 2600, timeout: int = 150):
    payload = {
        "model": config.OPENAI_CHAT_MODEL,
        "messages": [
            {"role": "system", "content": system_prompt(position)},
            {"role": "user", "content": user_prompt(topic, original)},
        ],
        "temperature": 0.6,
        "max_tokens": max_tokens,
        "stream": False,
    }
    r = requests.post(API_URL, headers=HEADERS, json=payload, timeout=timeout)
    r.raise_for_status()
    return r.json()["choices"][0]["message"]["content"]


def expand_one(rel, topic, original, position, min_chars, max_chars, max_tokens, force):
    """扩写单篇，成功返回 (ok=True, chars, md)，最终失败 ok=False。"""
    result = {"rel": rel, "ok": False, "chars": 0, "md": "", "error": ""}
    for attempt in range(3):
        try:
            raw = call_llm(topic, original, position, max_tokens=max_tokens)
            md = clean_output(raw, topic)
            chars = count_body_chars(md)
            if chars < 400:  # 明显没扩写/输出残缺 -> 重试
                raise ValueError(f"扩写后仅 {chars} 字，疑似输出残缺")
            # 结构校验：必须有 # 与至少 4 个 ## 小节
            if md.count("## ") < 4:
                raise ValueError(f"## 小节数不足({md.count('## ')}), 结构异常")
            result.update(ok=True, chars=chars, md=md)
            return result
        except Exception as e:
            if attempt < 2:
                time.sleep(3 * (attempt + 1))
            result["error"] = f"{type(e).__name__}: {str(e)[:120]}"
    return result


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--kb", help="只扩写指定库目录名，如 妇儿疾病")
    ap.add_argument("--all", action="store_true", help="扩写全部库")
    ap.add_argument("--min-chars", type=int, default=1000)
    ap.add_argument("--max-chars", type=int, default=1400)
    ap.add_argument("--concurrency", type=int, default=3)
    ap.add_argument("--max-tokens", type=int, default=2600)
    ap.add_argument("--force", action="store_true", help="忽略断点状态全部重跑")
    ap.add_argument("--dry-run", action="store_true", help="只列出待扩写文件")
    args = ap.parse_args()

    if not (args.kb or args.all):
        sys.exit("请指定 --kb <库名> 或 --all")
    if args.kb and args.all:
        sys.exit("--kb 与 --all 互斥")

    # 收集目标文件
    targets = []
    for kb_dir in sorted(UPLOADS.iterdir()):
        if not kb_dir.is_dir():
            continue
        if args.kb and kb_dir.name != args.kb:
            continue
        for sub in ("公开", "私有"):
            subdir = kb_dir / sub
            if not subdir.is_dir():
                continue
            for f in sorted(subdir.glob("*.md")):
                topic = f.stem.strip()
                if SKIP_NAME_RE.match(topic) or not re.search(r"[\u4e00-\u9fff]", topic):
                    print(f"[跳过] {f.relative_to(PROJECT_DIR)} （非医学主题名: {topic!r}）")
                    continue
                targets.append((f, topic, sub))

    if args.dry_run:
        print(f"待扩写 {len(targets)} 篇（目标正文 {args.min_chars}-{args.max_chars} 字）")
        for f, topic, sub in targets:
            print(f"  {sub}  {f.name}  <- {topic}")
        return

    # 断点状态
    state = {"done": [], "skipped": []}
    if STATE_FILE.exists() and not args.force:
        try:
            state = json.loads(STATE_FILE.read_text(encoding="utf-8"))
        except Exception:
            state = {"done": [], "skipped": []}
    done_keys = set(state.get("done", []))

    # 过滤已完成
    todo = []
    for f, topic, sub in targets:
        rel = str(f.relative_to(PROJECT_DIR))
        if rel in done_keys and not args.force:
            print(f"[已跳过] {rel}")
            continue
        todo.append((f, topic, sub, rel))

    print(f"待扩写 {len(todo)} 篇，并发 {args.concurrency}，目标 {args.min_chars}-{args.max_chars} 汉字")
    if not todo:
        print("无待处理文件")
        return

    ok_n, fail_n, warn_short = 0, 0, 0
    t0 = time.time()
    results = []

    def work(item):
        f, topic, sub, rel = item
        original = f.read_text(encoding="utf-8")
        return rel, topic, f, expand_one(rel, topic, original, doc_position(sub),
                                         args.min_chars, args.max_chars, args.max_tokens, args.force)

    with ThreadPoolExecutor(max_workers=args.concurrency) as ex:
        futs = {ex.submit(work, it): it for it in todo}
        n_done = 0
        for fut in as_completed(futs):
            rel, topic, f, r = fut.result()
            n_done += 1
            if r["ok"]:
                f.write_text(r["md"], encoding="utf-8")
                ok_n += 1
                results.append((rel, r["chars"]))
                flag = "" if args.min_chars <= r["chars"] <= args.max_chars else \
                    ("  <下限!" if r["chars"] < args.min_chars else "  >上限")
                if r["chars"] < args.min_chars:
                    warn_short += 1
                print(f"[{n_done}/{len(todo)}] {r['chars']:5d}字 {rel}{flag}")
            else:
                fail_n += 1
                print(f"[{n_done}/{len(todo)}] ✗失败 {rel}  {r['error']}")
            if not args.dry_run:
                done_keys.add(rel)
            STATE_FILE.write_text(
                json.dumps({"done": sorted(done_keys)}, ensure_ascii=False, indent=1),
                encoding="utf-8",
            )

    dur = time.time() - t0
    print("\n==== 扩写汇总 ====")
    print(f"成功 {ok_n}，失败 {fail_n}，不足下限 {warn_short}，耗时 {dur/60:.1f} 分钟")
    if results:
        chars = [c for _, c in results]
        print(f"正文字数: min={min(chars)} max={max(chars)} avg={sum(chars)//len(chars)}")
    if fail_n:
        print("\n失败文件需人工检查（断点状态已保留，重跑自动跳过成功项）")


if __name__ == "__main__":
    main()
