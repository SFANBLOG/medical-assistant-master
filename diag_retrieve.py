import time, traceback
t0 = time.time()
try:
    from backend.rag.retriever import retrieve
    print("import ok", round(time.time() - t0, 2), flush=True)
    t1 = time.time()
    hits = retrieve("感冒发烧应该注意什么？", "doctor", 1, top_k=5)
    print("retrieve done in", round(time.time() - t1, 2), "s; hits=", len(hits), flush=True)
    for h in hits[:3]:
        print("  -", h.get("filename"), round(h.get("similarity", 0), 3),
              str(h.get("text", ""))[:40], flush=True)
except Exception as e:
    print("ERROR after", round(time.time() - t0, 2), "s:", repr(e), flush=True)
    traceback.print_exc()
