-- ============================================================
-- 星伴(StarPal) 个人资料库系统 — 数据库迁移
-- 版本: 003 | 日期: 2026-08-04
-- 说明: 创建 library_tasks 表追踪异步处理任务，
--       并扩展 knowledge_documents 表支持双轨知识架构
--       (user_id=NULL=系统知识库, user_id=具体值=个人资料库)
-- 回滚: DROP TABLE IF EXISTS library_tasks;
--       ALTER TABLE knowledge_documents DROP FOREIGN KEY fk_kd_user;
--       ALTER TABLE knowledge_documents DROP COLUMN user_id;
-- ============================================================
USE wzyProjectDb;

-- -----------------------------------------------------------
-- 1. 资料库异步任务表
--    追踪文件上传→处理→入库的全流程状态
-- -----------------------------------------------------------
CREATE TABLE IF NOT EXISTS library_tasks (
    task_id         VARCHAR(36) PRIMARY KEY COMMENT '任务UUID',
    user_id         INT COMMENT '用户ID（NULL=系统任务）',
    doc_id          INT COMMENT '关联的knowledge_documents.doc_id（完成后填充）',
    file_name       VARCHAR(500) NOT NULL COMMENT '原始文件名',
    file_path       VARCHAR(1000) NOT NULL COMMENT '服务器端存储路径',
    file_type       ENUM('scanned_pdf','text_pdf','word') NOT NULL COMMENT '文件类型标识',
    file_size_bytes BIGINT NOT NULL COMMENT '文件大小(字节)',
    status          ENUM('pending','processing','completed','failed') DEFAULT 'pending' COMMENT '处理状态',
    progress_pct    FLOAT DEFAULT 0 COMMENT '处理进度 0-100',
    progress_detail JSON COMMENT '详细进度信息 {step, page, total, failed_pages:[...]}',
    error_message   TEXT COMMENT '失败原因（status=failed时填充）',
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    updated_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '最后更新时间',

    INDEX idx_task_user_status (user_id, status),
    INDEX idx_task_status (status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='资料库异步处理任务表';

-- -----------------------------------------------------------
-- 2. 扩展 knowledge_documents 表 —— 支持双轨知识架构
--    user_id IS NULL  → 系统知识库（管理员上传，所有用户共享）
--    user_id = 具体值  → 个人资料库（用户自主上传，仅本人可见）
-- -----------------------------------------------------------
SET @col_uid_exists := (
    SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS
    WHERE TABLE_SCHEMA = DATABASE()
      AND TABLE_NAME = 'knowledge_documents'
      AND COLUMN_NAME = 'user_id'
);
SET @sql_uid := IF(@col_uid_exists = 0,
    'ALTER TABLE `knowledge_documents` '
    'ADD COLUMN `user_id` INT DEFAULT NULL COMMENT ''用户ID（NULL=系统资料，非NULL=个人资料）'', '
    'ADD INDEX `idx_kd_user` (`user_id`)',
    'SET @noop := 1'
);
PREPARE stmt_uid FROM @sql_uid;
EXECUTE stmt_uid;
DEALLOCATE PREPARE stmt_uid;

-- 添加外键约束（仅当列是本次新建时才执行；已存在的列如果已有外键则跳过）
SET @fk_exists := (
    SELECT COUNT(*) FROM INFORMATION_SCHEMA.KEY_COLUMN_USAGE
    WHERE TABLE_SCHEMA = DATABASE()
      AND TABLE_NAME = 'knowledge_documents'
      AND COLUMN_NAME = 'user_id'
      AND REFERENCED_TABLE_NAME IS NOT NULL
);
SET @sql_fk := IF(@fk_exists = 0,
    'ALTER TABLE `knowledge_documents` '
    'ADD CONSTRAINT `fk_kd_user` FOREIGN KEY (`user_id`) REFERENCES `user`(`user_id`) ON DELETE CASCADE',
    'SET @noop := 1'
);
PREPARE stmt_fk FROM @sql_fk;
EXECUTE stmt_fk;
DEALLOCATE PREPARE stmt_fk;
