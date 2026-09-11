"""Smoke test for /api/kb/<id>/documents/batch end-to-end.

Uses a tiny raw multipart encoder so we don't fight Werkzeug's test client
quirks around multi-value fields.
"""
import json
import sys

sys.path.insert(0, '.')
from backend.app import create_app
from backend.utils.db import execute

app = create_app()
app.config['TESTING'] = True
client = app.test_client()


def login(user, pwd='demo123'):
    r = client.post('/api/auth/login', json={'username': user, 'password': pwd})
    assert r.status_code == 200, r.get_json()
    return r.get_json()['token']


token = login('doctordemo')
H = {'Authorization': 'Bearer ' + token}

# Find a KB
r = client.get('/api/kb/?page=1&size=100', headers=H)
kbs = r.get_json().get('list', [])
target = next((k for k in kbs if k.get('visibility') == 'public'), kbs[0])
kb_id = target['id']
print('using KB:', kb_id, target['name'])


def build_multipart(fields, files):
    """Build a multipart/form-data body manually.

    fields: list of (key, value) str pairs
    files:  list of (key, filename, content_bytes, content_type) tuples
    """
    import uuid
    BOUNDARY = '----WB' + uuid.uuid4().hex
    chunks = []
    for k, v in fields:
        chunks.append(('--' + BOUNDARY).encode())
        chunks.append(f'Content-Disposition: form-data; name="{k}"\r\n'.encode())
        chunks.append(v.encode())
        chunks.append(b'')
    for k, fn, body, ct in files:
        chunks.append(('--' + BOUNDARY).encode())
        chunks.append(
            f'Content-Disposition: form-data; name="{k}"; filename="{fn}"\r\n'.encode()
        )
        chunks.append(f'Content-Type: {ct}\r\n'.encode())
        chunks.append(body)
        chunks.append(b'')
    chunks.append(('--' + BOUNDARY + '--').encode())
    chunks.append(b'')
    body = b'\r\n'.join(chunks)
    return body, 'multipart/form-data; boundary=' + BOUNDARY


# === Test 1: 2 valid + 1 bad extension ===
files = [
    ('files', 'bulk_test_a.md', b'# Test Batch 1\n\nFirst batch document.\n\n## Symptom\nFever.', 'text/markdown'),
    ('files', 'bulk_test_b.md', b'# Test Batch 2\n\nSecond batch document.\n\n## Treatment\nAnti-inflammatory.', 'text/markdown'),
    ('files', 'bad.unknownext', b'\x00\x01bad', 'application/octet-stream'),
]
body, ctype = build_multipart(
    fields=[('visibility', 'public')],
    files=files,
)
# clean up any prior runs of this test
execute("DELETE FROM documents WHERE kb_id = %s AND filename IN %s",
        (kb_id, ('bulk_test_a.md', 'bulk_test_b.md')))
# Also try to remove orphan files
from backend import config
vis_dir = config.UPLOAD_DIR / target['name'] / '公开'
for nm in ('bulk_test_a.md', 'bulk_test_b.md'):
    p = vis_dir / nm
    if p.exists(): p.unlink()

r = client.post(
    f'/api/kb/{kb_id}/documents/batch?visibility=public',
    data=body,
    headers={**H, 'Content-Type': ctype},
)

print('\nTest 1 (mixed batch):')
print('  status:', r.status_code)
res = r.get_json()
print(json.dumps(res, ensure_ascii=False, indent=2))
assert r.status_code == 200
assert res['summary'] == {'total': 3, 'success': 2, 'failed': 1}
ok = {x['filename'] for x in res['results'] if x['ok']}
fail = {x['filename'] for x in res['results'] if not x['ok']}
assert ok == {'bulk_test_a.md', 'bulk_test_b.md'}
assert fail == {'bad.unknownext'}


# === Test 2: empty list → 400 ===
body, ctype = build_multipart(fields=[('visibility', 'public')], files=[])
r = client.post(f'/api/kb/{kb_id}/documents/batch?visibility=public',
                data=body, headers={**H, 'Content-Type': ctype})
print('\nTest 2 (empty):')
print('  status:', r.status_code, ' body:', r.get_json())
assert r.status_code == 400


# === Test 3: nonexistent KB → 200 with all failed ===
body, ctype = build_multipart(fields=[('visibility', 'public')], files=files[:1])
r = client.post(f'/api/kb/99999/documents/batch?visibility=public',
                data=body, headers={**H, 'Content-Type': ctype})
print('\nTest 3 (bad kb):')
print('  status:', r.status_code)
res = r.get_json()
print(json.dumps(res, ensure_ascii=False, indent=2)[:300])
assert r.status_code == 200
assert res['summary']['failed'] == 1


# === Test 4: cleanup ===
execute("DELETE FROM documents WHERE kb_id = %s AND filename IN %s",
        (kb_id, ('bulk_test_a.md', 'bulk_test_b.md')))
for nm in ('bulk_test_a.md', 'bulk_test_b.md'):
    p = vis_dir / nm
    if p.exists(): p.unlink()
print('\n[cleanup done]')

print('\n[OK] All assertions passed.')
