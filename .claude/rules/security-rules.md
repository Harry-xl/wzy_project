# 安全规范

## 密钥管理
- **所有密钥必须来自环境变量**，绝不在代码中硬编码
- `.env` 文件必须在 `.gitignore` 中
- 提供 `.env.example` 作为模板（含空值或占位符）
- 敏感信息清单：
  - `DEEPSEEK_API_KEY` — DeepSeek API 密钥
  - `MYSQL_PASSWORD` — 数据库密码
  - `FLASK_SECRET_KEY` — Flask session 签名密钥（如使用 session）

```python
# ✅ 正确
import os
API_KEY = os.getenv("DEEPSEEK_API_KEY")
if not API_KEY:
    raise RuntimeError("DEEPSEEK_API_KEY 未设置")

# ❌ 错误
API_KEY = "sk-abc123def456"  # 硬编码！
```

## 密码安全
- 使用 Werkzeug `generate_password_hash` (PBKDF2-SHA256)
- 验证使用 `check_password_hash`
- 兼容历史明文密码：首次登录时自动迁移为哈希
- 密码强度：最小 6 字符（当前），建议升级为 8 字符+复杂度要求

```python
from werkzeug.security import generate_password_hash, check_password_hash

# 存储密码
hashed = generate_password_hash(password, method='pbkdf2:sha256')

# 验证密码
if check_password_hash(stored_hash, input_password):
    # 登录成功
```

## SQL 注入防护
- 100% 使用参数化查询
- 禁止任何形式的字符串拼接/格式化构造 SQL
- 动态表名/列名需求：使用白名单验证

```python
# ✅ 正确
cursor.execute("SELECT * FROM user WHERE email = %s", (email,))

# ❌ 错误
cursor.execute(f"SELECT * FROM user WHERE email = '{email}'")
cursor.execute("SELECT * FROM user WHERE email = '%s'" % email)
```

## 输入验证
- API 入口处验证所有用户输入
- 邮箱格式验证
- 字符串长度限制（name ≤ 255, answer ≤ 500）
- 数字范围验证（count: 1-50, user_id: > 0）
- HTML/JS 注入防护：前端渲染时转义用户输入

```python
# 路由层验证
data = request.json
if not data:
    return jsonify({"success": False, "message": "请求体为空"}), 400

name = data.get('name', '').strip()
if len(name) < 1 or len(name) > 255:
    return jsonify({"success": False, "message": "昵称长度不合法"}), 400

import re
if not re.match(r'^[^@]+@[^@]+\.[^@]+$', data.get('email', '')):
    return jsonify({"success": False, "message": "邮箱格式不对"}), 400
```

## 错误信息安全
- 客户端错误：返回通用消息，不暴露内部细节
- 服务端错误：返回「服务暂时不可用」，gai详细日志写服务端
- 登录失败不提示「用户不存在」vs「密码错误」（防用户枚举）

## CORS
- 开发环境：`Access-Control-Allow-Origin: *`
- 生产环境：限制为具体前端域名
- 如引入 Session/Token 认证：添加 `Access-Control-Allow-Credentials: true`

## 依赖安全
- 定期检查 `requirements.txt` 中依赖的已知漏洞
- `pip list --outdated` 检查过期包
- 生产部署前运行 `safety check` 或 `pip-audit`

## 数据保护
- 日志中不打印密码（明文或哈希）
- 日志中不打印完整的 API Key
- 用户数据导出/删除需确认身份
