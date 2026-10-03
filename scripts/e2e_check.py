# 端到端验证：单容器模式（Flask 托管前端 + 注册/登录/问答全流程）
import json
import requests

BASE = "http://127.0.0.1:8010"

# 1. 前端页面
r = requests.get(f"{BASE}/", timeout=10)
assert r.status_code == 200 and "<div id=\"app\"" in r.text, f"前端页面异常: {r.status_code}"
print("1. GET / -> 200，返回 Vue 前端页面  ✅")

# 静态资源可达（hash 文件名从 index.html 里抠一个）
import re
asset = re.search(r'src="(/assets/[^"]+\.js)"', r.text)
if asset:
    r2 = requests.get(BASE + asset.group(1), timeout=10)
    assert r2.status_code == 200, f"静态资源 404: {asset.group(1)}"
    print(f"2. GET {asset.group(1)} -> 200  ✅")

# 3. 健康检查
r = requests.get(f"{BASE}/api/health", timeout=10).json()
assert r["status"] == "ok" and r["db_type"] == "sqlite"
print(f"3. /api/health -> {r}  ✅")

# 4. 注册新账号（模拟真实新用户）
import time
uname = f"e2etest{int(time.time())}"
r = requests.post(f"{BASE}/api/auth/register",
                  json={"username": uname, "password": "test1234", "role": "patient", "display_name": "端到端测试员"},
                  timeout=10)
assert r.status_code in (200, 201), f"注册失败 {r.status_code}: {r.text[:200]}"
print(f"4. 注册新用户 {uname} -> {r.status_code}  ✅")

# 5. 新账号登录拿 token
r = requests.post(f"{BASE}/api/auth/login", json={"username": uname, "password": "test1234"}, timeout=10)
assert r.status_code == 200, f"登录失败: {r.text[:200]}"
token = r.json()["token"]
print("5. 新用户登录成功，获得 JWT  ✅")

# 6. 演示账号登录（医生角色）
r = requests.post(f"{BASE}/api/auth/login", json={"username": "doctordemo", "password": "demo123"}, timeout=10)
assert r.status_code == 200, f"医生登录失败: {r.text[:200]}"
dtoken = r.json()["token"]
print("6. doctordemo 登录成功（医生门户） ✅")

H = {"Authorization": f"Bearer {token}"}

# 7. 创建会话 + SSE 提问（完整 RAG 链路：护栏→召回→精排→上下文→生成）
r = requests.post(f"{BASE}/api/chat/conversations", json={"title": "e2e 测试会话"}, headers=H, timeout=10)
assert r.status_code in (200, 201), f"建会话失败 {r.status_code}: {r.text[:200]}"
conv = r.json()
conv_id = conv.get("id") or conv.get("conversation", {}).get("id")
print(f"7. 创建会话 id={conv_id}  ✅")

with requests.post(f"{BASE}/api/chat/stream/{conv_id}",
                   json={"question": "儿童发烧怎么处理", "kb_id": None},
                   headers=H, stream=True, timeout=120) as resp:
    assert resp.status_code == 200, f"SSE 失败 {resp.status_code}"
    citations, content = None, ""
    for line in resp.iter_lines(decode_unicode=True):
        if not line or not line.startswith("data:"):
            continue
        ev = json.loads(line[5:])
        if "citations" in ev:
            citations = ev["citations"]
        if ev.get("content"):
            content += ev["content"]
        if ev.get("done"):
            break
assert citations and len(citations) > 0, "SSE 未返回引用来源（精排/检索链路异常）"
assert len(content) > 20, "SSE 未返回有效回答"
print(f"8. SSE 问答：引用 {len(citations)} 条来源，回答 {len(content)} 字  ✅")
print(f"   首条引用: {citations[0].get('filename')} (相关度 {citations[0].get('similarity')})")
print(f"   回答开头: {content[:60]}...")

# 9. 历史记录落库
r = requests.get(f"{BASE}/api/chat/history", headers=H, timeout=10)
assert r.status_code == 200
print("9. 会话历史接口正常  ✅")

print("\n🎉 端到端全部通过：注册 → 登录 → RAG 问答（含精排引用）→ 历史，全链路可用")
