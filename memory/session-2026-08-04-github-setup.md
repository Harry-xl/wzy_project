---
name: session-2026-08-04-github-setup
description: GitHub 仓库创建、密钥清理、.env 配置 — 项目首次推送到远程
metadata:
  type: project
---

# 2026-08-04 GitHub 仓库初始化与密钥清理

## 完成事项

### 1. Git 配置与初始提交
- 配置用户：`harry-xl` / `3387244788@qq.com`
- 初始提交：150 文件，27433 行代码（v0.3.0）
- 分支改名 `master` → `main`

### 2. GitHub 远程仓库
- **仓库地址**：[https://github.com/Harry-xl/wzy_project](https://github.com/Harry-xl/wzy_project)
- 远程名：`origin`，分支跟踪已设置

### 3. 密钥清理（8 个文件，7+ 处硬编码）
修改以下文件，将硬编码密钥改为 `os.getenv()` 读取：

| 文件 | 清理内容 |
|------|---------|
| `AI_operate/deepseek_chat.py` | DeepSeek API Key |
| `server/config.py` | DeepSeek API Key + MySQL 密码 + 新增 `load_dotenv()` |
| `server/app.py` | MySQL 密码 + 新增 `load_dotenv()` |
| `deepseek_importer/config.py` | DeepSeek API Key + MySQL 密码 |
| `database/db_connector.py` | MySQL 密码 |
| `database/init_db.py` | MySQL 密码 |
| `database/update_user_strength.py` | MySQL 密码 |
| `check_db_performance.py` | MySQL 密码 |

### 4. .env 文件
- 创建 `.env`（gitignore 保护），含开发用真实密钥
- `server/config.py` 和 `server/app.py` 启动时通过 `python-dotenv` 自动加载

## 当前提交历史
1. `42f3b99` — feat: 初始版本 v0.3.0
2. `4949e07` — fix: 添加 load_dotenv() 自动加载 .env

## 注意事项
- `.env` 文件不要删除，否则应用无法连接数据库和 DeepSeek API
- 新脚本如需读取配置，在顶部加 `from dotenv import load_dotenv; load_dotenv()`
- 旧的 `server/auth.js` 和 `server/index.js`（Express 版本）仍在仓库中，已废弃

**Why:** 项目首次推送到 GitHub，此前代码中存在多处硬编码密钥（项目已知问题 #1），GitHub push protection 拦截了推送。

**How to apply:** 后续开发中新增密钥配置一律使用 `os.getenv()` + `.env` 模式，`.env.example` 同步更新。新脚本启动时调用 `load_dotenv()`。
