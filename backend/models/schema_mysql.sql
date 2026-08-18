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
    `chunk_count` INT          NOT NULL DEFAULT 0,
    `status`      VARCHAR(16)  NOT NULL DEFAULT 'processing' COMMENT 'processing/ready/failed',
    `error`       VARCHAR(512) NULL,
    `created_at`  DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (`id`),
    KEY `idx_doc_kb` (`kb_id`),
    KEY `idx_doc_visibility` (`visibility`)
) ENGINE = InnoDB
  DEFAULT CHARSET = utf8mb4
  COLLATE = utf8mb4_unicode_ci COMMENT ='知识库文档表';

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
    KEY `idx_citations_msg` (`message_id`)
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