"""
种子数据：自动创建 5 角色用户、12 知识库、240 文档、业务数据。

运行: python seed.py
"""
from pathlib import Path

import os
import random
import sys
import uuid
from datetime import datetime, timedelta
from werkzeug.security import generate_password_hash

# 确保 backend 目录在 path 中
BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR))

from backend import config
from backend.utils.db import (
    execute, fetchone, fetchall, init_schema, DB_TYPE
)
from backend.rag.chunker import chunk_document
from backend.rag.embedder import get_embedder
from backend.rag.vectorstore import get_vectorstore, VectorRecord
from backend.utils.file_parser import (
    is_allowed,
    get_file_type,
    parse_file,
    parse_file_pages,
    strip_header_footer,
)

DEMO_PASSWORD = "demo123"
PASSWORD_HASH = generate_password_hash(DEMO_PASSWORD)

# 12 疾病知识库
DISEASE_KBS = [
    "呼吸系统疾病", "心血管疾病", "消化系统疾病", "神经系统疾病",
    "内分泌代谢疾病", "泌尿肾脏疾病", "风湿免疫疾病", "感染性疾病",
    "急诊急症", "外科骨科疾病", "皮肤科疾病", "妇儿疾病",
]

DEPARTMENTS = [
    "内科", "外科", "心内科", "呼吸科", "消化科", "神经科",
    "内分泌科", "肾内科", "风湿免疫科", "感染科",
    "急诊科", "骨科", "皮肤科", "妇产科", "儿科", "中医科",
]

DOCTOR_NAMES = ["张伟", "李芳", "王强", "刘洋", "陈静", "杨光", "赵敏", "黄磊",
                "周杰", "吴婷", "徐明", "孙丽", "马超", "朱琳", "胡军", "郭艳"]
NURSE_NAMES = ["林雪", "何月", "高翔", "罗琳", "梁宇", "宋佳", "谢斌", "许晴"]
PATIENT_NAMES = ["刘一", "陈二", "张三", "李四", "王五", "赵六", "钱七", "孙八",
                 "周一", "吴二", "郑三", "王四", "冯五", "蒋六", "韩七", "沈八",
                 "杨九", "秦十", "尤一", "许二", "何三", "罗四", "高五", "林六",
                 "赵七", "钱八", "孙九", "李十", "周一", "吴二"]
PUBLIC_NAMES = ["群众甲", "群众乙", "群众丙", "群众丁", "群众戊"]


def _placeholder():
    """返回当前 DB 类型的占位符。"""
    return "%s" if DB_TYPE == "mysql" else "?"


def seed_users():
    """创建 5 角色演示用户 + 更多用户。"""
    print("[Seed] 创建用户...")
    ph = _placeholder()

    # 演示账号
    demo_users = [
        ("patientdemo", "patient", "患者演示"),
        ("doctordemo", "doctor", "医生演示"),
        ("nursedemo", "nurse", "护士演示"),
        ("publicdemo", "public", "群众演示"),
        ("admindemo", "admin", "管理员演示"),
    ]
    for username, role, display_name in demo_users:
        execute(
            f"INSERT INTO users (username, password_hash, role, display_name) VALUES ({ph}, {ph}, {ph}, {ph})",
            (username, PASSWORD_HASH, role, display_name)
        )

    # 更多医生
    for i, name in enumerate(DOCTOR_NAMES):
        username = f"doctor{i + 1:02d}"
        execute(
            f"INSERT INTO users (username, password_hash, role, display_name) VALUES ({ph}, {ph}, {ph}, {ph})",
            (username, PASSWORD_HASH, "doctor", f"{name}医生")
        )

    # 更多护士
    for i, name in enumerate(NURSE_NAMES):
        username = f"nurse{i + 1:02d}"
        execute(
            f"INSERT INTO users (username, password_hash, role, display_name) VALUES ({ph}, {ph}, {ph}, {ph})",
            (username, PASSWORD_HASH, "nurse", f"{name}护士")
        )

    # 更多患者
    for i, name in enumerate(PATIENT_NAMES):
        username = f"patient{i + 1:02d}"
        execute(
            f"INSERT INTO users (username, password_hash, role, display_name) VALUES ({ph}, {ph}, {ph}, {ph})",
            (username, PASSWORD_HASH, "patient", f"{name}")
        )

    # 群众
    for i, name in enumerate(PUBLIC_NAMES):
        username = f"public{i + 1:02d}"
        execute(
            f"INSERT INTO users (username, password_hash, role, display_name) VALUES ({ph}, {ph}, {ph}, {ph})",
            (username, PASSWORD_HASH, "public", name)
        )

    count = fetchone("SELECT COUNT(*) AS cnt FROM users")["cnt"]
    print(f"[Seed] 用户创建完成: {count} 个")


