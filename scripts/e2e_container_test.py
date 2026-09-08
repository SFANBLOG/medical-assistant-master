"""容器内直连 gunicorn 的 SSE E2E 测试 v2：统计 data:/event: 两类行"""
import json
import sys
import time
import urllib.request

BASE = "http://127.0.0.1:8010"


def http_json(path, payload, token=None):
    data = json.dumps(payload).encode() if payload is not None else None
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = "Bearer " + token
    req = urllib.request.Request(BASE + path, data=data, headers=headers)
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode())


res = http_json("/api/auth/login", {"username": "doctordemo", "password": "demo123"})
token = res.get("access_token") or res.get("token")
print("LOGIN_OK:", bool(token))
if not token:
    sys.exit(1)

conv = http_json("/api/chat/conversations", {"kb_id": 12, "title": "container-e2e-v2"}, token=token)
conv_id = conv.get("conversation_id") or conv.get("id")
print("CONV_ID:", conv_id)

body = json.dumps({"question": "新生儿黄疸怎么办？", "kb_id": 12}).encode()
req = urllib.request.Request(
    BASE + f"/api/chat/stream/{conv_id}",
    data=body,
    headers={"Content-Type": "application/json", "Authorization": "Bearer " + token},
    method="POST",
)
t0 = time.time()
data_rows = 0
event_rows = 0
first_byte = None
citations_seen = None
content_len = 0
try:
    with urllib.request.urlopen(req, timeout=90) as r:
        print("STREAM_STATUS:", r.status, "| CT:", r.headers.get("Content-Type"))
        for raw in r:
            if first_byte is None:
                first_byte = round(time.time() - t0, 2)
            line = raw.decode("utf-8", "replace").strip()
            if not line:
                continue
            if line.startswith("event:"):
                event_rows += 1
            elif line.startswith("data:"):
                data_rows += 1
                payload = line[5:].strip()
                if citations_seen is None and '"citations"' in payload:
                    try:
                        obj = json.loads(payload)
                        citations_seen = obj.get("citations")
                    except Exception:
                        pass
                elif payload and '"content"' in payload:
                    try:
                        content_len += len(json.loads(payload).get("content", ""))
                    except Exception:
                        pass
            if time.time() - t0 > 55:
                print("GIVE_UP_55s")
                break
        print("FIRST_BYTE_SEC:", first_byte)
        print("DATA_ROWS:", data_rows, "| EVENT_ROWS:", event_rows)
        print("CONTENT_CHARS:", content_len)
        if citations_seen:
            print(f"CITATIONS: {len(citations_seen)} 条")
            for c in citations_seen:
                print(f"    sim={c.get('similarity')} doc={c.get('doc_id')} {c.get('title')}")
        else:
            print("CITATIONS: 未捕获")
except Exception as e:
    print("STREAM_ERROR:", type(e).__name__, str(e)[:300])
