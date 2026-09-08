"""
RAG 检索质量验证脚本。

用法：
    python scripts/test_retrieval.py

用一组医学问答测试检索相关度，对比改进前后。
"""
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ.setdefault("DB_TYPE", "mysql")
os.environ.setdefault("MILVUS_ENABLE", "0")


# 测试用例：(query, 期望匹配的知识库/文档关键词)
TEST_CASES = [
    ("儿童发热需要立刻就医吗？", ["发热", "儿童", "发烧", "体温"]),
    ("小儿肺炎的症状有哪些？", ["肺炎", "症状", "咳嗽", "发热", "呼吸"]),
    ("糖尿病的诊断标准是什么？", ["糖尿病", "诊断", "血糖", "空腹"]),
    ("高血压患者需要注意什么？", ["高血压", "血压", "注意", "饮食"]),
    ("婴儿腹泻怎么办？", ["腹泻", "婴儿", "拉肚子", "脱水"]),
]


def main():
    from backend.rag.retriever import retrieve
    from backend.rag.embedder import get_embedder
    from backend.rag.reranker import get_reranker

    print("=" * 65)
    print("  RAG 检索质量验证")
    print("=" * 65)

    embedder = get_embedder()
    reranker = get_reranker()
    print(f"\nEmbedder: {type(embedder).__name__}")
    print(f"Reranker: {reranker.model_info}")
    print(f"Using real CE model: {reranker.using_real_model}")
    print()

    all_scores = []
    for i, (query, expected_kws) in enumerate(TEST_CASES):
        print(f"--- 测试 {i+1}/{len(TEST_CASES)} ---")
        print(f"查询: {query}")

        t0 = time.time()
        hits = retrieve(query, role="public", user_id=0)
        elapsed = time.time() - t0

        print(f"耗时: {elapsed*1000:.0f}ms | 命中: {len(hits)} 条")
        if not hits:
            print("  ⚠️ 无结果！\n")
            continue

        for j, h in enumerate(hits):
            score = h.get("similarity", h.get("score", 0))
            # 检查期望关键词命中
            text_preview = h["text"][:80].replace("\n", " ")
            kw_hits = sum(1 for k in expected_kws if k in h["text"])
            marker = "✓" if score >= 0.85 else ("~" if score >= 0.60 else "✗")
            print(f"  [{marker}] #{j+1} 相关度={score:.1%} "
                  f"| {h.get('filename', '?')} | 关键词命中={kw_hits}/{len(expected_kws)}")
            print(f"      {text_preview}...")
            all_scores.append(score)
        print()

    # 汇总
    if all_scores:
        avg = sum(all_scores) / len(all_scores)
        top1_avg = sum(all_scores[::len(TEST_CASES)][:len(TEST_CASES)]) / min(len(TEST_CASES), len(all_scores))
        print("=" * 65)
        print(f"  全部 {len(all_scores)} 条结果平均分: {avg:.1%}")
        print(f"  首条结果平均分: {top1_avg:.1%}")
        print(f"  最高分: {max(all_scores):.1%} | 最低分: {min(all_scores):.1%}")
        print(f"  >= 90%: {sum(1 for s in all_scores if s >= 0.90)}/{len(all_scores)}")
        print(f"  >= 70%: {sum(1 for s in all_scores if s >= 0.70)}/{len(all_scores)}")
        print(f"  <  50%: {sum(1 for s in all_scores if s < 0.50)}/{len(all_scores)}")
        print("=" * 65)


if __name__ == "__main__":
    main()