def seed_knowledge_bases():
    """创建 12 疾病知识库 + 医生私有库。"""
    print("[Seed] 创建知识库...")
    ph = _placeholder()

    # 12 个公开疾病知识库
    for name in DISEASE_KBS:
        execute(
            f"INSERT INTO knowledge_bases (owner_id, name, description, visibility) "
            f"VALUES (NULL, {ph}, {ph}, 'public')",
            (name, f"{name}相关知识文档库")
        )

    # 医生私有知识库
    doctor_ids = [r["id"] for r in fetchall("SELECT id FROM users WHERE role = 'doctor'")]
    private_kb_names = [
        "我的临床笔记", "疑难病例讨论", "用药经验总结",
        "手术记录集", "科研文献整理"
    ]
    for i, name in enumerate(private_kb_names):
        owner = doctor_ids[i % len(doctor_ids)]
        execute(
            f"INSERT INTO knowledge_bases (owner_id, name, description, visibility) "
            f"VALUES ({ph}, {ph}, {ph}, 'private')",
            (owner, name, f"私有知识库: {name}")
        )

    # 平台公共私有知识库
    execute(
        f"INSERT INTO knowledge_bases (owner_id, name, description, visibility) "
        f"VALUES (NULL, {ph}, {ph}, 'private')",
        ("医疗质量管理规范", "院内医疗质量管理文档")
    )

    # 管理员私有知识库
    admin_id = fetchone("SELECT id FROM users WHERE role = 'admin'")["id"]
    execute(
        f"INSERT INTO knowledge_bases (owner_id, name, description, visibility) "
        f"VALUES ({ph}, {ph}, {ph}, 'private')",
        (admin_id, "系统管理文档", "系统运维与管理文档")
    )

    count = fetchone("SELECT COUNT(*) AS cnt FROM knowledge_bases")["cnt"]
    print(f"[Seed] 知识库创建完成: {count} 个")


