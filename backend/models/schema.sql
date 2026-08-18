-- 医智助手业务库 Schema（SQLite，数据库文件：medical-assistant-master.db）

CREATE TABLE IF NOT EXISTS users (
  id            INTEGER PRIMARY KEY AUTOINCREMENT,
  username      TEXT UNIQUE NOT NULL,
  password_hash TEXT NOT NULL,
  role          TEXT NOT NULL CHECK (role IN ('patient','doctor','nurse','public','admin')),
  display_name  TEXT,
  created_at    TEXT NOT NULL DEFAULT (datetime('now','localtime'))
);

CREATE TABLE IF NOT EXISTS knowledge_bases (
  id          INTEGER PRIMARY KEY AUTOINCREMENT,
  owner_id    INTEGER REFERENCES users(id) ON DELETE CASCADE,   -- NULL = 平台公共知识库
  name        TEXT NOT NULL,
  description TEXT,
  visibility  TEXT NOT NULL DEFAULT 'private' CHECK (visibility IN ('private','public')),
  created_at  TEXT NOT NULL DEFAULT (datetime('now','localtime'))
);

CREATE TABLE IF NOT EXISTS documents (
  id          INTEGER PRIMARY KEY AUTOINCREMENT,
  kb_id       INTEGER NOT NULL REFERENCES knowledge_bases(id) ON DELETE CASCADE,
  filename    TEXT NOT NULL,
  file_path   TEXT NOT NULL,               -- UPLOAD_DIR 下的相对路径
  file_type   TEXT NOT NULL,               -- txt | md | pdf | docx | pptx
  visibility  TEXT NOT NULL DEFAULT 'public' CHECK (visibility IN ('public','private')),
  chunk_count INTEGER NOT NULL DEFAULT 0,
  status      TEXT NOT NULL DEFAULT 'processing' CHECK (status IN ('processing','ready','failed')),
  error       TEXT,
  created_at  TEXT NOT NULL DEFAULT (datetime('now','localtime'))
);

CREATE TABLE IF NOT EXISTS conversations (
  id          TEXT PRIMARY KEY,            -- uuid4 hex
  user_id     INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  kb_id       INTEGER REFERENCES knowledge_bases(id) ON DELETE SET NULL,
  title       TEXT NOT NULL,
  created_at  TEXT NOT NULL DEFAULT (datetime('now','localtime')),
  updated_at  TEXT NOT NULL DEFAULT (datetime('now','localtime'))
);

CREATE TABLE IF NOT EXISTS messages (
  id              INTEGER PRIMARY KEY AUTOINCREMENT,
  conversation_id TEXT NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
  role            TEXT NOT NULL CHECK (role IN ('user','assistant')),
  content         TEXT NOT NULL,
  created_at      TEXT NOT NULL DEFAULT (datetime('now','localtime'))
);
CREATE INDEX IF NOT EXISTS idx_messages_conv ON messages(conversation_id);

CREATE TABLE IF NOT EXISTS citations (
  id           INTEGER PRIMARY KEY AUTOINCREMENT,
  message_id   INTEGER NOT NULL REFERENCES messages(id) ON DELETE CASCADE,
  document_id  INTEGER NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
  chunk_index  INTEGER NOT NULL,
  source_text  TEXT,
  title        TEXT,                       -- 冗余文档名，便于展示
  similarity   REAL
);
CREATE INDEX IF NOT EXISTS idx_citations_msg ON citations(message_id);

-- ===== 患者健康档案 / 医护工作数据 =====

-- 住院信息
CREATE TABLE IF NOT EXISTS hospitalizations (
  id             INTEGER PRIMARY KEY AUTOINCREMENT,
  patient_id     INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  admit_date     TEXT NOT NULL,
  discharge_date TEXT,
  department     TEXT NOT NULL,
  ward           TEXT,
  bed_no         TEXT,
  diagnosis      TEXT,
  doctor_id      INTEGER REFERENCES users(id) ON DELETE SET NULL,
  status         TEXT NOT NULL DEFAULT 'in_hospital' CHECK (status IN ('in_hospital','discharged')),
  total_cost     REAL NOT NULL DEFAULT 0,
  created_at     TEXT NOT NULL DEFAULT (datetime('now','localtime'))
);
CREATE INDEX IF NOT EXISTS idx_hosp_patient ON hospitalizations(patient_id);

-- 消费明细（挂号/检查/检验/药品/住院等）
CREATE TABLE IF NOT EXISTS bills (
  id          INTEGER PRIMARY KEY AUTOINCREMENT,
  patient_id  INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  bill_no     TEXT UNIQUE NOT NULL,
  category    TEXT NOT NULL,               -- 挂号/检查/检验/药品/住院/门诊
  description TEXT,
  amount      REAL NOT NULL DEFAULT 0,
  status      TEXT NOT NULL DEFAULT 'unpaid' CHECK (status IN ('paid','unpaid')),
  created_at  TEXT NOT NULL DEFAULT (datetime('now','localtime'))
);
CREATE INDEX IF NOT EXISTS idx_bills_patient ON bills(patient_id);

-- 门诊预约挂号
CREATE TABLE IF NOT EXISTS appointments (
  id          INTEGER PRIMARY KEY AUTOINCREMENT,
  patient_id  INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  doctor_id   INTEGER REFERENCES users(id) ON DELETE SET NULL,
  department  TEXT NOT NULL,
  date        TEXT NOT NULL,
  time_slot   TEXT NOT NULL,               -- 如 08:00-08:30
  symptom     TEXT,                        -- 主诉/症状
  fee         REAL NOT NULL DEFAULT 0,
  status      TEXT NOT NULL DEFAULT 'booked' CHECK (status IN ('booked','confirmed','visited','cancelled')),
  created_at  TEXT NOT NULL DEFAULT (datetime('now','localtime'))
);
CREATE INDEX IF NOT EXISTS idx_appt_patient ON appointments(patient_id);

-- 护理记录
CREATE TABLE IF NOT EXISTS nursing_records (
  id          INTEGER PRIMARY KEY AUTOINCREMENT,
  patient_id  INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  nurse_id    INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  record_type TEXT NOT NULL DEFAULT 'daily' CHECK (record_type IN ('daily','medication','vitals','other')),
  content     TEXT NOT NULL,
  recorded_at TEXT NOT NULL DEFAULT (datetime('now','localtime'))
);
CREATE INDEX IF NOT EXISTS idx_nursing_patient ON nursing_records(patient_id);

-- 医护排班
CREATE TABLE IF NOT EXISTS schedules (
  id          INTEGER PRIMARY KEY AUTOINCREMENT,
  staff_id    INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  work_date   TEXT NOT NULL,
  shift       TEXT NOT NULL,               -- 白班/夜班/值班
  department  TEXT,
  status      TEXT NOT NULL DEFAULT 'on_duty' CHECK (status IN ('on_duty','off','leave')),
  created_at  TEXT NOT NULL DEFAULT (datetime('now','localtime'))
);
CREATE INDEX IF NOT EXISTS idx_schedule_staff ON schedules(staff_id);
