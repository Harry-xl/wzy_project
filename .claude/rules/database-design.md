# 数据库设计规范

## 引擎与字符集
- 引擎：InnoDB（支持事务、外键、行级锁）
- 字符集：`utf8mb4`（支持 emoji 和全 Unicode）
- 排序规则：`utf8mb4_unicode_ci`

## 命名约定
- 表名：小写 + 下划线，单数（`user`, `problem`, `ability_profile`）
- 主键：`<表名>_id`，如 `user_id`, `problem_id`
- 外键：与被引用表的主键同名
- 索引：`idx_<表名>_<列名>`，如 `idx_user_answers_user_id`
- 唯一约束：`uq_<表名>_<列名>`

## 字段设计
```sql
CREATE TABLE user (
    user_id      INT AUTO_INCREMENT PRIMARY KEY COMMENT '用户ID',
    email        VARCHAR(255) NOT NULL COMMENT '邮箱（登录账号）',
    name         VARCHAR(255) NOT NULL COMMENT '用户昵称',
    password     VARCHAR(255) NOT NULL COMMENT 'PBKDF2-SHA256 哈希密码',
    user_strength FLOAT DEFAULT 0.5 COMMENT '用户整体实力（0.0~1.0）',
    created_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '注册时间',

    UNIQUE KEY uq_user_email (email)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='用户表';
```

## 设计原则
- 所有表必须有 `COMMENT`（表和列都需要）
- 所有外键必须定义 `FOREIGN KEY ... REFERENCES`
- 级联删除仅在语义合理时使用 `ON DELETE CASCADE`
- 枚举值用中文允许（`ENUM('简单','中等','困难')`）
- 避免 `NULL`，使用合理的默认值
- 使用 `TIMESTAMP` 而非 `DATETIME`（自动时区处理）

## 索引策略
- 主键自动有聚簇索引
- 所有外键列建索引
- 频繁查询的 WHERE 列建索引
- 复合索引：最频繁的查询组合
- 定期分析慢查询（`EXPLAIN`）
- 避免过多索引（影响写入性能）

## SQL 编写规范
- 关键字大写：`SELECT`, `FROM`, `WHERE`, `JOIN`
- 每条子句独占一行
- 使用参数化查询，禁止字符串拼接

```python
# ✅ 正确 — 参数化查询
sql = """
    SELECT problem_id, problem_num, problem, answer, difficulty, knowledge_point
    FROM problems
    WHERE difficulty = %s AND knowledge_point LIKE %s
    ORDER BY RAND()
    LIMIT %s
"""
cursor.execute(sql, (difficulty, f"%{kp}%", count))

# ❌ 错误 — 字符串拼接
sql = f"SELECT * FROM problems WHERE difficulty = '{difficulty}'"
```

## 数据库迁移
- 所有 schema 变更放在 `database/migrations/` 中
- 文件命名：`NNN_描述.sql`（如 `001_create_tables.sql`, `002_add_user_strength.sql`）
- 编号连续递增，不修改已有迁移文件
- 每个迁移包含注释说明：变更目的、影响范围、回滚方式
- `init_db.py` 按序执行所有迁移

## 备份与恢复
- 开发环境：`mysqldump wzyProjectDb > backup_YYYYMMDD.sql`
- 生产环境前需制定完整备份策略
