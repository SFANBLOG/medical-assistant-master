"""演示数据播种（幂等）：5 种角色演示账号 + 12 个疾病知识库（公开/私有文档） + 各表 ≥50 条业务数据。

数据库：MySQL `medical-assistant-master`（或 DB_TYPE=sqlite 时的本地 SQLite）。
运行：python seed.py 或 python app.py --seed

文档来源：backend/data/kb_docs_src/<知识库>/公开|私有/*.md，
落盘到 backend/data/uploads/<知识库>/公开|私有/ 并向量化入库。
"""
import os
import uuid
from datetime import date, timedelta

from data.kb_docs import DISEASE_KBS, KB_DOCS_SRC_DIR
from models.db import get_conn, init_schema
from services import auth_service
from services.doc_pipeline import process_document
from utils.file_utils import safe_folder_name

DEMO_PASSWORD = "demo123"

ROLE_CN = {"patient": "患者", "doctor": "医生", "nurse": "护士", "public": "群众", "admin": "管理员"}

# ---- 各表目标行数（至少 50）----
USERS_TARGET = 50
KBS_TARGET = 50
CONVERSATIONS_TARGET = 50
CITATIONS_TARGET = 50
HOSPITALIZATIONS_TARGET = 50
BILLS_TARGET = 50
APPOINTMENTS_TARGET = 50
NURSING_TARGET = 50
SCHEDULES_TARGET = 50

DEPARTMENTS = [
    "心血管内科", "呼吸内科", "消化内科", "神经内科", "内分泌科",
    "肾内科", "风湿免疫科", "感染科", "急诊科", "骨科",
    "皮肤科", "儿科", "妇产科", "普外科",
]
DIAGNOSES = [
    "高血压病", "2型糖尿病", "急性阑尾炎", "慢性胃炎", "支气管哮喘",
    "冠心病", "腰椎间盘突出症", "泌尿系感染", "类风湿关节炎", "社区获得性肺炎",
]
SHIFTS = ["day", "night", "evening", "off"]
BILL_CATEGORIES = ["挂号", "检查", "检验", "药品", "治疗", "床位", "手术", "材料", "其他"]
APPT_SLOTS = ["08:00-08:30", "08:30-09:00", "09:00-09:30", "14:00-14:30", "14:30-15:00"]
NURSING_TYPES = ["daily", "medication", "vitals", "other"]
NURSING_TEXTS = [
    "生命体征平稳，血压正常", "遵医嘱给予口服药物并观察反应",
    "协助翻身拍背，预防压疮", "测量体温、脉搏、呼吸并记录",
    "巡视病房，患者主诉无明显不适", "宣教术后注意事项，做好心理疏导",
]
CONVERSATION_QUESTIONS = [
    "高血压患者日常饮食需要注意什么？", "最近总是咳嗽，是不是感冒了？",
    "糖尿病患者如何控制血糖？", "宝宝发烧该怎么护理？",
    "体检报告显示尿酸偏高怎么办？", "腰疼伴腿麻是什么问题？",
    "带状疱疹会传染吗？", "孕妇血糖偏高有什么影响？",
    "中暑了第一时间该怎么做？", "骨折后应该如何固定？",
]
CONVERSATION_ANSWERS = [
    "建议控制饮食、规律作息、戒烟限酒，遵医嘱规律服药；症状持续或加重请及时就医。",
    "结合知识库资料，普通感冒多为自限性，注意休息饮水；持续发热或呼吸困难请及时就医。",
    "建议饮食控制、规律运动并监测血糖，必要时在医生指导下用药，切勿自行停药。",
    "发热期间保证饮水、清淡饮食、充分休息，体温过高可遵医嘱退热，出现精神差请立即就医。",
    "建议低嘌呤饮食、多饮水、戒酒并控制体重，尿酸持续偏高应到内分泌或风湿科就诊。",
    "腰腿痛常见于腰椎间盘突出等，急性期应休息、避免负重，出现下肢无力需尽快就医。",
    "带状疱疹有一定的传染性，主要通过直接接触疱液传播，及时抗病毒治疗并注意隔离。",
    "妊娠期血糖偏高需医学营养治疗并监测血糖，控制不佳时在医生指导下使用胰岛素。",
    "应立即将患者移至阴凉处、物理降温并补充含盐水分，意识不清者立即拨打急救电话。",
    "应就地固定制动，开放性伤口覆盖止血后尽快送医，勿强行复位。",
]

