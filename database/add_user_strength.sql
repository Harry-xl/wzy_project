-- Add user strength field to user table (idempotent, compatible with older MySQL)
USE wzyProjectDb;

-- Conditionally add column `user_strength` if it does not exist
SET @col_exists := (
  SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS
  WHERE TABLE_SCHEMA = DATABASE()
    AND TABLE_NAME = 'user'
    AND COLUMN_NAME = 'user_strength'
);

-- Prepare the proper DDL statement (no result sets produced)
SET @sql := IF(@col_exists = 0,
  'ALTER TABLE `user` ADD COLUMN `user_strength` FLOAT NOT NULL DEFAULT 0.5 COMMENT ''User strength level (0.0-1.0, 0.5 is medium)''',
  'SET @noop := 1'
);
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

-- Initialize strength values for existing users based on their ability profile
UPDATE `user` u 
SET u.user_strength = (
    SELECT COALESCE(AVG(ap.proficiency_level), 0.5)
    FROM ability_profile ap 
    WHERE ap.user_id = u.user_id
)
WHERE u.user_id IN (SELECT DISTINCT user_id FROM ability_profile);