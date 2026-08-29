-- 医智助手业务库 Schema MySQL版本（修复数据库名横杠、兼容5.7&8.0）
CREATE DATABASE IF NOT EXISTS `medical-assistant-master` DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE `medical-assistant-master`;

CREATE TABLE IF NOT EXISTS users (
    id            INT PRIMARY KEY AUTO_INCREMENT,
    username      VARCHAR(128) UNIQUE NOT NULL,
    password_hash TEXT                NOT NULL,
    role          VARCHAR(32)         NOT NULL,
    display_name  VARCHAR(128),
    first_login_done TINYINT NOT NULL DEFAULT 0,
    created_at    DATETIME            NOT NULL DEFAULT CURRENT_TIMESTAMP
) ENGINE = InnoDB
  DEFAULT CHARSET = utf8mb4
  COLLATE = utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS knowledge_bases (
    id          INT PRIMARY KEY AUTO_INCREMENT,
    owner_id    INT          NULL,
    name        VARCHAR(255) NOT NULL,
    description TEXT,
    visibility  VARCHAR(16)  NOT NULL DEFAULT 'private',
    created_at  DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_kb_owner FOREIGN KEY (owner_id) REFERENCES users (id) ON DELETE CASCADE
) ENGINE = InnoDB
  DEFAULT CHARSET = utf8mb4
  COLLATE = utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS documents (
    id          INT PRIMARY KEY AUTO_INCREMENT,
    kb_id       INT          NOT NULL,
    filename    VARCHAR(255) NOT NULL,
    file_path   VARCHAR(512) NOT NULL,
    file_type   VARCHAR(32)  NOT NULL,
    visibility  VARCHAR(16)  NOT NULL DEFAULT 'public',
    chunk_count INT          NOT NULL DEFAULT 0,
    status      VARCHAR(16)  NOT NULL DEFAULT 'processing',
    error       TEXT,
    indexed_at  DATETIME     NULL,
    created_at  DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_doc_kb FOREIGN KEY (kb_id) REFERENCES knowledge_bases (id) ON DELETE CASCADE
) ENGINE = InnoDB
  DEFAULT CHARSET = utf8mb4
  COLLATE = utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS chunks (
    id          INT PRIMARY KEY AUTO_INCREMENT,
    doc_id      INT          NOT NULL,
    kb_id       INT          NOT NULL,
    parent_id   INT          NULL,
    chunk_index INT          NOT NULL,
    heading     VARCHAR(512) NULL,
    text        TEXT         NOT NULL,
    token_count INT          NOT NULL DEFAULT 0,
    created_at  DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP
) ENGINE = InnoDB
  DEFAULT CHARSET = utf8mb4
  COLLATE = utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS sub_chunks (
    id            INT PRIMARY KEY AUTO_INCREMENT,
    chunk_id      INT          NOT NULL,
    doc_id        INT          NOT NULL,
    kb_id         INT          NOT NULL,
    sub_index     INT          NOT NULL,
    text          TEXT         NOT NULL,
    vector_path   VARCHAR(512) NULL,
    bm25_terms    TEXT         NULL,
    token_count   INT          NOT NULL DEFAULT 0,
    created_at    DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP
) ENGINE = InnoDB
  DEFAULT CHARSET = utf8mb4
  COLLATE = utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS bm25_terms (
    id         INT PRIMARY KEY AUTO_INCREMENT,
    kb_id      INT          NOT NULL,
    term       VARCHAR(128) NOT NULL,
    df         INT          NOT NULL DEFAULT 0,
    cf         INT          NOT NULL DEFAULT 0,
    updated_at DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    UNIQUE KEY uk_bm25_kb_term (kb_id, term)
) ENGINE = InnoDB
  DEFAULT CHARSET = utf8mb4
  COLLATE = utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS chunk_vectors (
    id           INT PRIMARY KEY AUTO_INCREMENT,
    sub_chunk_id INT          NOT NULL,
    doc_id       INT          NOT NULL,
    kb_id        INT          NOT NULL,
    store_type   VARCHAR(32)  NOT NULL DEFAULT 'numpy',
    store_key    VARCHAR(128) NOT NULL,
    created_at   DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP
) ENGINE = InnoDB
  DEFAULT CHARSET = utf8mb4
  COLLATE = utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS conversations (
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

CREATE TABLE IF NOT EXISTS messages (
    id              INT PRIMARY KEY AUTO_INCREMENT,
    conversation_id VARCHAR(36) NOT NULL,
    role            VARCHAR(16) NOT NULL,
    content         TEXT        NOT NULL,
    created_at      DATETIME    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_msg_conv FOREIGN KEY (conversation_id) REFERENCES conversations (id) ON DELETE CASCADE
) ENGINE = InnoDB
  DEFAULT CHARSET = utf8mb4
  COLLATE = utf8mb4_unicode_ci;

-- 安全创建索引：兼容MySQL5.7/8.0，不存在才创建
SET @sql := IF(
    NOT EXISTS (SELECT 1 FROM INFORMATION_SCHEMA.STATISTICS WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME='messages' AND INDEX_NAME='idx_messages_conv'),
    'CREATE INDEX idx_messages_conv ON messages(conversation_id);',
    'SELECT ''index exists'';'
);
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

CREATE TABLE IF NOT EXISTS citations (
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

SET @sql := IF(
    NOT EXISTS (SELECT 1 FROM INFORMATION_SCHEMA.STATISTICS WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME='citations' AND INDEX_NAME='idx_citations_msg'),
    'CREATE INDEX idx_citations_msg ON citations(message_id);',
    'SELECT ''index exists'';'
);
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET @sql := IF(
    NOT EXISTS (SELECT 1 FROM INFORMATION_SCHEMA.STATISTICS WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME='documents' AND INDEX_NAME='idx_doc_kb_status'),
    'CREATE INDEX idx_doc_kb_status ON documents(kb_id, status);',
    'SELECT ''index exists'';'
);
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET @sql := IF(
    NOT EXISTS (SELECT 1 FROM INFORMATION_SCHEMA.STATISTICS WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME='citations' AND INDEX_NAME='idx_citations_doc'),
    'CREATE INDEX idx_citations_doc ON citations(document_id);',
    'SELECT ''index exists'';'
);
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

-- ===== 患者健康档案 / 医护工作数据 =====
-- 住院信息
CREATE TABLE IF NOT EXISTS hospitalizations (
    id             INT PRIMARY KEY AUTO_INCREMENT,
    patient_id     INT            NOT NULL,
    admit_date     DATETIME       NOT NULL,
    discharge_date DATETIME       NULL,
    department     VARCHAR(128)   NOT NULL,
    ward           VARCHAR(64),
    bed_no         VARCHAR(32),
    diagnosis      TEXT,
    doctor_id      INT            NULL,
    status         VARCHAR(16)    NOT NULL DEFAULT 'in_hospital',
    total_cost     DECIMAL(12, 2) NOT NULL DEFAULT 0.00,
    created_at     DATETIME       NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_hosp_patient FOREIGN KEY (patient_id) REFERENCES users (id) ON DELETE CASCADE,
    CONSTRAINT fk_hosp_doctor FOREIGN KEY (doctor_id) REFERENCES users (id) ON DELETE SET NULL
) ENGINE = InnoDB
  DEFAULT CHARSET = utf8mb4
  COLLATE = utf8mb4_unicode_ci;

SET @sql := IF(
    NOT EXISTS (SELECT 1 FROM INFORMATION_SCHEMA.STATISTICS WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME='hospitalizations' AND INDEX_NAME='idx_hosp_patient'),
    'CREATE INDEX idx_hosp_patient ON hospitalizations(patient_id);',
    'SELECT ''index exists'';'
);
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

-- 消费明细（挂号/检查/检验/药品/住院等）
CREATE TABLE IF NOT EXISTS bills (
    id          INT PRIMARY KEY AUTO_INCREMENT,
    patient_id  INT                 NOT NULL,
    bill_no     VARCHAR(128) UNIQUE NOT NULL,
    category    VARCHAR(64)         NOT NULL,
    description TEXT,
    amount      DECIMAL(12, 2)      NOT NULL DEFAULT 0.00,
    status      VARCHAR(16)         NOT NULL DEFAULT 'unpaid',
    created_at  DATETIME            NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_bill_patient FOREIGN KEY (patient_id) REFERENCES users (id) ON DELETE CASCADE
) ENGINE = InnoDB
  DEFAULT CHARSET = utf8mb4
  COLLATE = utf8mb4_unicode_ci;

SET @sql := IF(
    NOT EXISTS (SELECT 1 FROM INFORMATION_SCHEMA.STATISTICS WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME='bills' AND INDEX_NAME='idx_bills_patient'),
    'CREATE INDEX idx_bills_patient ON bills(patient_id);',
    'SELECT ''index exists'';'
);
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

-- 门诊预约挂号
CREATE TABLE IF NOT EXISTS appointments (
    id         INT PRIMARY KEY AUTO_INCREMENT,
    patient_id INT            NOT NULL,
    doctor_id  INT            NULL,
    department VARCHAR(128)   NOT NULL,
    date       DATE           NOT NULL,
    time_slot  VARCHAR(32)    NOT NULL,
    symptom    TEXT,
    fee        DECIMAL(12, 2) NOT NULL DEFAULT 0.00,
    status     VARCHAR(16)    NOT NULL DEFAULT 'booked',
    created_at DATETIME       NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_appt_patient FOREIGN KEY (patient_id) REFERENCES users (id) ON DELETE CASCADE,
    CONSTRAINT fk_appt_doctor FOREIGN KEY (doctor_id) REFERENCES users (id) ON DELETE SET NULL
) ENGINE = InnoDB
  DEFAULT CHARSET = utf8mb4
  COLLATE = utf8mb4_unicode_ci;

SET @sql := IF(
    NOT EXISTS (SELECT 1 FROM INFORMATION_SCHEMA.STATISTICS WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME='appointments' AND INDEX_NAME='idx_appt_patient'),
    'CREATE INDEX idx_appt_patient ON appointments(patient_id);',
    'SELECT ''index exists'';'
);
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

-- 护理记录
CREATE TABLE IF NOT EXISTS nursing_records (
    id          INT PRIMARY KEY AUTO_INCREMENT,
    patient_id  INT         NOT NULL,
    nurse_id    INT         NOT NULL,
    record_type VARCHAR(16) NOT NULL DEFAULT 'daily',
    content     TEXT        NOT NULL,
    recorded_at DATETIME    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_nursing_patient FOREIGN KEY (patient_id) REFERENCES users (id) ON DELETE CASCADE,
    CONSTRAINT fk_nursing_nurse FOREIGN KEY (nurse_id) REFERENCES users (id) ON DELETE CASCADE
) ENGINE = InnoDB
  DEFAULT CHARSET = utf8mb4
  COLLATE = utf8mb4_unicode_ci;

SET @sql := IF(
    NOT EXISTS (SELECT 1 FROM INFORMATION_SCHEMA.STATISTICS WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME='nursing_records' AND INDEX_NAME='idx_nursing_patient'),
    'CREATE INDEX idx_nursing_patient ON nursing_records(patient_id);',
    'SELECT ''index exists'';'
);
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

-- 医护排班
CREATE TABLE IF NOT EXISTS schedules (
    id         INT PRIMARY KEY AUTO_INCREMENT,
    staff_id   INT         NOT NULL,
    work_date  DATE        NOT NULL,
    shift      VARCHAR(32) NOT NULL,
    department VARCHAR(128),
    status     VARCHAR(16) NOT NULL DEFAULT 'on_duty',
    created_at DATETIME    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_schedule_staff FOREIGN KEY (staff_id) REFERENCES users (id) ON DELETE CASCADE
) ENGINE = InnoDB
  DEFAULT CHARSET = utf8mb4
  COLLATE = utf8mb4_unicode_ci;

SET @sql := IF(
    NOT EXISTS (SELECT 1 FROM INFORMATION_SCHEMA.STATISTICS WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME='schedules' AND INDEX_NAME='idx_schedule_staff'),
    'CREATE INDEX idx_schedule_staff ON schedules(staff_id);',
    'SELECT ''index exists'';'
);
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;
