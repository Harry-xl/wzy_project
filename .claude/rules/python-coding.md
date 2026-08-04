# Python 编码规范

## 代码风格
- 严格遵循 PEP 8 规范
- 缩进：4 个空格（禁止 Tab）
- 行宽：最大 100 字符
- 文件末尾留一个空行

## 命名约定
- 模块/文件：snake_case（如 `exam_service.py`）
- 类名：PascalCase（如 `AbilityProfile`）
- 函数/方法：snake_case（如 `get_personalized_problems`）
- 变量：snake_case（如 `user_id`, `knowledge_point`）
- 常量：UPPER_SNAKE_CASE（如 `MAX_POOL_SIZE`, `CLEANUP_INTERVAL_SECONDS`）
- 私有成员：前缀单下划线（如 `_fetch_candidates`）

## 类型提示
- 所有函数签名必须包含类型提示
- 使用 `typing` 模块：`List`, `Dict`, `Optional`, `Tuple`, `Union`

```python
from typing import List, Dict, Optional, Tuple

def get_personalized_problems(
    user_id: int,
    count: int = 5,
    stale_days: int = 30
) -> List[Dict[str, object]]:
    """根据用户能力画像推荐个性化题目。

    Args:
        user_id: 用户 ID
        count: 题目数量，默认 5，最大 50
        stale_days: 久未做阈值天数

    Returns:
        题目列表，每项包含 problem_id, problem_num, problem, answer 等字段
    """
    ...
```

## 导入顺序
```python
# 1. 标准库
import json
import threading
from datetime import datetime, timedelta

# 2. 第三方库
from flask import Blueprint, request, jsonify

# 3. 本地模块（使用绝对导入）
from src.shared.database import get_connection
from src.server.services.exam_service import get_personalized_problems
```

## 错误处理
- 使用具体的异常类型，禁止 `except:`
- API 层：try/except 返回结构化 JSON 错误
- 服务层：抛出自定义异常，由路由层捕获
- 始终记录错误日志，但不暴露堆栈给客户端

```python
# ✅ 正确
try:
    result = db.query(sql, params)
except mysql.connector.Error as e:
    logger.error(f"数据库查询失败: {e}")
    return jsonify({"success": False, "message": "服务暂时不可用"}), 500

# ❌ 错误
try:
    result = db.query(sql, params)
except:
    return "error"
```

## 日志
- `print()` 仅用于启动信息（端口号、配置摘要）
- 运行时日志使用 `logging` 模块
- AI/LLM 调用必须记录：请求时间、Token 用量、延迟

## 数据库操作
-  使用参数化查询，禁止字符串拼接 SQL
- 连接从连接池获取，用完立即释放（使用 `with` 或 try/finally）
- 长事务避免，单个请求中尽量只提交一次

## 配置管理
- 所有敏感配置来自环境变量
- 提供合理的默认值
- 使用 `os.getenv("KEY", default)` 模式