def seed_documents_and_vectors():
    """注册 240 篇文档并切分向量化入库。"""
    print("[Seed] 注册文档并向量化...")
    ph = _placeholder()
    uploads_dir = config.UPLOAD_DIR

    # 知识库映射: name -> id
    kb_map = {}
    for r in fetchall("SELECT id, name FROM knowledge_bases"):
        kb_map[r["name"]] = r["id"]

    embedder = get_embedder()
    vs = get_vectorstore()

    total_docs = 0
    total_chunks = 0

    for kb_name in DISEASE_KBS:
        kb_id = kb_map.get(kb_name)
        if not kb_id:
            continue

        for vis_folder, visibility in [("公开", "public"), ("私有", "private")]:
            folder = uploads_dir / kb_name / vis_folder
            if not folder.exists():
                continue

            # 扫描全部受支持格式（md / txt / pdf / docx / pptx / xlsx ...）
            for doc_file in sorted(p for p in folder.iterdir()
                                   if p.is_file() and is_allowed(p.name)):
                rel_path = f"{kb_name}/{vis_folder}/{doc_file.name}"
                file_type = get_file_type(doc_file.name)
                try:
                    if file_type == "pdf":
                        pages = parse_file_pages(str(doc_file))
                        if sum(len(t.strip()) for _, t in pages) < config.PDF_MIN_TEXT_CHARS:
                            print(f"    [skip] {rel_path}: 无文本层（疑似扫描件）")
                            continue
                        if config.PDF_STRIP_HEADER_FOOTER:
                            pages = strip_header_footer(pages)
                        file_text = "\n\n".join(t for _, t in pages)
                    else:
                        file_text = parse_file(str(doc_file))

                    chunks = chunk_document(file_text)

                    if not chunks:
                        print(f"    [skip] {rel_path}: 无有效文本")
                        continue

                    # 注册文档
                    # review_status='approved'：播种文档为平台预置权威知识，默认可检索
                    # （HITL 仅约束用户上传/AI 回答，不约束预置语料）。
                    execute(
                        f"INSERT INTO documents (kb_id, filename, file_path, file_type, visibility, chunk_count, status, review_status) "
                        f"VALUES ({ph}, {ph}, {ph}, {ph}, {ph}, {ph}, 'ready', 'approved')",
                        (kb_id, doc_file.stem, rel_path, file_type, visibility, len(chunks))
                    )

                    # 获取文档 ID
                    doc_row = fetchone(
                        f"SELECT id FROM documents WHERE file_path = {ph}",
                        (rel_path,)
                    )
                    doc_id = doc_row["id"] if doc_row else 0

                    # 向量化并写入向量库
                    chunk_texts = [c.text for c in chunks]
                    embeddings = embedder.embed_batch(chunk_texts)

                    records = []
                    for chunk, emb in zip(chunks, embeddings):
                        chunk_id = f"doc{doc_id}_chunk{chunk.index}"
                        records.append(VectorRecord(
                            id=chunk_id,
                            kb_id=kb_id,
                            doc_id=doc_id,
                            chunk_index=chunk.index,
                            text=chunk.text,
                            embedding=emb.tolist(),
                        ))

                    vs.insert_batch(records, flush=False)
                    total_docs += 1
                    total_chunks += len(chunks)
                    if total_docs % 20 == 0:
                        print(f"    ... {total_docs} 篇已处理（{total_chunks} chunks）", flush=True)
                except Exception as e:
                    print(f"    [ERROR] {rel_path}: {e}", flush=True)
                    continue

    # 全部文档插入完成后统一 flush 一次，使向量可检索（避免逐条 flush 导致的极慢播种）
    try:
        vs.flush()
        print("[Seed] 向量 flush 完成")
    except Exception as e:  # noqa: BLE001
        print(f"[Seed] 向量 flush 失败（数据仍可能稍后自动落盘）: {e}", flush=True)

    print(f"[Seed] 文档注册完成: {total_docs} 篇, {total_chunks} 个 chunk")


def seed_conversations():
    """创建演示会话与消息。"""
    print("[Seed] 创建会话与消息...")
    ph = _placeholder()

    patient_ids = [r["id"] for r in fetchall("SELECT id FROM users WHERE role = 'patient' LIMIT 10")]
    public_ids = [r["id"] for r in fetchall("SELECT id FROM users WHERE role = 'public' LIMIT 5")]
    all_ids = patient_ids + public_ids

    kb_ids = [r["id"] for r in fetchall("SELECT id FROM knowledge_bases WHERE visibility = 'public' LIMIT 12")]

    qa_pairs = [
        ("高血压应该怎么控制？",
         "根据知识库内容，高血压的控制主要包括以下几个方面：\n1. 生活方式干预：减少钠盐摄入、控制体重、戒烟限酒、适量运动。\n2. 药物治疗：根据血压水平和合并疾病选择合适的降压药物。\n3. 定期监测：每日测量血压，记录血压日记。\n\n⚠️ 本回答仅用于健康知识辅助理解，不构成诊断或治疗建议。"),
        ("糖尿病患者饮食有什么注意事项？",
         "根据知识库内容，糖尿病饮食注意事项包括：\n1. 控制总热量摄入，均衡营养。\n2. 选择低升糖指数食物，如全谷物、蔬菜。\n3. 定时定量进餐，避免暴饮暴食。\n4. 限制高糖、高脂食物。\n\n⚠️ 本回答仅用于健康知识辅助理解，不构成诊断或治疗建议。"),
        ("感冒和流感有什么区别？",
         "根据知识库内容，感冒和流感的区别：\n1. 病原体不同：普通感冒多为鼻病毒等，流感由流感病毒引起。\n2. 症状轻重不同：感冒症状较轻，流感症状重、起病急。\n3. 全身症状：流感常有高热、全身酸痛。\n\n⚠️ 本回答仅用于健康知识辅助理解，不构成诊断或治疗建议。"),
    ]

    for i in range(15):
        user_id = all_ids[i % len(all_ids)]
        kb_id = kb_ids[i % len(kb_ids)]
        conv_id = uuid.uuid4().hex
        qa = qa_pairs[i % len(qa_pairs)]

        execute(
            f"INSERT INTO conversations (id, user_id, kb_id, title) VALUES ({ph}, {ph}, {ph}, {ph})",
            (conv_id, user_id, kb_id, qa[0][:20])
        )
        # user message
        execute(
            f"INSERT INTO messages (conversation_id, role, content) VALUES ({ph}, {ph}, {ph})",
            (conv_id, "user", qa[0])
        )
        msg_id = fetchone(f"SELECT id FROM messages WHERE conversation_id = {ph} ORDER BY id DESC LIMIT 1", (conv_id,))[
            "id"]
        # assistant message
        execute(
            f"INSERT INTO messages (conversation_id, role, content) VALUES ({ph}, {ph}, {ph})",
            (conv_id, "assistant", qa[1])
        )
        # citation
        doc_row = fetchone(f"SELECT id FROM documents WHERE kb_id = {ph} ORDER BY id LIMIT 1", (kb_id,))
        if doc_row:
            execute(
                f"INSERT INTO citations (message_id, document_id, chunk_index, source_text, title, similarity) "
                f"VALUES ({ph}, {ph}, {ph}, {ph}, {ph}, {ph})",
                (msg_id, doc_row["id"], 0, qa[0][:100], "知识库文档", 0.85)
            )

    count = fetchone("SELECT COUNT(*) AS cnt FROM conversations")["cnt"]
    print(f"[Seed] 会话创建完成: {count} 个")