# 源文档目录名（与用户约定 data/疾病名/<公有>|<私有> 一致）
PUBLIC_DIR = "公有"
PRIVATE_DIR = "私有"


def _ensure_user(username: str, password: str, role: str, display_name: str = "") -> bool:
    """创建用户（若已存在则跳过），返回是否新建。"""
    conn = get_conn()
    exists = conn.execute("SELECT 1 FROM users WHERE username = ?", (username,)).fetchone()
    if exists:
        return False
    auth_service.create_user(username, password, role, display_name)
    return True


def _create_kb_if_missing(name: str, owner_id, visibility: str = "private",
                          description: str = "") -> tuple[int, bool]:
    """按 (名称, owner) 幂等创建知识库，返回 (id, 是否新建)。"""
    conn = get_conn()
    if owner_id is None:
        row = conn.execute(
            "SELECT id FROM knowledge_bases WHERE name=? AND owner_id IS NULL", (name,)
        ).fetchone()
    else:
        row = conn.execute(
            "SELECT id FROM knowledge_bases WHERE name=? AND owner_id=?", (name, owner_id)
        ).fetchone()
    if row:
        return row["id"], False
    cur = conn.execute(
        "INSERT INTO knowledge_bases (owner_id, name, description, visibility) VALUES (?,?,?,?)",
        (owner_id, name, description, visibility),
    )
    conn.commit()
    return cur.lastrowid, True


def _add_doc_if_missing(kb_id: int, kb_name: str, filename: str, content: str,
                        visibility: str, cfg) -> None:
    """幂等写入文档文件并向量化入库（落在 uploads/<知识库>/公开|私有/ 目录）。

    幂等规则：
    - 同一 (kb_id, filename) 已存在且 status='ready' -> 直接跳过（避免重复向量化）。
    - 不存在 -> 新建文档记录并向量化。
    - 已存在但 status='failed'/'processing'（例如先前 Milvus 不可用、远程 embedding 失败）
      -> 清理可能残留的旧向量后重新向量化，确保重部署后向量库不为空、问答有答案。
    """
    conn = get_conn()
    row = conn.execute(
        "SELECT id, status, file_path FROM documents WHERE kb_id=? AND filename=?",
        (kb_id, filename),
    ).fetchone()
    if row and row["status"] == "ready":
        return
    # 上传落盘子目录与运行时上传（kb_service）保持一致：公开 / 私有
    from services.kb_service import PRIVATE_DIR as KB_PRIVATE_DIR, PUBLIC_DIR as KB_PUBLIC_DIR

    sub_dir = KB_PUBLIC_DIR if visibility == "public" else KB_PRIVATE_DIR
    folder = safe_folder_name(kb_name, str(kb_id))
    rel_dir = os.path.join(cfg["UPLOAD_DIR"], folder, sub_dir)
    os.makedirs(rel_dir, exist_ok=True)
    if row is None:
        rel_path = os.path.join(folder, sub_dir, f"seed_{uuid.uuid4().hex[:8]}_{filename}")
        abs_path = os.path.join(cfg["UPLOAD_DIR"], rel_path)
        with open(abs_path, "w", encoding="utf-8") as f:
            f.write(content)
        cur = conn.execute(
            """INSERT INTO documents (kb_id, filename, file_path, file_type, visibility, status)
               VALUES (?, ?, ?, ?, ?, 'processing')""",
            (kb_id, filename, rel_path, os.path.splitext(filename)[1].lstrip("."), visibility),
        )
        conn.commit()
        doc_id = cur.lastrowid
    else:
        doc_id = row["id"]
        abs_path = os.path.join(cfg["UPLOAD_DIR"], row["file_path"])
        # 文件可能被清理，内容仍在 content 中，补回即可
        if not os.path.exists(abs_path):
            with open(abs_path, "w", encoding="utf-8") as f:
                f.write(content)
    # 清理可能残留的旧向量（Milvus 部分写入 / NumpyStore 旧切片），避免重复
    try:
        from extensions import get_vector_store
        get_vector_store(cfg).delete_doc(kb_id, doc_id)
    except Exception:  # noqa: BLE001 向量库尚未就绪时跳过清理，重试时 process_document 会覆盖
        pass
    process_document(doc_id, kb_id, abs_path, filename, visibility)


