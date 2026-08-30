CREATE DATABASE IF NOT EXISTS `medical-assistant-master`
    DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

-- 修复：去掉database关键字
USE `medical-assistant-master`;

CREATE TABLE IF NOT EXISTS `users`
(
    `id`            INT UNSIGNED NOT NULL AUTO_INCREMENT,
    `username`      VARCHAR(32)  NOT NULL COMMENT '登录用户名（唯一）',
    `password_hash` VARCHAR(255) NOT NULL COMMENT '密码哈希',
    `role`          VARCHAR(16)  NOT NULL COMMENT 'patient/doctor/nurse/public/admin',
    `display_name`  VARCHAR(64)  NULL,
    `first_login_done` TINYINT   NOT NULL DEFAULT 0 COMMENT '是否已初次登录（用于管理员/医生首登清空知识库）',
    `created_at`    DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (`id`),
    UNIQUE KEY `uk_users_username` (`username`),
    KEY `idx_users_role` (`role`)
) ENGINE = InnoDB
  DEFAULT CHARSET = utf8mb4
  COLLATE = utf8mb4_unicode_ci COMMENT ='用户表';

-- 知识库表（visibility：public/private）
CREATE TABLE IF NOT EXISTS `knowledge_bases`
(
    `id`          INT UNSIGNED NOT NULL AUTO_INCREMENT,
    `owner_id`    INT UNSIGNED NULL COMMENT 'NULL=平台公共知识库',
    `name`        VARCHAR(128) NOT NULL,
    `description` VARCHAR(512) NULL,
    `visibility`  VARCHAR(16)  NOT NULL DEFAULT 'private' COMMENT 'public/private',
    `created_at`  DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (`id`),
    KEY `idx_kb_owner` (`owner_id`),
    KEY `idx_kb_visibility` (`visibility`)
) ENGINE = InnoDB
  DEFAULT CHARSET = utf8mb4
  COLLATE = utf8mb4_unicode_ci COMMENT ='知识库表';

-- 文档表（visibility：public/private，存于 uploads/<知识库>/公开|私有/ 目录）
CREATE TABLE IF NOT EXISTS `documents`
(
    `id`          INT UNSIGNED NOT NULL AUTO_INCREMENT,
    `kb_id`       INT UNSIGNED NOT NULL,
    `filename`    VARCHAR(255) NOT NULL,
    `file_path`   VARCHAR(512) NOT NULL COMMENT 'UPLOAD_DIR 下的相对路径',
    `file_type`   VARCHAR(16)  NOT NULL COMMENT 'txt/md/pdf/docx/pptx',
    `visibility`  VARCHAR(16)  NOT NULL DEFAULT 'public' COMMENT 'public/private',
    `chunk_count`    INT          NOT NULL DEFAULT 0,
    `status`         VARCHAR(16)  NOT NULL DEFAULT 'processing' COMMENT 'processing/ready/failed',
    `review_status`  VARCHAR(16)  NOT NULL DEFAULT 'pending' COMMENT 'pending/approved/rejected（人工复核）',
    `reviewer_id`    INT UNSIGNED NULL,
    `reviewed_at`    DATETIME     NULL,
    `review_note`    VARCHAR(512) NULL,
    `error`          VARCHAR(512) NULL,
    `indexed_at`     DATETIME     NULL COMMENT '最近一次向量化完成时间',
    `created_at`     DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (`id`),
    KEY `idx_doc_kb` (`kb_id`),
    KEY `idx_doc_visibility` (`visibility`),
    KEY `idx_doc_kb_status` (`kb_id`, `status`)
) ENGINE = InnoDB;

