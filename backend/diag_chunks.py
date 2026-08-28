# -*- coding: utf-8 -*-
"""
临时诊断脚本：核对「向量库 chunk 内容」与「数据库文档标题」是否一致。
用于定位「引用文档相似度低 / 标题与内容错配」的数据问题。
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.rag.vectorstore import get_vectorstore  # noqa: E402
from backend.utils.db import fetchall  # noqa: E402


def main():
    vs = get_vectorstore()
    print(f"[diag] vector store = {type(vs).__name__}, count = {vs.count}")

    chunks = vs.get_all_chunks()
    print(f"[diag] exported chunks = {len(chunks)}")

    # doc_id -> (filename, first chunk text)
    docs = {r["id"]: r for r in fetchall("SELECT id, kb_id, filename FROM documents")}

    mismatch = 0
    checked = 0
    by_doc: dict = {}
    for c in chunks:
        by_doc.setdefault(c["doc_id"], []).append(c)

    print("\n" + "=" * 78)
    print(f"{'doc_id':>7} | {'filename':<28} | first chunk preview")
    print("=" * 78)

    for doc_id in sorted(by_doc.keys()):
        chunks_of = by_doc[doc_id]
        first = chunks_of[0]["text"].replace("\n", " ").strip()
        meta = docs.get(doc_id)
        fname = meta["filename"] if meta else "<MISSING>"
        preview = first[:44]
        print(f"{doc_id:>7} | {fname:<28} | {preview}")

        # 一致性校验：chunk 开头的标题行（# xxx）应与文件名主体一致
        if meta and first.startswith("#"):
            checked += 1
            # 提取 markdown 一级标题
            head = first.lstrip("#").strip()
            # 去掉可能的 ## 二级标记
            head = head.split("#")[0].strip()
            stem = fname.rsplit(".", 1)[0]
            # seed_ 前缀文件名取中文部分
            if "_" in stem and stem.startswith("seed_"):
                stem = stem.split("_", 2)[-1]
            if head and stem and head not in stem and stem not in head:
                mismatch += 1
                print(f"        ^^^ MISMATCH: chunk 标题='{head}' vs 文件名='{stem}'")

    print("=" * 78)
    print(f"[diag] 检查 {checked} 个文档，内容/标题不一致 {mismatch} 个")


if __name__ == "__main__":
    main()
