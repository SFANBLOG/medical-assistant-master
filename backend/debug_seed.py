"""调试：定位 seed 文档向量化的崩溃点（原生崩溃时通过日志定位）"""
import os, sys, faulthandler
os.environ['MILVUS_ENABLE'] = '0'
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

LOG = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'crash_trace.log'), 'w', encoding='utf-8')

def log(msg):
    LOG.write(msg + '\n')
    LOG.flush()

faulthandler.enable(file=LOG)

from backend import config
from backend.utils.db import fetchall, execute, fetchone
from backend.utils.file_parser import parse_file
from backend.rag.chunker import chunk_document
from backend.rag.embedder import get_embedder
from backend.rag.vectorstore import get_vectorstore, VectorRecord

DISEASE_KBS = [
    '呼吸系统疾病', '心血管疾病', '消化系统疾病', '神经系统疾病',
    '内分泌代谢疾病', '泌尿肾脏疾病', '风湿免疫疾病', '感染性疾病',
    '急诊急症', '外科骨科疾病', '皮肤科疾病', '妇儿疾病',
]

log('=== START ===')
kb_map = {r['name']: r['id'] for r in fetchall('SELECT id, name FROM knowledge_bases')}
log(f'kb_map: {len(kb_map)}')

embedder = get_embedder()
log('embedder OK')
vs = get_vectorstore()
log(f'vectorstore: {vs.__class__.__name__}')

total = 0
for kb_name in DISEASE_KBS:
    kb_id = kb_map.get(kb_name)
    if not kb_id:
        log(f'SKIP KB {kb_name}')
        continue
    for vis_folder, visibility in [('公开', 'public'), ('私有', 'private')]:
        folder = config.UPLOAD_DIR / kb_name / vis_folder
        if not folder.exists():
            log(f'NO FOLDER {folder}')
            continue
        for md_file in sorted(folder.glob('*.md')):
            total += 1
            log(f'[{total}] {kb_name}/{vis_folder}/{md_file.name}')
            rel_path = f'{kb_name}/{vis_folder}/{md_file.name}'
            try:
                file_text = parse_file(str(md_file))
                chunks = chunk_document(file_text)
                if not chunks:
                    log('  no chunks')
                    continue
                execute(
                    'INSERT INTO documents (kb_id, filename, file_path, file_type, visibility, chunk_count, status) VALUES (%s, %s, %s, %s, %s, %s, %s)',
                    (kb_id, md_file.stem, rel_path, 'md', visibility, len(chunks), 'ready')
                )
                doc_row = fetchone('SELECT id FROM documents WHERE file_path = %s ORDER BY id DESC LIMIT 1', (rel_path,))
                doc_id = doc_row['id'] if doc_row else 0
                log(f'  doc_id={doc_id}, chunks={len(chunks)}')
                embeddings = embedder.embed_batch([c.text for c in chunks])
                records = []
                for chunk, emb in zip(chunks, embeddings):
                    records.append(VectorRecord(
                        id=f'doc{doc_id}_chunk{chunk.index}', kb_id=kb_id, doc_id=doc_id,
                        chunk_index=chunk.index, text=chunk.text, embedding=emb.tolist()
                    ))
                vs.insert_batch(records)
                log('  inserted OK')
            except Exception as e:
                log(f'  EXC: {type(e).__name__}: {e}')

log(f'=== DONE, total={total} ===')
LOG.close()
print('All done, total =', total)
