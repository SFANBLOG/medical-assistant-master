-- 医智助手业务库 Schema MySQL版本（修复索引语法，兼容5.7&8.0）
CREATE DATABASE IF NOT EXISTS medical_assistant_master DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE medical_assistant_master;

CREATE TABLE IF NOT EXISTS users
(
    id            INT PRIMARY KEY AUTO_INCREMENT,
    username      VARCHAR(128) UNIQUE NOT NULL,
    password_hash TEXT                NOT NULL,
    role          VARCHAR(32)         NOT NULL CHECK (role IN ('patient', 'doctor', 'nurse', 'public', 'admin')),
    display_name  VARCHAR(128),
    created_at    DATETIME            NOT NULL DEFAULT CURRENT_TIMESTAMP
) ENGINE = InnoDB
  DEFAULT CHARSET = utf8mb4
  COLLATE = utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS knowledge_bases
(
    id          INT PRIMARY KEY AUTO_INCREMENT,
    owner_id    INT          NULL,
    name        VARCHAR(255) NOT NULL,
    description TEXT,
    visibility  VARCHAR(16)  NOT NULL DEFAULT 'private' CHECK (visibility IN ('private', 'public')),
    created_at  DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_kb_owner FOREIGN KEY (owner_id) REFERENCES users (id) ON DELETE CASCADE
) ENGINE = InnoDB
  DEFAULT CHARSET = utf8mb4
  COLLATE = utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS documents
(
    id          INT PRIMARY KEY AUTO_INCREMENT,
    kb_id       INT          NOT NULL,
    filename    VARCHAR(255) NOT NULL,
    file_path   VARCHAR(512) NOT NULL,
    file_type   VARCHAR(32)  NOT NULL,
    visibility  VARCHAR(16)  NOT NULL DEFAULT 'public' CHECK (visibility IN ('public', 'private')),
    chunk_count INT          NOT NULL DEFAULT 0,
    status      VARCHAR(16)  NOT NULL DEFAULT 'processing' CHECK (status IN ('processing', 'ready', 'failed')),
    error       TEXT,
    created_at  DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_doc_kb FOREIGN KEY (kb_id) REFERENCES knowledge_bases (id) ON DELETE CASCADE
) ENGINE = InnoDB
  DEFAULT CHARSET = utf8mb4
  COLLATE = utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS conversations
(
    id         VARCHAR(36) PRIMARY KEY,
    user_id    INT          NOT NULL,
    kb_id      INT          NULL,
    title      VARCHAR(255) NOT NULL,
    created_at DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    CONSTRAINT fk_conv_user FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE,
    CONSTRAINT fk_conv_kb FOREIGN KEY (kb_id) REFERENCES knowledge_bases (id) ON DELETE SET NULL
) ENGINE = InnoDB
  DEFAULT CHARSET = utf8mb4
  COLLATE = utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS messages
(
    id              INT PRIMARY KEY AUTO_INCREMENT,
    conversation_id VARCHAR(36) NOT NULL,
    role            VARCHAR(16) NOT NULL CHECK (role IN ('user', 'assistant')),
    content         TEXT        NOT NULL,
    created_at      DATETIME    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_msg_conv FOREIGN KEY (conversation_id) REFERENCES conversations (id) ON DELETE CASCADE
) ENGINE = InnoDB
  DEFAULT CHARSET = utf8mb4
  COLLATE = utf8mb4_unicode_ci;
CREATE INDEX idx_messages_conv ON messages (conversation_id);

CREATE TABLE IF NOT EXISTS citations
(
    id          INT PRIMARY KEY AUTO_INCREMENT,
    message_id  INT NOT NULL,
    document_id INT NOT NULL,
    chunk_index INT NOT NULL,
    source_text TEXT,
    title       VARCHAR(255),
    similarity  DOUBLE,
    CONSTRAINT fk_cite_msg FOREIGN KEY (message_id) REFERENCES messages (id) ON DELETE CASCADE,
    CONSTRAINT fk_cite_doc FOREIGN KEY (document_id) REFERENCES documents (id) ON DELETE CASCADE
) ENGINE = InnoDB
  DEFAULT CHARSET = utf8mb4
  COLLATE = utf8mb4_unicode_ci;
CREATE INDEX idx_citations_msg ON citations (message_id);

-- ===== 患者健康档案 / 医护工作数据 =====