def seed_hospitalizations():
    """创建住院信息。"""
    print("[Seed] 创建住院信息...")
    ph = _placeholder()

    patient_ids = [r["id"] for r in fetchall("SELECT id FROM users WHERE role = 'patient'")]
    doctor_ids = [r["id"] for r in fetchall("SELECT id FROM users WHERE role = 'doctor'")]

    diagnoses = ["高血压3级", "2型糖尿病", "急性支气管炎", "冠心病", "慢性胃炎",
                 "脑梗死", "肺炎", "心力衰竭", "肝硬化", "急性阑尾炎",
                 "肾结石", "哮喘急性发作", "甲状腺功能亢进", "脑出血", "骨折"]

    now = datetime.now()
    for i in range(50):
        pid = patient_ids[i % len(patient_ids)]
        did = doctor_ids[i % len(doctor_ids)]
        dept = DEPARTMENTS[i % len(DEPARTMENTS)]
        admit = (now - timedelta(days=random.randint(1, 60))).strftime("%Y-%m-%d")
        is_discharged = random.random() > 0.4
        discharge = (now - timedelta(days=random.randint(0, 30))).strftime("%Y-%m-%d") if is_discharged else None
        status = "discharged" if is_discharged else "in_hospital"
        cost = round(random.uniform(3000, 50000), 2)

        execute(
            f"INSERT INTO hospitalizations (patient_id, admit_date, discharge_date, department, ward, bed_no, "
            f"diagnosis, doctor_id, status, total_cost) "
            f"VALUES ({ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph})",
            (pid, admit, discharge, dept, f"{dept}病房", f"{random.randint(1, 30):02d}床",
             diagnoses[i % len(diagnoses)], did, status, cost)
        )

    count = fetchone("SELECT COUNT(*) AS cnt FROM hospitalizations")["cnt"]
    print(f"[Seed] 住院信息创建完成: {count} 条")


