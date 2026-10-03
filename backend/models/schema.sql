-- 医智助手业务库 Schema · SQLite 版本
-- 供 DB_TYPE=sqlite 时使用（零外部依赖，适合本地演示 / 单元测试）。
-- 字段与 schema_mysql.sql 一一对应，由 backend/utils/db.py 的 init_schema() 幂等执行。
--
-- 说明：
--   1. 不使用外键约束，引用完整性由应用层保证（与 MySQL 版保持一致）；
--   2. MySQL 的 ON UPDATE CURRENT_TIMESTAMP 在 SQLite 中不受支持，
--      conversations.updated_at / bm25_terms.updated_at 由应用层显式写入；
--   3. init_schema() 会按分号切分执行，因此本文件内不得出现语句内部的分号。

CREATE TABLE IF NOT EXISTS users (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    username         VARCHAR(32)  NOT NULL UNIQUE,
    password_hash    VARCHAR(255) NOT NULL,
    role             VARCHAR(16)  NOT NULL,
    display_name     VARCHAR(64)  NULL,
    first_login_done INTEGER      NOT NULL DEFAULT 0,
    created_at       DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_users_role ON users(role);

CREATE TABLE IF NOT EXISTS knowledge_bases (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    owner_id    INTEGER      NULL,
    name        VARCHAR(128) NOT NULL,
    description VARCHAR(512) NULL,
    visibility  VARCHAR(16)  NOT NULL DEFAULT 'private',
    created_at  DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_kb_owner ON knowledge_bases(owner_id);
CREATE INDEX IF NOT EXISTS idx_kb_visibility ON knowledge_bases(visibility);

CREATE TABLE IF NOT EXISTS documents (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    kb_id         INTEGER      NOT NULL,
    filename      VARCHAR(255) NOT NULL,
    file_path     VARCHAR(512) NOT NULL,
    file_type     VARCHAR(16)  NOT NULL,
    visibility    VARCHAR(16)  NOT NULL DEFAULT 'public',
    chunk_count   INTEGER      NOT NULL DEFAULT 0,
    status        VARCHAR(16)  NOT NULL DEFAULT 'processing',
    review_status VARCHAR(16)  NOT NULL DEFAULT 'pending',
    reviewer_id   INTEGER      NULL,
    reviewed_at   DATETIME     NULL,
    review_note   VARCHAR(512) NULL,
    error         VARCHAR(512) NULL,
    indexed_at    DATETIME     NULL,
    created_at    DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_doc_kb ON documents(kb_id);
CREATE INDEX IF NOT EXISTS idx_doc_visibility ON documents(visibility);
CREATE INDEX IF NOT EXISTS idx_doc_kb_status ON documents(kb_id, status);

CREATE TABLE IF NOT EXISTS chunks (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    doc_id      INTEGER      NOT NULL,
    kb_id       INTEGER      NOT NULL,
    parent_id   INTEGER      NULL,
    chunk_index INTEGER      NOT NULL,
    heading     VARCHAR(512) NULL,
    text        TEXT         NOT NULL,
    token_count INTEGER      NOT NULL DEFAULT 0,
    created_at  DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_chunk_doc ON chunks(doc_id);
CREATE INDEX IF NOT EXISTS idx_chunk_kb ON chunks(kb_id);
CREATE INDEX IF NOT EXISTS idx_chunk_parent ON chunks(parent_id);

CREATE TABLE IF NOT EXISTS sub_chunks (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    chunk_id    INTEGER      NOT NULL,
    doc_id      INTEGER      NOT NULL,
    kb_id       INTEGER      NOT NULL,
    sub_index   INTEGER      NOT NULL,
    text        TEXT         NOT NULL,
    vector_path VARCHAR(512) NULL,
    bm25_terms  TEXT         NULL,
    token_count INTEGER      NOT NULL DEFAULT 0,
    created_at  DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_sub_chunk ON sub_chunks(chunk_id);
CREATE INDEX IF NOT EXISTS idx_sub_doc ON sub_chunks(doc_id);
CREATE INDEX IF NOT EXISTS idx_sub_kb ON sub_chunks(kb_id);

CREATE TABLE IF NOT EXISTS bm25_terms (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    kb_id      INTEGER      NOT NULL,
    term       VARCHAR(128) NOT NULL,
    df         INTEGER      NOT NULL DEFAULT 0,
    cf         INTEGER      NOT NULL DEFAULT 0,
    updated_at DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE UNIQUE INDEX IF NOT EXISTS uk_bm25_kb_term ON bm25_terms(kb_id, term);
CREATE INDEX IF NOT EXISTS idx_bm25_kb ON bm25_terms(kb_id);

CREATE TABLE IF NOT EXISTS chunk_vectors (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    sub_chunk_id INTEGER      NOT NULL UNIQUE,
    doc_id       INTEGER      NOT NULL,
    kb_id        INTEGER      NOT NULL,
    store_type   VARCHAR(32)  NOT NULL DEFAULT 'numpy',
    store_key    VARCHAR(128) NOT NULL,
    created_at   DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_vec_doc ON chunk_vectors(doc_id);
CREATE INDEX IF NOT EXISTS idx_vec_kb ON chunk_vectors(kb_id);

CREATE TABLE IF NOT EXISTS conversations (
    id         VARCHAR(32) PRIMARY KEY,
    user_id    INTEGER      NOT NULL,
    kb_id      INTEGER      NULL,
    title      VARCHAR(128) NOT NULL,
    created_at DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_conv_user ON conversations(user_id);
CREATE INDEX IF NOT EXISTS idx_conv_kb ON conversations(kb_id);

CREATE TABLE IF NOT EXISTS messages (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    conversation_id VARCHAR(32) NOT NULL,
    role            VARCHAR(16) NOT NULL,
    content         TEXT        NOT NULL,
    review_status   VARCHAR(16) NOT NULL DEFAULT 'pending',
    reviewer_id     INTEGER     NULL,
    reviewed_at     DATETIME    NULL,
    review_note     VARCHAR(512) NULL,
    created_at      DATETIME    NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_messages_conv ON messages(conversation_id);

CREATE TABLE IF NOT EXISTS citations (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    message_id  INTEGER      NOT NULL,
    document_id INTEGER      NOT NULL,
    chunk_index INTEGER      NOT NULL,
    source_text TEXT         NULL,
    title       VARCHAR(255) NULL,
    similarity  REAL         NULL
);
CREATE INDEX IF NOT EXISTS idx_citations_msg ON citations(message_id);
CREATE INDEX IF NOT EXISTS idx_citations_doc ON citations(document_id);

CREATE TABLE IF NOT EXISTS hospitalizations (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    patient_id     INTEGER      NOT NULL,
    admit_date     VARCHAR(20)  NOT NULL,
    discharge_date VARCHAR(20)  NULL,
    department     VARCHAR(64)  NOT NULL,
    ward           VARCHAR(64)  NULL,
    bed_no         VARCHAR(32)  NULL,
    diagnosis      VARCHAR(255) NULL,
    doctor_id      INTEGER      NULL,
    status         VARCHAR(16)  NOT NULL DEFAULT 'in_hospital',
    total_cost     REAL         NOT NULL DEFAULT 0,
    created_at     DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_hosp_patient ON hospitalizations(patient_id);

CREATE TABLE IF NOT EXISTS bills (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    patient_id  INTEGER      NOT NULL,
    bill_no     VARCHAR(64)  NOT NULL UNIQUE,
    category    VARCHAR(32)  NOT NULL,
    description VARCHAR(255) NULL,
    amount      REAL         NOT NULL DEFAULT 0,
    status      VARCHAR(16)  NOT NULL DEFAULT 'unpaid',
    created_at  DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_bills_patient ON bills(patient_id);

CREATE TABLE IF NOT EXISTS appointments (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    patient_id INTEGER      NOT NULL,
    doctor_id  INTEGER      NULL,
    department VARCHAR(64)  NOT NULL,
    date       VARCHAR(20)  NOT NULL,
    time_slot  VARCHAR(32)  NOT NULL,
    symptom    VARCHAR(255) NULL,
    fee        REAL         NOT NULL DEFAULT 0,
    status     VARCHAR(16)  NOT NULL DEFAULT 'booked',
    created_at DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_appt_patient ON appointments(patient_id);

CREATE TABLE IF NOT EXISTS nursing_records (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    patient_id  INTEGER      NOT NULL,
    nurse_id    INTEGER      NOT NULL,
    record_type VARCHAR(16)  NOT NULL DEFAULT 'daily',
    content     TEXT         NOT NULL,
    recorded_at DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_nursing_patient ON nursing_records(patient_id);

-- 体征 / 检验指标表（结构化，供个性化问答注入「近期血糖」等临床读数）
-- metric 例：blood_glucose（血糖）；value+unit 组合表达如 8.6 mmol/L。
CREATE TABLE IF NOT EXISTS health_metrics (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    patient_id  INTEGER      NOT NULL,
    metric      VARCHAR(32)  NOT NULL,
    value       REAL         NOT NULL,
    unit        VARCHAR(16)  NOT NULL,
    context     VARCHAR(32)  NULL,
    recorded_at DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_hm_patient_metric ON health_metrics(patient_id, metric);

CREATE TABLE IF NOT EXISTS schedules (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    staff_id   INTEGER      NOT NULL,
    work_date  VARCHAR(20)  NOT NULL,
    shift      VARCHAR(16)  NOT NULL,
    department VARCHAR(64)  NULL,
    remark     VARCHAR(255) NULL,
    status     VARCHAR(16)  NOT NULL DEFAULT 'on_duty',
    created_at DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_schedule_staff ON schedules(staff_id);

CREATE TABLE IF NOT EXISTS audit_logs (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    actor_id    INTEGER      NULL,
    actor_role  VARCHAR(32)  NULL,
    action      VARCHAR(64)  NOT NULL,
    target_type VARCHAR(32)  NULL,
    target_id   VARCHAR(64)  NULL,
    detail      TEXT         NULL,
    ip          VARCHAR(64)  NULL,
    created_at  DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_audit_action ON audit_logs(action);
CREATE INDEX IF NOT EXISTS idx_audit_target ON audit_logs(target_type, target_id);
CREATE INDEX IF NOT EXISTS idx_audit_created ON audit_logs(created_at);