-- 父块表：按文档标题/章节生成的大段语义块，用于保留完整上下文
CREATE TABLE IF NOT EXISTS `chunks`
(
    `id`          INT UNSIGNED NOT NULL AUTO_INCREMENT,
    `doc_id`      INT UNSIGNED NOT NULL COMMENT '所属文档',
    `kb_id`       INT UNSIGNED NOT NULL COMMENT '所属知识库',
    `parent_id`   INT UNSIGNED NULL COMMENT '父块ID（根块为NULL）',
    `chunk_index` INT          NOT NULL COMMENT '块在文档内的序号',
    `heading`     VARCHAR(512) NULL COMMENT '所属章节标题',
    `text`        TEXT         NOT NULL COMMENT '块文本',
    `token_count` INT          NOT NULL DEFAULT 0,
    `created_at`  DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (`id`),
    KEY `idx_chunk_doc` (`doc_id`),
    KEY `idx_chunk_kb` (`kb_id`),
    KEY `idx_chunk_parent` (`parent_id`)
    -- 注：外键在 MySQL 某些版本/字符集组合下易出现类型不兼容，由应用层保证引用完整性
) ENGINE = InnoDB
  DEFAULT CHARSET = utf8mb4
  COLLATE = utf8mb4_unicode_ci COMMENT ='文档父块表';

-- 子块表：从父块进一步切分的检索单元，存 bge 向量路径与 BM25 统计
CREATE TABLE IF NOT EXISTS `sub_chunks`
(
    `id`            INT UNSIGNED NOT NULL AUTO_INCREMENT,
    `chunk_id`      INT UNSIGNED NOT NULL COMMENT '所属父块',
    `doc_id`        INT UNSIGNED NOT NULL,
    `kb_id`         INT UNSIGNED NOT NULL,
    `sub_index`     INT          NOT NULL COMMENT '子块在父块内的序号',
    `text`          TEXT         NOT NULL,
    `vector_path`   VARCHAR(512) NULL COMMENT '向量文件相对路径（JSON/npy 或 Milvus 已存标记）',
    `bm25_terms`    JSON         NULL COMMENT 'BM25 词频统计 {term: tf}',
    `token_count`   INT          NOT NULL DEFAULT 0,
    `created_at`    DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (`id`),
    KEY `idx_sub_chunk` (`chunk_id`),
    KEY `idx_sub_doc` (`doc_id`),
    KEY `idx_sub_kb` (`kb_id`)
) ENGINE = InnoDB
  DEFAULT CHARSET = utf8mb4
  COLLATE = utf8mb4_unicode_ci COMMENT ='文档子块表';

-- BM25 全局词频/文档频率表：按知识库维护，用于快速 BM25 打分
CREATE TABLE IF NOT EXISTS `bm25_terms`
(
    `id`       INT UNSIGNED NOT NULL AUTO_INCREMENT,
    `kb_id`    INT UNSIGNED NOT NULL,
    `term`     VARCHAR(128) NOT NULL,
    `df`       INT          NOT NULL DEFAULT 0 COMMENT '文档频率（出现该词的子块数）',
    `cf`       INT          NOT NULL DEFAULT 0 COMMENT '集合频率（总出现次数）',
    `updated_at` DATETIME   NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (`id`),
    UNIQUE KEY `uk_bm25_kb_term` (`kb_id`, `term`),
    KEY `idx_bm25_kb` (`kb_id`)
) ENGINE = InnoDB
  DEFAULT CHARSET = utf8mb4
  COLLATE = utf8mb4_unicode_ci COMMENT ='BM25 词频统计表';

-- 向量存储元数据表：记录每个子块在 Milvus / NumpyStore 中的存储状态
CREATE TABLE IF NOT EXISTS `chunk_vectors`
(
    `id`           INT UNSIGNED NOT NULL AUTO_INCREMENT,
    `sub_chunk_id` INT UNSIGNED NOT NULL,
    `doc_id`       INT UNSIGNED NOT NULL,
    `kb_id`        INT UNSIGNED NOT NULL,
    `store_type`   VARCHAR(32)  NOT NULL DEFAULT 'numpy' COMMENT 'milvus/numpy',
    `store_key`    VARCHAR(128) NOT NULL COMMENT 'Milvus id 或 numpy 文件键',
    `created_at`   DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (`id`),
    UNIQUE KEY `uk_vec_sub` (`sub_chunk_id`),
    KEY `idx_vec_doc` (`doc_id`),
    KEY `idx_vec_kb` (`kb_id`)
) ENGINE = InnoDB
  DEFAULT CHARSET = utf8mb4
  COLLATE = utf8mb4_unicode_ci COMMENT ='子块向量元数据表';

