-- 医智助手 · SQLite 兜底建表语句（幂等）
-- 用于本机无 MySQL 时的本地运行（DB_TYPE=sqlite）。

CREATE TABLE IF NOT EXISTS users (
  id            INTEGER PRIMARY KEY AUTOINCREMENT,
  username      TEXT NOT NULL UNIQUE,
  password_hash TEXT NOT NULL,
  role          TEXT NOT NULL,
  display_name  TEXT,
  created_at    TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_users_role ON users(role);

CREATE TABLE IF NOT EXISTS knowledge_bases (
  id          INTEGER PRIMARY KEY AUTOINCREMENT,
  owner_id    INTEGER,
  name        TEXT NOT NULL,
  description TEXT,
  visibility  TEXT NOT NULL DEFAULT 'private',
  created_at  TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_kb_owner ON knowledge_bases(owner_id);
CREATE INDEX IF NOT EXISTS idx_kb_visibility ON knowledge_bases(visibility);

CREATE TABLE IF NOT EXISTS documents (
  id          INTEGER PRIMARY KEY AUTOINCREMENT,
  kb_id       INTEGER NOT NULL,
  filename    TEXT NOT NULL,
  file_path   TEXT NOT NULL,
  file_type   TEXT NOT NULL,
  visibility  TEXT NOT NULL DEFAULT 'public',
  chunk_count INTEGER NOT NULL DEFAULT 0,
  status      TEXT NOT NULL DEFAULT 'processing',
  error       TEXT,
  created_at  TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_doc_kb ON documents(kb_id);
CREATE INDEX IF NOT EXISTS idx_doc_visibility ON documents(visibility);

CREATE TABLE IF NOT EXISTS conversations (
  id          TEXT PRIMARY KEY,
  user_id     INTEGER NOT NULL,
  kb_id       INTEGER,
  title       TEXT NOT NULL,
  created_at  TEXT NOT NULL DEFAULT (datetime('now')),
  updated_at  TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_conv_user ON conversations(user_id);
CREATE INDEX IF NOT EXISTS idx_conv_kb ON conversations(kb_id);

CREATE TABLE IF NOT EXISTS messages (
  id              INTEGER PRIMARY KEY AUTOINCREMENT,
  conversation_id TEXT NOT NULL,
  role            TEXT NOT NULL,
  content         TEXT NOT NULL,
  created_at      TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_messages_conv ON messages(conversation_id);

CREATE TABLE IF NOT EXISTS citations (
  id           INTEGER PRIMARY KEY AUTOINCREMENT,
  message_id   INTEGER NOT NULL,
  document_id  INTEGER NOT NULL,
  chunk_index  INTEGER NOT NULL,
  source_text  TEXT,
  title        TEXT,
  similarity   REAL
);
CREATE INDEX IF NOT EXISTS idx_citations_msg ON citations(message_id);

CREATE TABLE IF NOT EXISTS hospitalizations (
  id             INTEGER PRIMARY KEY AUTOINCREMENT,
  patient_id     INTEGER NOT NULL,
  admit_date     TEXT NOT NULL,
  discharge_date TEXT,
  department     TEXT NOT NULL,
  ward           TEXT,
  bed_no         TEXT,
  diagnosis      TEXT,
  doctor_id      INTEGER,
  status         TEXT NOT NULL DEFAULT 'in_hospital',
  total_cost     REAL NOT NULL DEFAULT 0,
  created_at     TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_hosp_patient ON hospitalizations(patient_id);

CREATE TABLE IF NOT EXISTS bills (
  id          INTEGER PRIMARY KEY AUTOINCREMENT,
  patient_id  INTEGER NOT NULL,
  bill_no     TEXT NOT NULL UNIQUE,
  category    TEXT NOT NULL,
  description TEXT,
  amount      REAL NOT NULL DEFAULT 0,
  status      TEXT NOT NULL DEFAULT 'unpaid',
  created_at  TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_bills_patient ON bills(patient_id);

CREATE TABLE IF NOT EXISTS appointments (
  id         INTEGER PRIMARY KEY AUTOINCREMENT,
  patient_id INTEGER NOT NULL,
  doctor_id  INTEGER,
  department TEXT NOT NULL,
  date       TEXT NOT NULL,
  time_slot  TEXT NOT NULL,
  symptom    TEXT,
  fee        REAL NOT NULL DEFAULT 0,
  status     TEXT NOT NULL DEFAULT 'booked',
  created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_appt_patient ON appointments(patient_id);

CREATE TABLE IF NOT EXISTS nursing_records (
  id          INTEGER PRIMARY KEY AUTOINCREMENT,
  patient_id  INTEGER NOT NULL,
  nurse_id    INTEGER NOT NULL,
  record_type TEXT NOT NULL DEFAULT 'daily',
  content     TEXT NOT NULL,
  recorded_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_nursing_patient ON nursing_records(patient_id);

CREATE TABLE IF NOT EXISTS schedules (
  id         INTEGER PRIMARY KEY AUTOINCREMENT,
  staff_id   INTEGER NOT NULL,
  work_date  TEXT NOT NULL,
  shift      TEXT NOT NULL,
  department TEXT,
  remark     TEXT,
  status     TEXT NOT NULL DEFAULT 'on_duty',
  created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_schedule_staff ON schedules(staff_id);
