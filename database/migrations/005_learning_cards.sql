-- ============================================================
-- 迁移: 005_learning_cards
-- 描述: 知识点学习卡片 + 文档可读内容
--       1. 创建 knowledge_learning_cards 表（学习卡片缓存）
--       2. 为 knowledge_documents 添加 readable_content 列
--       3. 为 knowledge_documents 添加 readable_generated_at 列
-- 日期: 2026-08-07
-- 回滚:
--   DROP TABLE IF EXISTS knowledge_learning_cards;
--   ALTER TABLE knowledge_documents DROP COLUMN readable_content;
--   ALTER TABLE knowledge_documents DROP COLUMN readable_generated_at;
-- ============================================================
USE wzyProjectDb;

-- -----------------------------------------------------------
-- 1. 创建知识点学习卡片缓存表
-- -----------------------------------------------------------
CREATE TABLE IF NOT EXISTS `knowledge_learning_cards` (
    `card_id`        INT AUTO_INCREMENT PRIMARY KEY COMMENT '卡片ID',
    `sub_topic_id`   INT NOT NULL COMMENT '关联子知识点ID',
    `user_id`        INT DEFAULT NULL COMMENT '资料库用户ID（NULL=系统知识库）',
    `slim_content`   TEXT NOT NULL COMMENT '精简版内容（定义+要点+来源，约200-400字）',
    `full_content`   TEXT DEFAULT NULL COMMENT '完整版内容（详细讲解+常见误区+记忆口诀等）',
    `source_doc_ids` VARCHAR(500) DEFAULT NULL COMMENT '来源文档ID列表，JSON数组如[1,2,3]',
    `is_regenerating` TINYINT(1) NOT NULL DEFAULT 0 COMMENT '是否正在重新生成',
    `generated_at`   TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '生成时间',
    `updated_at`     TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '最后更新时间',

    UNIQUE KEY `uq_card_topic_user` (`sub_topic_id`, `user_id`),
    INDEX `idx_card_user` (`user_id`),
    CONSTRAINT `fk_card_sub_topic` FOREIGN KEY (`sub_topic_id`)
        REFERENCES `knowledge_sub_topics`(`sub_topic_id`) ON DELETE CASCADE,
    CONSTRAINT `fk_card_user` FOREIGN KEY (`user_id`)
        REFERENCES `user`(`user_id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
  COMMENT='知识点学习卡片缓存表（按子知识点+用户粒度缓存AI生成内容）';

-- -----------------------------------------------------------
-- 2. knowledge_documents 添加可读内容字段（动态列检测）
-- -----------------------------------------------------------
SET @col_rc_exists := (
    SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS
    WHERE TABLE_SCHEMA = DATABASE()
      AND TABLE_NAME = 'knowledge_documents'
      AND COLUMN_NAME = 'readable_content'
);
SET @sql_rc := IF(@col_rc_exists = 0,
    'ALTER TABLE `knowledge_documents` '
    'ADD COLUMN `readable_content` MEDIUMTEXT DEFAULT NULL COMMENT ''AI整理后的可读Markdown内容'' AFTER `user_id`',
    'SET @noop := 1'
);
PREPARE stmt_rc FROM @sql_rc;
EXECUTE stmt_rc;
DEALLOCATE PREPARE stmt_rc;

SET @col_rga_exists := (
    SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS
    WHERE TABLE_SCHEMA = DATABASE()
      AND TABLE_NAME = 'knowledge_documents'
      AND COLUMN_NAME = 'readable_generated_at'
);
SET @sql_rga := IF(@col_rga_exists = 0,
    'ALTER TABLE `knowledge_documents` '
    'ADD COLUMN `readable_generated_at` TIMESTAMP NULL DEFAULT NULL COMMENT ''可读内容生成时间'' AFTER `readable_content`',
    'SET @noop := 1'
);
PREPARE stmt_rga FROM @sql_rga;
EXECUTE stmt_rga;
DEALLOCATE PREPARE stmt_rga;