# ---------- 用户 ----------
def _seed_users() -> None:
    conn = get_conn()
    for role, label in ROLE_CN.items():
        _ensure_user(f"{role}demo", DEMO_PASSWORD, role, f"演示{label}")

    count = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    seq = 1
    while count < USERS_TARGET:
        for role in ("patient", "doctor", "nurse", "public", "admin"):
            if count >= USERS_TARGET:
                break
            if _ensure_user(f"{role}_{seq:02d}", DEMO_PASSWORD, role, f"{ROLE_CN[role]}示例{seq}"):
                count += 1
        seq += 1


# ---------- 知识库与文档 ----------
def _seed_disease_kbs(cfg) -> None:
    """12 个疾病知识库：公开 10 篇 + 私有 10 篇文档。"""
    for name, description in DISEASE_KBS.items():
        kb_id, _ = _create_kb_if_missing(name, None, "public", description)
        src_dir = os.path.join(KB_DOCS_SRC_DIR, name)
        for sub_dir, visibility in ((PUBLIC_DIR, "public"), (PRIVATE_DIR, "private")):
            src_sub = os.path.join(src_dir, sub_dir)
            if not os.path.isdir(src_sub):
                continue
            files = sorted(
                f for f in os.listdir(src_sub)
                if f.lower().endswith((".md", ".txt"))
            )
            for fname in files:
                with open(os.path.join(src_sub, fname), encoding="utf-8") as f:
                    content = f.read()
                _add_doc_if_missing(kb_id, name, fname, content, visibility, cfg)


def _seed_filler_kbs() -> None:
    """补足知识库到 50 个（12 个疾病库 + 医生私有库）。"""
    conn = get_conn()
    count = conn.execute("SELECT COUNT(*) FROM knowledge_bases").fetchone()[0]
    doctors = conn.execute(
        "SELECT id, display_name FROM users WHERE role='doctor' ORDER BY id"
    ).fetchall()
    if not doctors:
        return
    seq = 1
    while count < KBS_TARGET:
        owner = doctors[(seq - 1) % len(doctors)]
        name = f"{owner['display_name']}的临床资料{seq:03d}"
        _, created = _create_kb_if_missing(name, owner["id"], "private", "医生私有临床知识库")
        if created:
            count += 1
        seq += 1


# ---------- 会话 / 消息 / 引用 ----------
def _seed_conversations() -> None:
    conn = get_conn()
    count = conn.execute("SELECT COUNT(*) FROM conversations").fetchone()[0]
    if count >= CONVERSATIONS_TARGET:
        return
    users = conn.execute(
        "SELECT id FROM users WHERE role IN ('patient','public') ORDER BY id"
    ).fetchall()
    kbs = conn.execute(
        "SELECT id FROM knowledge_bases WHERE visibility='public' ORDER BY id"
    ).fetchall()
    if not users or not kbs:
        return
    need = CONVERSATIONS_TARGET - count
    for i in range(need):
        user = users[i % len(users)]
        kb_id = kbs[i % len(kbs)]["id"]
        q = CONVERSATION_QUESTIONS[i % len(CONVERSATION_QUESTIONS)]
        a = CONVERSATION_ANSWERS[i % len(CONVERSATION_ANSWERS)]
        cid = uuid.uuid4().hex
        conn.execute(
            "INSERT INTO conversations (id, user_id, kb_id, title) VALUES (?,?,?,?)",
            (cid, user["id"], kb_id, q[:30]),
        )
        conn.execute(
            "INSERT INTO messages (conversation_id, role, content) VALUES (?, 'user', ?)", (cid, q)
        )
        conn.execute(
            "INSERT INTO messages (conversation_id, role, content) VALUES (?, 'assistant', ?)", (cid, a)
        )
    conn.commit()