-- 咨询会话表
CREATE TABLE IF NOT EXISTS `conversations`
(
    `id`         VARCHAR(32)  NOT NULL COMMENT 'uuid4 hex',
    `user_id`    INT UNSIGNED NOT NULL,
    `kb_id`      INT UNSIGNED NULL,
    `title`      VARCHAR(128) NOT NULL,
    `created_at` DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    `updated_at` DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (`id`),
    KEY `idx_conv_user` (`user_id`),
    KEY `idx_conv_kb` (`kb_id`)
) ENGINE = InnoDB
  DEFAULT CHARSET = utf8mb4
  COLLATE = utf8mb4_unicode_ci COMMENT ='咨询会话表';

-- 会话消息表
CREATE TABLE IF NOT EXISTS `messages`
(
    `id`              INT UNSIGNED NOT NULL AUTO_INCREMENT,
    `conversation_id` VARCHAR(32)  NOT NULL,
    `role`            VARCHAR(16)  NOT NULL COMMENT 'user/assistant',
    `content`         TEXT         NOT NULL,
    `review_status`   VARCHAR(16)  NOT NULL DEFAULT 'pending' COMMENT 'pending/approved/rejected（人工复核）',
    `reviewer_id`     INT UNSIGNED NULL,
    `reviewed_at`     DATETIME     NULL,
    `review_note`     VARCHAR(512) NULL,
    `agent_steps`     TEXT         NULL COMMENT 'Agent ReAct 轨迹(JSON)',
    `created_at`      DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (`id`),
    KEY `idx_messages_conv` (`conversation_id`)
) ENGINE = InnoDB
  DEFAULT CHARSET = utf8mb4
  COLLATE = utf8mb4_unicode_ci COMMENT ='会话消息表';

-- 引用来源表
CREATE TABLE IF NOT EXISTS `citations`
(
    `id`          INT UNSIGNED NOT NULL AUTO_INCREMENT,
    `message_id`  INT UNSIGNED NOT NULL,
    `document_id` INT UNSIGNED NOT NULL,
    `chunk_index` INT          NOT NULL,
    `source_text` TEXT         NULL,
    `title`       VARCHAR(255) NULL,
    `similarity`  DOUBLE       NULL,
    PRIMARY KEY (`id`),
    KEY `idx_citations_msg` (`message_id`),
    KEY `idx_citations_doc` (`document_id`)
) ENGINE = InnoDB
  DEFAULT CHARSET = utf8mb4
  COLLATE = utf8mb4_unicode_ci COMMENT ='回答引用来源表';

-- 住院信息表
CREATE TABLE IF NOT EXISTS `hospitalizations`
(
    `id`             INT UNSIGNED NOT NULL AUTO_INCREMENT,
    `patient_id`     INT UNSIGNED NOT NULL,
    `admit_date`     VARCHAR(20)  NOT NULL,
    `discharge_date` VARCHAR(20)  NULL,
    `department`     VARCHAR(64)  NOT NULL,
    `ward`           VARCHAR(64)  NULL,
    `bed_no`         VARCHAR(32)  NULL,
    `diagnosis`      VARCHAR(255) NULL,
    `doctor_id`      INT UNSIGNED NULL,
    `status`         VARCHAR(16)  NOT NULL DEFAULT 'in_hospital' COMMENT 'in_hospital/discharged',
    `total_cost`     DOUBLE       NOT NULL DEFAULT 0,
    `created_at`     DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (`id`),
    KEY `idx_hosp_patient` (`patient_id`)
) ENGINE = InnoDB
  DEFAULT CHARSET = utf8mb4
  COLLATE = utf8mb4_unicode_ci COMMENT ='住院信息表';

-- 消费明细表
CREATE TABLE IF NOT EXISTS `bills`
(
    `id`          INT UNSIGNED NOT NULL AUTO_INCREMENT,
    `patient_id`  INT UNSIGNED NOT NULL,
    `bill_no`     VARCHAR(64)  NOT NULL,
    `category`    VARCHAR(32)  NOT NULL COMMENT '挂号/检查/检验/药品/住院/门诊',
    `description` VARCHAR(255) NULL,
    `amount`      DOUBLE       NOT NULL DEFAULT 0,
    `status`      VARCHAR(16)  NOT NULL DEFAULT 'unpaid' COMMENT 'paid/unpaid',
    `created_at`  DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (`id`),
    UNIQUE KEY `uk_bills_bill_no` (`bill_no`),
    KEY `idx_bills_patient` (`patient_id`)
) ENGINE = InnoDB
  DEFAULT CHARSET = utf8mb4
  COLLATE = utf8mb4_unicode_ci COMMENT ='消费明细表';

