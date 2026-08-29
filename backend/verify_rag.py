"""端到端验证：不同角色提问 -> 检索正确参考文档 + 相似度（疾病名类 >= 0.95）+ 权限隔离。

用法（backend 目录下）：
    python verify_rag.py
"""
import json
import os
import sys

os.environ["HF_ENDPOINT"] = "https://hf-mirror.com"
sys.path.insert(0, os.getcwd())

from app import app

# (账号, 问题, 期望文档关键词, 期望命中, 是否要求标题级>=0.95)
CASES = [
    ("patientdemo", "糖尿病患者如何控制血糖？", "糖尿病", True, True),
    ("patientdemo", "高血压患者日常饮食需要注意什么？", "高血压", True, True),
    ("patientdemo", "痛风发作时应该怎么办？", "痛风", True, True),
    ("patientdemo", "带状疱疹会传染吗？", "带状疱疹", True, True),
    ("publicdemo", "流感疫苗什么时候打比较好？", "流感", True, True),
    ("publicdemo", "骨折后应该如何固定？", "骨折", True, True),
    ("doctordemo", "胰岛素使用与剂量调整的要点有哪些？", "胰岛素", True, True),
    # 症状/非标题类：要求检索到正确文档（相似度按实际给出）
    ("publicdemo", "宝宝发烧应该怎么护理？", "发热", True, False),
    ("patientdemo", "膝关节疼痛是什么原因？", "关节", True, False),
    ("publicdemo", "孕妇血糖偏高有什么影响？", "妊娠期糖尿病", True, False),
    # 权限隔离：私有文档患者不可见
    ("patientdemo", "胰岛素使用与剂量调整的要点有哪些？", "胰岛素", False, False),
    ("patientdemo", "上消化道出血怎么处理？", "上消化道出血", False, False),
]

ROLE_CN = {"patient": "患者", "doctor": "医生", "nurse": "护士", "public": "群众", "admin": "管理员"}


def parse_sse(resp_text: str) -> dict:
    out = {}
    for frame in resp_text.split("\n\n"):
        for line in frame.split("\n"):
            if line.startswith("data:"):
                try:
                    evt = json.loads(line[5:].strip())
                except Exception:
                    continue
                if evt.get("type") == "done":
                    out["citations"] = evt.get("citations") or []
    return out


def run_case(client, token, username, q, expect_kw, expect_hit, require_95):
    resp = client.post(
        "/api/chat/ask",
        json={"kb_id": 0, "question": q},
        headers={"Authorization": f"Bearer {token}"},
    )
    if resp.status_code != 200:
        print(f"  [ERROR] HTTP {resp.status_code}: {resp.get_data(as_text=True)[:200]}")
        return False
    data = parse_sse(resp.get_data(as_text=True))
    cits = data.get("citations", [])
    top = cits[0] if cits else None
    hit = top and expect_kw in top["title"]
    sim = top["similarity"] if top else 0.0
    doc_ok = (hit == expect_hit)
    sim_ok = (sim >= 0.95) if (require_95 and hit) else True
    ok = doc_ok and sim_ok
    label = "PASS" if ok else "FAIL"
    if top:
        print(f"[{label}] {username}({ROLE_CN.get(username[:-4], '')}) 问：{q[:24]}")
        print(f"        top1: {top['title']}  相似度={sim:.3f}  命中={hit}(期望{expect_hit})")
    else:
        print(f"[{label}] {username} 问：{q[:24]}  -> 无引用")
    return ok


def main():
    client = app.test_client()
    total = passed = 0
    tokens = {}
    with app.app_context():
        for username in ("patientdemo", "publicdemo", "doctordemo"):
            r = client.post("/api/auth/login", json={"username": username, "password": "demo123"})
            tokens[username] = r.get_json()["token"]
        for username, q, kw, hit, req95 in CASES:
            total += 1
            if run_case(client, tokens[username], username, q, kw, hit, req95):
                passed += 1
        print(f"\n结果：{passed}/{total} 通过")


if __name__ == "__main__":
    main()
