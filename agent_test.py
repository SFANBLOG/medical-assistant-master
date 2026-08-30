import json, sys, requests

requests.Session.trust_env = False
s = requests.Session()
s.trust_env = False
s.proxies = {"http": None, "https": None}

BASE = "http://127.0.0.1:8010"
TO = 180

def log(*a):
    print(*a, flush=True)

# 1. login
r = s.post(f"{BASE}/api/auth/login", json={"username": "doctordemo", "password": "demo123"}, timeout=TO)
log("LOGIN", r.status_code, r.text[:120])
j = r.json()
token = j.get("token") or j.get("access_token")
log("TOKEN?", bool(token))
H = {"Authorization": f"Bearer {token}"}

# 2. create conversation
r = s.post(f"{BASE}/api/chat/conversations", headers=H, json={"title": "Agent测试"}, timeout=TO)
log("CREATE_CONV", r.status_code, r.text[:120])
conv_id = r.json().get("id")
log("CONV_ID", conv_id)

# 3. stream agent
for q in ["感冒发烧应该注意什么？患者 patientdemo 的住院情况如何？", "南京今天天气怎么样？"]:
    log(f"\n===== AGENT STREAM: {q} =====")
    r = s.post(f"{BASE}/api/agent/stream/{conv_id}", headers=H, json={"question": q}, stream=True, timeout=TO)
    log("STREAM STATUS", r.status_code)
    if r.status_code != 200:
        log("  BODY:", r.text[:300])
        continue
    types = []
    for line in r.iter_lines(decode_unicode=True):
        if not line or not line.startswith("data:"):
            continue
        try:
            ev = json.loads(line[5:].strip())
        except Exception:
            continue
        t = ev.get("type")
        if t:
            types.append(t)
        if t == "thought":
            log(f"  [thought] {ev.get('content','')[:80]}")
        elif t == "tool_call":
            log(f"  [tool_call] {ev.get('name')} args={ev.get('args')}")
        elif t == "observation":
            log(f"  [observation] {ev.get('content','')[:140]}")
        elif t == "citations":
            log(f"  [citations] count={len(ev.get('citations',[]))}")
        elif t == "done":
            log("  [done]")
        elif t == "error":
            log(f"  [error] {ev.get('content')}")
    log("  EVENT TYPES:", types)
log("\nALL DONE")
