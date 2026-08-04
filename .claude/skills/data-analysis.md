# Skill: 数据分析 (data-analysis)

> 查询和分析项目数据，生成洞察报告

## 适用场景
- 用户行为分析
- 学习效果评估
- 题库质量审查
- 系统使用统计

## 工作流程

### 第一步：明确分析目标
- 要回答什么问题？
- 需要哪些数据？
- 时间范围？

### 第二步：查询数据
直接连接数据库执行查询：
```python
from src.shared.database import get_connection

conn = get_connection()
cursor = conn.cursor(dictionary=True)
# 执行分析查询
```

### 第三步：生成分析报告
格式：
```markdown
## 数据分析报告：<主题>
日期: YYYY-MM-DD

### 关键发现
1. 发现一
2. 发现二

### 详细数据
| 指标 | 数值 |
|------|------|
| xxx  | xxx  |

### 建议
- 建议一
- 建议二
```

### 常见分析查询模板

**用户活跃度**：
```sql
SELECT DATE(answer_time) as date,
       COUNT(DISTINCT user_id) as active_users,
       COUNT(*) as total_answers
FROM user_answers
WHERE answer_time >= DATE_SUB(NOW(), INTERVAL 30 DAY)
GROUP BY DATE(answer_time)
ORDER BY date;
```

**知识点难度分布**：
```sql
SELECT knowledge_point, difficulty, COUNT(*) as cnt
FROM problems
GROUP BY knowledge_point, difficulty
ORDER BY knowledge_point, FIELD(difficulty, '简单','中等','困难');
```

**用户进步趋势**：
```sql
SELECT u.name, COUNT(ua.answer_id) as total,
       SUM(ua.is_correct) as correct,
       ROUND(SUM(ua.is_correct) / COUNT(ua.answer_id) * 100, 1) as accuracy
FROM user u
JOIN user_answers ua ON u.user_id = ua.user_id
WHERE ua.answer_time >= DATE_SUB(NOW(), INTERVAL 7 DAY)
GROUP BY u.user_id
ORDER BY accuracy DESC;
```