def seed_bills():
    """创建消费明细。"""
    print("[Seed] 创建消费明细...")
    ph = _placeholder()

    patient_ids = [r["id"] for r in fetchall("SELECT id FROM users WHERE role = 'patient'")]
    categories = ["挂号", "检查", "检验", "药品", "住院", "门诊"]
    descriptions = {
        "挂号": ["普通门诊挂号", "专家门诊挂号", "特需门诊挂号"],
        "检查": ["胸部CT", "腹部B超", "心电图", "心脏彩超", "头颅MRI"],
        "检验": ["血常规", "尿常规", "肝功能", "肾功能", "血脂", "血糖"],
        "药品": ["降压药", "降糖药", "抗生素", "中成药", "营养支持"],
        "住院": ["床位费", "护理费", "手术费", "麻醉费"],
        "门诊": ["门诊治疗", "门诊换药", "门诊注射"],
    }

    for i in range(50):
        pid = patient_ids[i % len(patient_ids)]
        cat = categories[i % len(categories)]
        desc_list = descriptions[cat]
        amount = round(random.uniform(20, 3000), 2)
        bill_no = f"BILL{now_str()}{i:04d}"
        status = "paid" if random.random() > 0.3 else "unpaid"

        execute(
            f"INSERT INTO bills (patient_id, bill_no, category, description, amount, status) "
            f"VALUES ({ph}, {ph}, {ph}, {ph}, {ph}, {ph})",
            (pid, bill_no, cat, random.choice(desc_list), amount, status)
        )

    count = fetchone("SELECT COUNT(*) AS cnt FROM bills")["cnt"]
    print(f"[Seed] 消费明细创建完成: {count} 条")


def seed_appointments():
    """创建预约挂号。"""
    print("[Seed] 创建预约挂号...")
    ph = _placeholder()

    patient_ids = [r["id"] for r in fetchall("SELECT id FROM users WHERE role = 'patient'")]
    public_ids = [r["id"] for r in fetchall("SELECT id FROM users WHERE role = 'public'")]
    all_patient_ids = patient_ids + public_ids
    doctor_ids = [r["id"] for r in fetchall("SELECT id FROM users WHERE role = 'doctor'")]

    time_slots = ["08:00-09:00", "09:00-10:00", "10:00-11:00", "14:00-15:00", "15:00-16:00"]
    symptoms = ["头痛", "咳嗽", "胸闷", "腹痛", "关节疼痛", "视力模糊", "发热", "乏力"]
    statuses = ["booked", "confirmed", "visited", "cancelled"]

    now = datetime.now()
    for i in range(50):
        pid = all_patient_ids[i % len(all_patient_ids)]
        did = doctor_ids[i % len(doctor_ids)]
        dept = DEPARTMENTS[i % len(DEPARTMENTS)]
        date = (now + timedelta(days=random.randint(-30, 30))).strftime("%Y-%m-%d")
        ts = random.choice(time_slots)
        symptom = random.choice(symptoms)
        fee = round(random.uniform(20, 200), 2)
        status = random.choice(statuses)

        execute(
            f"INSERT INTO appointments (patient_id, doctor_id, department, date, time_slot, symptom, fee, status) "
            f"VALUES ({ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph})",
            (pid, did, dept, date, ts, symptom, fee, status)
        )

    count = fetchone("SELECT COUNT(*) AS cnt FROM appointments")["cnt"]
    print(f"[Seed] 预约挂号创建完成: {count} 条")