-- 门诊预约挂号表
CREATE TABLE IF NOT EXISTS `appointments`
(
    `id`         INT UNSIGNED NOT NULL AUTO_INCREMENT,
    `patient_id` INT UNSIGNED NOT NULL,
    `doctor_id`  INT UNSIGNED NULL,
    `department` VARCHAR(64)  NOT NULL,
    `date`       VARCHAR(20)  NOT NULL,
    `time_slot`  VARCHAR(32)  NOT NULL,
    `symptom`    VARCHAR(255) NULL,
    `fee`        DOUBLE       NOT NULL DEFAULT 0,
    `status`     VARCHAR(16)  NOT NULL DEFAULT 'booked' COMMENT 'booked/confirmed/visited/cancelled',
    `created_at` DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (`id`),
    KEY `idx_appt_patient` (`patient_id`)
) ENGINE = InnoDB
  DEFAULT CHARSET = utf8mb4
  COLLATE = utf8mb4_unicode_ci COMMENT ='门诊预约挂号表';

-- 护理记录表
CREATE TABLE IF NOT EXISTS `nursing_records`
(
    `id`          INT UNSIGNED NOT NULL AUTO_INCREMENT,
    `patient_id`  INT UNSIGNED NOT NULL,
    `nurse_id`    INT UNSIGNED NOT NULL,
    `record_type` VARCHAR(16)  NOT NULL DEFAULT 'daily' COMMENT 'daily/medication/vitals/other',
    `content`     TEXT         NOT NULL,
    `recorded_at` DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (`id`),
    KEY `idx_nursing_patient` (`patient_id`)
) ENGINE = InnoDB
  DEFAULT CHARSET = utf8mb4
  COLLATE = utf8mb4_unicode_ci COMMENT ='护理记录表';

-- 医护排班表
CREATE TABLE IF NOT EXISTS `schedules`
(
    `id`         INT UNSIGNED NOT NULL AUTO_INCREMENT,
    `staff_id`   INT UNSIGNED NOT NULL,
    `work_date`  VARCHAR(20)  NOT NULL,
    `shift`      VARCHAR(16)  NOT NULL COMMENT 'day/night/evening/off',
    `department` VARCHAR(64)  NULL,
    `remark`     VARCHAR(255) NULL,
    `status`     VARCHAR(16)  NOT NULL DEFAULT 'on_duty' COMMENT 'on_duty/off/leave',
    `created_at` DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (`id`),
    KEY `idx_schedule_staff` (`staff_id`)
) ENGINE = InnoDB
  DEFAULT CHARSET = utf8mb4
  COLLATE = utf8mb4_unicode_ci COMMENT ='医护排班表';
-- 审计日志表（人工复核 HITL 留痕 + 关键操作追溯）
CREATE TABLE IF NOT EXISTS `audit_logs`
(
    `id`          INT UNSIGNED NOT NULL AUTO_INCREMENT COMMENT '主键',
    `actor_id`    INT UNSIGNED NULL COMMENT '操作人 user_id',
    `actor_role`  VARCHAR(32)  NULL COMMENT '操作人角色快照',
    `action`      VARCHAR(64)  NOT NULL COMMENT '动作标识：ai_answer_approved / doc_rejected / ...',
    `target_type` VARCHAR(32)  NULL COMMENT '对象类型：message / document / user ...',
    `target_id`   VARCHAR(64)  NULL COMMENT '对象 ID',
    `detail`      VARCHAR(1000) NULL COMMENT '摘要或复核意见',
    `ip`          VARCHAR(64)  NULL COMMENT '来源 IP',
    `created_at`  DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '发生时间',
    PRIMARY KEY (`id`),
    KEY `idx_audit_action` (`action`),
    KEY `idx_audit_target` (`target_type`, `target_id`),
    KEY `idx_audit_created` (`created_at`)
) ENGINE = InnoDB
  DEFAULT CHARSET = utf8mb4
  COLLATE = utf8mb4_unicode_ci COMMENT ='审计日志表';
