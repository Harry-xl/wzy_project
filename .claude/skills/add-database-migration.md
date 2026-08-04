# Skill: 添加数据库迁移 (add-database-migration)

> 安全地变更数据库 schema

## 工作流程

### 第一步：创建迁移文件
在 `database/migrations/` 中创建新文件：
- 命名：`NNN_描述.sql`（编号递增）
- 例如：`003_add_user_avatar.sql`

### 第二步：编写迁移 SQL
```sql
-- ==============================================================
-- 迁移: 003_add_user_avatar
-- 描述: 用户表添加头像 URL 字段
-- 日期: YYYY-MM-DD
-- 回滚: ALTER TABLE user DROP COLUMN avatar_url;
-- ==============================================================

-- UP: 添加字段
ALTER TABLE user
ADD COLUMN avatar_url VARCHAR(500) DEFAULT NULL COMMENT '用户头像URL';

-- 如果需要回滚（DOWN），注释中保留：
-- ALTER TABLE user DROP COLUMN avatar_url;
```

### 第三步：遵循数据库规范
- 遵循 `.claude/rules/database-design.md`
- 新字段必须有 COMMENT
- 新表使用 InnoDB + utf8mb4
- 添加合适的索引

### 第四步：更新文档
- 更新 `docs/database-schema.md` 中的表结构
- 添加 ER 图变更说明

### 第五步：更新初始化脚本
确保 `database/scripts/init_db.py` 能执行新迁移。

### 第六步：测试
1. 在测试数据库上运行迁移：`mysql wzyProjectDb_test < migrations/003_xxx.sql`
2. 运行测试：`python -m pytest tests/ -v`
3. 验证回滚脚本也能正常执行