def seed_nursing_records():
    """创建护理记录。"""
    print("[Seed] 创建护理记录...")
    ph = _placeholder()

    patient_ids = [r["id"] for r in fetchall("SELECT id FROM users WHERE role = 'patient'")]
    nurse_ids = [r["id"] for r in fetchall("SELECT id FROM users WHERE role = 'nurse'")]
    record_types = ["daily", "medication", "vitals", "other"]

    daily_notes = [
        "患者精神可，主诉无明显不适。生命体征平稳，体温36.5℃。",
        "患者诉夜间睡眠欠佳，给予心理疏导。晨起血压 130/80mmHg。",
        "患者今日进食半流质饮食，无恶心呕吐。伤口换药一次。",
        "患者诉头晕较前减轻，遵医嘱继续观察。24小时尿量1500ml。",
    ]
    med_notes = [
        "遵医嘱给予氨氯地平5mg口服，患者无不适。",
        "遵医嘱给予头孢唑肟钠静脉输注，过程顺利。",
        "遵医嘱给予胰岛素8U皮下注射，监测血糖变化。",
        "遵医嘱给予阿司匹林100mg口服，观察有无出血倾向。",
    ]
    vitals_notes = [
        "T:36.8℃ P:78次/分 R:18次/分 BP:125/78mmHg SpO2:98%",
        "T:37.2℃ P:85次/分 R:20次/分 BP:140/85mmHg SpO2:96%",
        "T:36.5℃ P:72次/分 R:16次/分 BP:118/75mmHg SpO2:99%",
        "T:38.1℃ P:92次/分 R:22次/分 BP:135/82mmHg SpO2:94%",
    ]

    now = datetime.now()
    for i in range(50):
        pid = patient_ids[i % len(patient_ids)]
        nid = nurse_ids[i % len(nurse_ids)]
        rtype = record_types[i % len(record_types)]
        if rtype == "daily":
            content = random.choice(daily_notes)
        elif rtype == "medication":
            content = random.choice(med_notes)
        elif rtype == "vitals":
            content = random.choice(vitals_notes)
        else:
            content = "患者一般情况良好，继续目前治疗方案。"
        recorded = (now - timedelta(days=random.randint(0, 30), hours=random.randint(0, 23))).strftime(
            "%Y-%m-%d %H:%M:%S")

        execute(
            f"INSERT INTO nursing_records (patient_id, nurse_id, record_type, content, recorded_at) "
            f"VALUES ({ph}, {ph}, {ph}, {ph}, {ph})",
            (pid, nid, rtype, content, recorded)
        )

    count = fetchone("SELECT COUNT(*) AS cnt FROM nursing_records")["cnt"]
    print(f"[Seed] 护理记录创建完成: {count} 条")


def seed_schedules():
    """创建排班。"""
    print("[Seed] 创建排班...")
    ph = _placeholder()

    staff_ids = [r["id"] for r in fetchall("SELECT id FROM users WHERE role IN ('doctor', 'nurse')")]
    shifts = ["day", "night", "evening", "off"]

    now = datetime.now()
    for i in range(50):
        sid = staff_ids[i % len(staff_ids)]
        dept = DEPARTMENTS[i % len(DEPARTMENTS)]
        date = (now + timedelta(days=random.randint(-7, 14))).strftime("%Y-%m-%d")
        shift = shifts[i % len(shifts)]
        status = "on_duty" if shift != "off" else "off"
        remark = "" if random.random() > 0.2 else "备注信息"

        execute(
            f"INSERT INTO schedules (staff_id, work_date, shift, department, remark, status) "
            f"VALUES ({ph}, {ph}, {ph}, {ph}, {ph}, {ph})",
            (sid, date, shift, dept, remark, status)
        )

    count = fetchone("SELECT COUNT(*) AS cnt FROM schedules")["cnt"]
    print(f"[Seed] 排班创建完成: {count} 条")


def now_str():
    return datetime.now().strftime("%Y%m%d%H%M%S")


def seed_all():
    """执行全部播种。"""
    # 将日志写到文件，避免 Windows 控制台编码导致崩溃
    logf = open(os.path.join(BASE_DIR, "seed_run.log"), "w", encoding="utf-8")

    def log(msg):
        try:
            logf.write(msg + "\n")
            logf.flush()
        except Exception:
            pass

    log("=" * 60)
    log("  医智助手 · 数据播种")
    log("=" * 60)

    steps = [
        ("init_schema", init_schema),
        ("seed_users", seed_users),
        ("seed_knowledge_bases", seed_knowledge_bases),
        ("seed_documents_and_vectors", seed_documents_and_vectors),
        ("seed_conversations", seed_conversations),
        ("seed_hospitalizations", seed_hospitalizations),
        ("seed_bills", seed_bills),
        ("seed_appointments", seed_appointments),
        ("seed_nursing_records", seed_nursing_records),
        ("seed_schedules", seed_schedules),
    ]

    try:
        for name, fn in steps:
            log(f"[STEP] {name} ...")
            fn()
            log(f"[STEP] {name} OK")
    except Exception as e:
        import traceback
        log(f"[FATAL] {name} 失败: {type(e).__name__}: {e}")
        log(traceback.format_exc())
        logf.close()
        raise

    log("=" * 60)
    log("  播种完成！")
    log(f"  演示账号: patientdemo / doctordemo / nursedemo / publicdemo / admindemo")
    log(f"  密码: {DEMO_PASSWORD}")
    log("=" * 60)
    logf.close()


if __name__ == "__main__":
    seed_all()
