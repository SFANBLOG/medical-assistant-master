"""
RAG 管线自检：验证检索正确性、角色可见性与相似度（修复「相似度 0.3~0.5」问题）。
用法：在 backend 目录下执行
  python verify_rag.py
会自动完成：建库建表 → 播种 → 索引知识库，随后执行检索用例。
"""
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

import config as cfg
from models.db import init_db
from seed import bootstrap
from services import kb_service
from services.embeddings import get_embedder
from services.retriever import retrieve
from services.vector_store import get_vector_store
from models import db


def setup():
    print(">>> 初始化数据库 & 播种 & 索引 ...")
    init_db()
    bootstrap()
    store = get_vector_store()
    if store.count() == 0:
        kb_service.reindex_all()
    else:
        print(f">>> 向量库已有 {store.count()} 个片段。")


def test_retrieval():
    print(f"\n嵌入模式：{get_embedder().mode}  向量库：{get_vector_store().__class__.__name__}")
    print(f"向量库片段数：{get_vector_store().count()}\n")

    cases = [
        ("感冒有哪些常见症状？", "patient", "呼吸系统疾病"),
        ("高血压患者平时需要注意什么？", "patient", "心血管疾病"),
        ("糖尿病的饮食管理建议", "public", "内分泌代谢疾病"),
        ("脑卒中发病时有哪些表现？", "nurse", "神经系统疾病"),
    ]
    ok = True
    for q, role, expect_kb in cases:
        res = retrieve(q, role)
        print(f"【{role}】查询：{q}")
        if not res:
            print("  （无召回）❌"); ok = False; continue
        top = res[0]
        print(f"  命中相似度 {top['similarity']:.4f} | {top['title']} | 可见性={top.get('visibility')}")
        print(f"  片段：{top['text'][:46]}...")
        if top['similarity'] < 0.30:
            print("  ❌ 相似度过低（<0.30）"); ok = False

    # 精确匹配：查询文本作为片段命中 → 相似度必须 ≥0.95
    print("\n=== 精确匹配验证（相似度需 ≥0.95）===")
    r = retrieve("感冒与流感", "doctor")
    assert r, "未召回，请确认索引已生成"
    top = r[0]
    print(f"查询「感冒与流感」→ 最高相似度 {top['similarity']:.4f}  title={top['title']}")
    assert top['similarity'] >= 0.95, f"相似度未达 0.95：{top['similarity']}"
    print("✅ 精确匹配相似度 ≥0.95 校验通过")

    # 角色可见性：public 角色不能检索到 private 文档
    print("\n=== 角色可见性验证（public 不应看到 private 文档）===")
    priv = db.query("SELECT id FROM documents WHERE visibility='private' LIMIT 1")
    if priv:
        r_pub = retrieve("呼吸衰竭分型与氧疗", "public")
        saw_private = any(c.get("visibility") == "private" for c in r_pub)
        r_doc = retrieve("呼吸衰竭分型与氧疗", "doctor")
        doc_saw_private = any(c.get("visibility") == "private" for c in r_doc)
        print(f"  public 检索是否含私有文档：{saw_private}；doctor 检索是否含私有文档：{doc_saw_private}")
        assert not saw_private, "❌ public 角色越权看到了私有文档"
        assert doc_saw_private, "❌ doctor 角色未能看到私有文档"
        print("✅ 角色可见性校验通过（public 不可见 / doctor 可见）")
    else:
        print("  （无私有文档，跳过）")

    print("\n=== 自检结论 ===")
    print("✅ 全部通过" if ok else "❌ 存在不达标项")
    return ok


if __name__ == "__main__":
    setup()
    test_retrieval()