-- 住院信息
CREATE TABLE IF NOT EXISTS hospitalizations
(
    id             INT PRIMARY KEY AUTO_INCREMENT,
    patient_id     INT            NOT NULL,
    admit_date     DATETIME       NOT NULL,
    discharge_date DATETIME       NULL,
    department     VARCHAR(128)   NOT NULL,
    ward           VARCHAR(64),
    bed_no         VARCHAR(32),
    diagnosis      TEXT,
    doctor_id      INT            NULL,
    status         VARCHAR(16)    NOT NULL DEFAULT 'in_hospital' CHECK (status IN ('in_hospital', 'discharged')),
    total_cost     DECIMAL(12, 2) NOT NULL DEFAULT 0.00,
    created_at     DATETIME       NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_hosp_patient FOREIGN KEY (patient_id) REFERENCES users (id) ON DELETE CASCADE,
    CONSTRAINT fk_hosp_doctor FOREIGN KEY (doctor_id) REFERENCES users (id) ON DELETE SET NULL
) ENGINE = InnoDB
  DEFAULT CHARSET = utf8mb4
  COLLATE = utf8mb4_unicode_ci;
CREATE INDEX idx_hosp_patient ON hospitalizations (patient_id);

-- 消费明细（挂号/检查/检验/药品/住院等）
CREATE TABLE IF NOT EXISTS bills
(
    id          INT PRIMARY KEY AUTO_INCREMENT,
    patient_id  INT                 NOT NULL,
    bill_no     VARCHAR(128) UNIQUE NOT NULL,
    category    VARCHAR(64)         NOT NULL,
    description TEXT,
    amount      DECIMAL(12, 2)      NOT NULL DEFAULT 0.00,
    status      VARCHAR(16)         NOT NULL DEFAULT 'unpaid' CHECK (status IN ('paid', 'unpaid')),
    created_at  DATETIME            NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_bill_patient FOREIGN KEY (patient_id) REFERENCES users (id) ON DELETE CASCADE
) ENGINE = InnoDB
  DEFAULT CHARSET = utf8mb4
  COLLATE = utf8mb4_unicode_ci;
CREATE INDEX idx_bills_patient ON bills (patient_id);

-- 门诊预约挂号
CREATE TABLE IF NOT EXISTS appointments
(
    id         INT PRIMARY KEY AUTO_INCREMENT,
    patient_id INT            NOT NULL,
    doctor_id  INT            NULL,
    department VARCHAR(128)   NOT NULL,
    date       DATE           NOT NULL,
    time_slot  VARCHAR(32)    NOT NULL,
    symptom    TEXT,
    fee        DECIMAL(12, 2) NOT NULL DEFAULT 0.00,
    status     VARCHAR(16)    NOT NULL DEFAULT 'booked' CHECK (status IN ('booked', 'confirmed', 'visited', 'cancelled')),
    created_at DATETIME       NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_appt_patient FOREIGN KEY (patient_id) REFERENCES users (id) ON DELETE CASCADE,
    CONSTRAINT fk_appt_doctor FOREIGN KEY (doctor_id) REFERENCES users (id) ON DELETE SET NULL
) ENGINE = InnoDB
  DEFAULT CHARSET = utf8mb4
  COLLATE = utf8mb4_unicode_ci;
CREATE INDEX idx_appt_patient ON appointments (patient_id);

-- 护理记录
CREATE TABLE IF NOT EXISTS nursing_records
(
    id          INT PRIMARY KEY AUTO_INCREMENT,
    patient_id  INT         NOT NULL,
    nurse_id    INT         NOT NULL,
    record_type VARCHAR(16) NOT NULL DEFAULT 'daily' CHECK (record_type IN ('daily', 'medication', 'vitals', 'other')),
    content     TEXT        NOT NULL,
    recorded_at DATETIME    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_nursing_patient FOREIGN KEY (patient_id) REFERENCES users (id) ON DELETE CASCADE,
    CONSTRAINT fk_nursing_nurse FOREIGN KEY (nurse_id) REFERENCES users (id) ON DELETE CASCADE
) ENGINE = InnoDB
  DEFAULT CHARSET = utf8mb4
  COLLATE = utf8mb4_unicode_ci;
CREATE INDEX idx_nursing_patient ON nursing_records (patient_id);

-- 医护排班
CREATE TABLE IF NOT EXISTS schedules
(
    id         INT PRIMARY KEY AUTO_INCREMENT,
    staff_id   INT         NOT NULL,
    work_date  DATE        NOT NULL,
    shift      VARCHAR(32) NOT NULL,
    department VARCHAR(128),
    status     VARCHAR(16) NOT NULL DEFAULT 'on_duty' CHECK (status IN ('on_duty', 'off', 'leave')),
    created_at DATETIME    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_schedule_staff FOREIGN KEY (staff_id) REFERENCES users (id) ON DELETE CASCADE
) ENGINE = InnoDB
  DEFAULT CHARSET = utf8mb4
  COLLATE = utf8mb4_unicode_ci;
CREATE INDEX idx_schedule_staff ON schedules (staff_id);
