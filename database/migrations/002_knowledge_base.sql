-- ============================================================
-- 星伴(StarPal) 知识库系统 — 数据库迁移
-- 版本: 002 | 日期: 2026-08-02
-- 说明: 创建知识库核心表、子知识点表、知识点关系表，
--       并扩展 user_answers 和 ability_profile 字段
-- 回滚: 删除 knowledge_* 表，删除扩展字段（如有数据需先备份）
-- ============================================================
USE wzyProjectDb;

-- -----------------------------------------------------------
-- 1. 知识文档表
-- -----------------------------------------------------------
CREATE TABLE IF NOT EXISTS knowledge_documents (
    doc_id          INT AUTO_INCREMENT PRIMARY KEY COMMENT '文档ID',
    title           VARCHAR(500) NOT NULL COMMENT '文档标题',
    doc_type        ENUM('textbook','rfc','knowledge_entry','problem_solution','paper','lab','other') NOT NULL COMMENT '文档类型',
    knowledge_points VARCHAR(1000) COMMENT '关联知识点（JSON数组）',
    osi_layer       VARCHAR(50) COMMENT '关联OSI层级',
    difficulty      ENUM('基础','进阶','高级') DEFAULT '基础' COMMENT '内容难度',
    source          VARCHAR(500) COMMENT '来源（书名/RFC编号/URL）',
    source_page     VARCHAR(100) COMMENT '来源页码/章节号',
    version         INT DEFAULT 1 COMMENT '版本号',
    status          ENUM('draft','published','archived') DEFAULT 'draft' COMMENT '文档状态',
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    updated_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    INDEX idx_doc_type (doc_type),
    INDEX idx_status (status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='知识库文档元数据表';

-- -----------------------------------------------------------
-- 2. 知识块表（RAG检索的最小单元）
--    注意: 嵌入向量存储在 ChromaDB 中，此处仅保留文本和元数据
-- -----------------------------------------------------------
CREATE TABLE IF NOT EXISTS knowledge_chunks (
    chunk_id        INT AUTO_INCREMENT PRIMARY KEY COMMENT '块ID',
    doc_id          INT NOT NULL COMMENT '所属文档ID',
    chunk_index     INT NOT NULL COMMENT '块在文档中的序号（从0开始）',
    content         MEDIUMTEXT NOT NULL COMMENT '文本内容',
    content_hash    VARCHAR(64) COMMENT '内容哈希（SHA-256，用于增量更新检测）',
    token_count     INT COMMENT 'Token 估算数',
    sub_topic_id    INT COMMENT '关联的子知识点ID',
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    FOREIGN KEY (doc_id) REFERENCES knowledge_documents(doc_id) ON DELETE CASCADE,
    INDEX idx_doc_chunk (doc_id, chunk_index),
    INDEX idx_sub_topic (sub_topic_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='知识块表——RAG检索的最小单元';

-- -----------------------------------------------------------
-- 3. 知识点关系表（知识图谱）
-- -----------------------------------------------------------
CREATE TABLE IF NOT EXISTS knowledge_relations (
    relation_id     INT AUTO_INCREMENT PRIMARY KEY COMMENT '关系ID',
    source_kp       VARCHAR(200) NOT NULL COMMENT '源知识点',
    target_kp       VARCHAR(200) NOT NULL COMMENT '目标知识点',
    relation_type   ENUM('prerequisite','extension','related','part_of') NOT NULL COMMENT '关系类型: prerequisite=前置知识, extension=扩展知识, related=相关知识, part_of=组成部分',
    description     VARCHAR(500) COMMENT '关系说明',
    INDEX idx_source (source_kp),
    INDEX idx_target (target_kp)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='知识点关系图';

-- -----------------------------------------------------------
-- 4. 子知识点表（细粒度知识组织）
--    双层架构: sub_topic → parent_kp (25个粗粒度知识点之一)
-- -----------------------------------------------------------
CREATE TABLE IF NOT EXISTS knowledge_sub_topics (
    sub_topic_id    INT AUTO_INCREMENT PRIMARY KEY COMMENT '子知识点ID',
    sub_topic_name  VARCHAR(200) NOT NULL COMMENT '子知识点名称',
    parent_kp       VARCHAR(200) NOT NULL COMMENT '所属粗粒度知识点（对应25个标准知识点之一）',
    description     TEXT COMMENT '子知识点简介',
    sort_order      INT DEFAULT 0 COMMENT '建议学习顺序（在同parent_kp内排序）',
    UNIQUE KEY uq_sub_topic (sub_topic_name, parent_kp),
    INDEX idx_parent (parent_kp)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='子知识点表——细粒度知识组织';

-- -----------------------------------------------------------
-- 5. 扩展 user_answers 表 —— 错题归因字段 (为Phase2准备)
-- -----------------------------------------------------------
SET @col_ea_exists := (
    SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS
    WHERE TABLE_SCHEMA = DATABASE()
      AND TABLE_NAME = 'user_answers'
      AND COLUMN_NAME = 'error_attribution'
);
SET @sql_ea := IF(@col_ea_exists = 0,
    'ALTER TABLE `user_answers` ADD COLUMN `error_attribution` VARCHAR(50) COMMENT ''错因归类: concept_confusion/calculation_error/misread/forgotten/reasoning_error''',
    'SET @noop := 1'
);
PREPARE stmt_ea FROM @sql_ea;
EXECUTE stmt_ea;
DEALLOCATE PREPARE stmt_ea;

SET @col_ad_exists := (
    SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS
    WHERE TABLE_SCHEMA = DATABASE()
      AND TABLE_NAME = 'user_answers'
      AND COLUMN_NAME = 'attribution_detail'
);
SET @sql_ad := IF(@col_ad_exists = 0,
    'ALTER TABLE `user_answers` ADD COLUMN `attribution_detail` JSON COMMENT ''归因详情（JSON格式: {reason, suggestion, related_kp}）''',
    'SET @noop := 1'
);
PREPARE stmt_ad FROM @sql_ad;
EXECUTE stmt_ad;
DEALLOCATE PREPARE stmt_ad;

-- -----------------------------------------------------------
-- 6. 扩展 ability_profile 表 —— 画像置信度字段 (为Phase2准备)
-- -----------------------------------------------------------
SET @col_cf_exists := (
    SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS
    WHERE TABLE_SCHEMA = DATABASE()
      AND TABLE_NAME = 'ability_profile'
      AND COLUMN_NAME = 'confidence'
);
SET @sql_cf := IF(@col_cf_exists = 0,
    'ALTER TABLE `ability_profile` ADD COLUMN `confidence` FLOAT DEFAULT 0.0 COMMENT ''熟练度置信度（数据充分度，答题越多越高）''',
    'SET @noop := 1'
);
PREPARE stmt_cf FROM @sql_cf;
EXECUTE stmt_cf;
DEALLOCATE PREPARE stmt_cf;

SET @col_ls_exists := (
    SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS
    WHERE TABLE_SCHEMA = DATABASE()
      AND TABLE_NAME = 'ability_profile'
      AND COLUMN_NAME = 'learning_speed'
);
SET @sql_ls := IF(@col_ls_exists = 0,
    'ALTER TABLE `ability_profile` ADD COLUMN `learning_speed` FLOAT COMMENT ''学习速度（每10题的熟练度提升量）''',
    'SET @noop := 1'
);
PREPARE stmt_ls FROM @sql_ls;
EXECUTE stmt_ls;
DEALLOCATE PREPARE stmt_ls;
