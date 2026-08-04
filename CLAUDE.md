# StarPal (星伴) — AI 开发指南

> AI 入口文件：每次会话开始时自动加载。本文件告诉 AI 这个项目是什么、怎么跑、规矩是什么。

---

## 项目身份 (Project Identity)

- **名称**：StarPal (星伴) — 计算机网络智能刷题 + AI 辅导平台
- **使命**：帮助计算机网络学习者通过智能刷题和 AI 辅导高效备考
- **用户**：中国计算机专业学生
- **语言规范**：代码标识符用英文，文档/注释可用中文，面向用户的内容用中文
- **版本**：0.3.0（知识库+RAG 已集成，Phase 1 完成）

---

## 技术栈 (Tech Stack)

| 层级 | 技术 | 说明 |
|------|------|------|
| 后端框架 | Python 3.11 + Flask 2.0.1 | REST API，端口 3001 |
| 数据库 | MySQL 8.x | 数据库名 `wzyProjectDb`，连接池 size=5 |
| 数据库驱动 | mysql-connector-python 8.0.26 | |
| 密码安全 | Werkzeug 2.2.3 | PBKDF2-SHA256 哈希 |
| AI 模型 | DeepSeek Chat API | 同步 + SSE 流式两种调用方式 |
| 前端 | 原生 HTML/CSS/JS | 无框架，ES6 类，iframe 嵌入架构 |
| 前端图标 | RemixIcon | 开源图标库 |
| Markdown | marked.js + Prism.js + KaTeX | 代码高亮 + 数学公式渲染 |

---

## 项目架构 (Architecture)

```
浏览器 (http://127.0.0.1:8888)
  ├── login.html            → 入口：登录/注册
  ├── dashboard.html        → 主仪表盘（iframe 容器）
  │   ├── exam.html         → 做题 iframe
  │   ├── (内联)            → 能力画像（雷达图/条形图/环形图）
  │   ├── (内联)            → 错题管理
  │   └── chat.html         → AI 对话 iframe
  ├── exam.html             → 独立做题页
  ├── chat.html             → 独立聊天页
  └── admin.html            → 管理后台
         │
         ▼ HTTP API (port 3001)
  Flask (server/app.py)
         │
    ┌────┴──────────┐
    ▼                ▼
  MySQL 8.x      DeepSeek API
  wzyProjectDb   (deepseek-chat)
```

**数据库表**（5 张）：`user`, `problems`, `ability_profile`, `user_answers`, `learning_sessions`

**核心业务流**：
```
登录 → 个性化选题（70%弱点 + 30%强点）→ 答提交 → 
自动流水线（记录答题 → 更新画像 → 聚合会话 → 刷新实力）
→ 查看画像/AI分析 → 错题重做/AI讲解 → AI 对话辅导
```

---

## 启动方式 (How to Run)

### 环境要求
- Python 3.11+
- MySQL 8.x（本地运行，默认端口 3306）
- Windows 操作系统

### 一键启动
```bash
run_all.bat
```
该脚本依次：激活 venv → 安装依赖 → 初始化数据库 → 启动 Flask (3001) → 启动静态服务 (8888)

### 手动启动
```bash
pip install -r requirements.txt
python database/init_db.py
python server/app.py                          # 终端1: Flask API
python -m http.server 8888 --directory static  # 终端2: 静态文件
```
浏览器打开 `http://127.0.0.1:8888/login.html`

---

## 关键约定 (Key Conventions)

### 代码组织
- `server/app.py` — Flask 主后端（1373 行，当前为单文件，计划拆分为蓝图架构）
- `AI_operate/` — AI 业务逻辑模块（选题策略、能力画像、DeepSeek 封装）
- `database/` — 数据库层（连接池、DDL、初始化脚本）
- `deepseek_importer/` — DOCX 题目批量导入工具（支持断点续传）
- `static/` — 前端静态资源（HTML + JS + CSS + assets）

### 编码规范（详见 `.claude/rules/`）
- **Python**：PEP 8，类型提示，snake_case，Google 风格 docstring
- **JavaScript**：ES6+，const/let（禁用 var），ES6 class，camelCase
- **CSS**：kebab-case，CSS 变量定义色板，4px 间距基元
- **API**：RESTful，`/api/<resource>`，响应格式 `{ success, data?, message?, error? }`
- **数据库**：InnoDB + utf8mb4，主键 `<table>_id`，参数化查询
- **安全**：密钥来自环境变量，密码 PBKDF2-SHA256，SQL 参数化，输入验证

### 禁止事项 (DO NOT)
- ❌ **绝不硬编码密钥**（API Key、数据库密码）→ 使用环境变量
- ❌ **绝不提交** `.env`、`.venv/`、`__pycache__/`
- ❌ **绝不使用** `server/auth.js` 和 `server/index.js`（旧 Express 版本，已废弃）
- ❌ **绝不裸写 SQL 字符串拼接** → 始终使用参数化查询
- ❌ **绝不在错误响应中暴露堆栈信息** → 返回通用错误消息

---

## 待处理问题 (Known Issues)

1. **硬编码密钥**：`AI_operate/deepseek_chat.py` 和 `server/app.py` 中存在硬编码 API Key 和数据库密码
2. **单文件后端**：`server/app.py` 1373 行，需拆分为 routes/services/models 分层
3. **无自动化测试**：零测试覆盖
4. **无 Git 版本控制**：尚未初始化仓库
5. **废弃代码**：`server/auth.js` 和 `server/index.js` 是旧 Express 版本
6. **测试数据不匹配**：`insert_test_data.sql` 是 C 语言题，与计算机网络主题不符
7. **前端无构建工具**：原生 JS 无打包/压缩/TypeScript
8. **CORS 宽松**：全局 `Access-Control-Allow-Origin: *`

---

## 关联文件

- AI 领域规则 → `.claude/rules/`（编码/安全/测试/API/数据库/Git/需求工程 等 10 个规范文件）
- AI 技能 → `.claude/skills/`（添加功能/修复Bug/写测试/代码审查/重构等 10 个工作流）
- AI Agent → `.claude/agents/`（架构师/后端/前端/测试/审查/需求分析 6 个角色）
- 文档模板 → `.claude/templates/`（PRD/技术规格/代码审查清单/测试计划/发布清单/任务分解）
- 项目文档 → `项目文档.md`（完整中文项目文档，801 行）
- 项目配置 → `.claude/settings.local.json`
- 会话记忆 → `memory/`（历次开发会话记录，新会话应首先读取 `memory/MEMORY.md`）
- 需求文档 → `docs/PRD-智能助学升级.md`（Phase 1-4 完整规划）

## 最近重大变更 (v0.3.0)

**2026-08-02：知识库 + RAG 系统集成（Phase 1 完成）**
- 新增 ChromaDB 向量数据库（32 个知识块已索引）
- 新增 RAG 检索增强生成管道（`AI_operate/rag_service.py`）
- 新增文本嵌入服务（本地 sentence-transformers 模型，HF 镜像）
- 新增 5 个知识库 API 端点（`/api/knowledge/*`）
- 改造 `/api/chat`、`/api/explain` 支持 RAG（可溯源回答）
- 新增 4 张数据库表 + 种子数据（71 子知识点, 47 关系, 12 文档）
- 前端新增来源引用卡片展示
- 详见 `memory/session-2026-08-02-phase1-implementation.md`