def _seed_citations() -> None:
    conn = get_conn()
    count = conn.execute("SELECT COUNT(*) FROM citations").fetchone()[0]
    if count >= CITATIONS_TARGET:
        return
    docs = conn.execute("SELECT id, filename FROM documents ORDER BY id").fetchall()
    msgs = conn.execute(
        "SELECT id, content FROM messages WHERE role='assistant' ORDER BY id"
    ).fetchall()
    if not docs or not msgs:
        return
    need = CITATIONS_TARGET - count
    for i in range(need):
        msg = msgs[i % len(msgs)]
        doc = docs[i % len(docs)]
        source = (doc["filename"] + "：" + msg["content"])[:200]
        conn.execute(
            """INSERT INTO citations (message_id, document_id, chunk_index, source_text, title, similarity)
               VALUES (?, ?, 0, ?, ?, 0.85)""",
            (msg["id"], doc["id"], source, doc["filename"]),
        )
    conn.commit()


# ---------- 患者健康档案 / 医护数据 ----------
def _seed_medical_volume() -> None:
    conn = get_conn()
    patients = conn.execute("SELECT id FROM users WHERE role='patient' ORDER BY id").fetchall()
    doctors = conn.execute("SELECT id FROM users WHERE role='doctor' ORDER BY id").fetchall()
    nurses = conn.execute("SELECT id FROM users WHERE role='nurse' ORDER BY id").fetchall()
    publics = conn.execute("SELECT id FROM users WHERE role='public' ORDER BY id").fetchall()
    if not patients:
        return

    def top_up(table: str, target: int, gen) -> None:
        c = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        if c >= target:
            return
        for i in range(target - c):
            gen(i, c + i)

    def gen_hosp(i: int, n: int) -> None:
        p = patients[i % len(patients)]
        doctor = doctors[i % len(doctors)] if doctors else None
        admit = date.today() - timedelta(days=i % 60)
        status = "in_hospital" if i % 3 else "discharged"
        discharge = (admit + timedelta(days=(i % 14) + 2)).isoformat() if status == "discharged" else None
        conn.execute(
            """INSERT INTO hospitalizations
               (patient_id, admit_date, discharge_date, department, ward, bed_no, diagnosis, doctor_id, status,
                total_cost)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (p["id"], admit.isoformat(), discharge, DEPARTMENTS[i % len(DEPARTMENTS)],
             f"{i % 3 + 3}病区", f"{i % 20 + 1}床", DIAGNOSES[i % len(DIAGNOSES)],
             doctor["id"] if doctor else None, status, round(((i % 30) + 5) * 100, 2)),
        )

    def gen_bill(i: int, n: int) -> None:
        p = patients[i % len(patients)]
        cat = BILL_CATEGORIES[i % len(BILL_CATEGORIES)]
        bill_no = f"BLL{date.today().strftime('%Y%m%d')}{n:05d}"
        conn.execute(
            """INSERT INTO bills (patient_id, bill_no, category, description, amount, status, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (p["id"], bill_no, cat, f"{cat}费用", round(((i % 40) + 1) * 20, 2),
             "paid" if i % 2 else "unpaid",
             (date.today() - timedelta(days=i % 30)).isoformat()),
        )

    def gen_appt(i: int, n: int) -> None:
        pool = list(patients) + list(publics)
        p = pool[i % len(pool)]
        doctor = doctors[i % len(doctors)] if doctors else None
        status = ["booked", "confirmed", "visited", "cancelled"][i % 4]
        conn.execute(
            """INSERT INTO appointments (patient_id, doctor_id, department, date, time_slot, symptom, fee, status)
               VALUES (?, ?, ?, ?, ?, ?, 20, ?)""",
            (p["id"], doctor["id"] if doctor else None, DEPARTMENTS[i % len(DEPARTMENTS)],
             (date.today() + timedelta(days=i % 7)).isoformat(), APPT_SLOTS[i % len(APPT_SLOTS)],
             DIAGNOSES[i % len(DIAGNOSES)], status),
        )

    def gen_nursing(i: int, n: int) -> None:
        p = patients[i % len(patients)]
        nurse = nurses[i % len(nurses)] if nurses else None
        conn.execute(
            """INSERT INTO nursing_records (patient_id, nurse_id, content, record_type, recorded_at)
               VALUES (?, ?, ?, ?, ?)""",
            (p["id"], nurse["id"] if nurse else None, NURSING_TEXTS[i % len(NURSING_TEXTS)],
             NURSING_TYPES[i % len(NURSING_TYPES)],
             (date.today() - timedelta(days=i % 15)).isoformat()),
        )

    def gen_sched(i: int, n: int) -> None:
        staff = list(doctors) + list(nurses)
        if not staff:
            return
        s = staff[i % len(staff)]
        conn.execute(
            """INSERT INTO schedules (staff_id, work_date, shift, department, status)
               VALUES (?, ?, ?, ?, 'on_duty')""",
            (s["id"], (date.today() + timedelta(days=i % 30)).isoformat(),
             SHIFTS[i % len(SHIFTS)], DEPARTMENTS[i % len(DEPARTMENTS)]),
        )

    top_up("hospitalizations", HOSPITALIZATIONS_TARGET, gen_hosp)
    top_up("bills", BILLS_TARGET, gen_bill)
    top_up("appointments", APPOINTMENTS_TARGET, gen_appt)
    top_up("nursing_records", NURSING_TARGET, gen_nursing)
    top_up("schedules", SCHEDULES_TARGET, gen_sched)
    conn.commit()


def _print_summary() -> None:
    conn = get_conn()
    tables = [
        "users", "knowledge_bases", "documents", "conversations", "messages", "citations",
        "hospitalizations", "bills", "appointments", "nursing_records", "schedules",
    ]
    print("[seed] 各表数据量：")
    for t in tables:
        c = conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
        print(f"  - {t}: {c}")
    pub = conn.execute(
        "SELECT COUNT(*) FROM documents WHERE visibility='public'"
    ).fetchone()[0]
    pri = conn.execute(
        "SELECT COUNT(*) FROM documents WHERE visibility='private'"
    ).fetchone()[0]
    print(f"  - 文档可见性：公开 {pub} / 私有 {pri}")


def seed_all(app, force_kb_docs: bool | None = None) -> None:
    """演示数据播种（幂等）。

    force_kb_docs:
      - None  -> 由配置 SEED_KB_DOCS 决定（默认 False，不播种知识库文档）；
      - True  -> 强制播种知识库文档（示例疾病文档）；
      - False -> 强制不播种知识库文档。
    默认不播种知识库文档，使首启后知识库保持为空，由管理员/医生首次登录后清零并自行上传。
    """
    cfg = app.config
    init_schema(cfg)
    with app.app_context():
        _seed_users()
        seed_kb = force_kb_docs if force_kb_docs is not None else bool(cfg.get("SEED_KB_DOCS", False))
        if seed_kb:
            _seed_disease_kbs(cfg)
            _seed_filler_kbs()
        _seed_conversations()
        _seed_citations()
        _seed_medical_volume()
        _print_summary()
        print(
            "[seed] 演示账号（密码均为 demo123）：patientdemo / doctordemo / nursedemo / publicdemo / admindemo"
        )
        if not seed_kb:
            print("[seed] 知识库文档未自动播种（SEED_KB_DOCS=0）。"
                  "管理员/医生首次登录后知识库将清零，可手动上传，或运行 `python seed.py --kb-docs` 一键导入示例文档。")


if __name__ == "__main__":
    import argparse

    from app import app

    parser = argparse.ArgumentParser(description="医智助手演示数据播种")
    parser.add_argument("--kb-docs", action="store_true",
                        help="强制播种知识库示例文档（忽略 SEED_KB_DOCS 配置）")
    args = parser.parse_args()

    with app.app_context():
        seed_all(app, force_kb_docs=args.kb_docs if args.kb_docs else None)
