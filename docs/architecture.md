# 星伴 (StarPal) — 系统架构文档

> 版本: 0.2.6 | 更新: 2026-08-01

---

## 系统概述

星伴是一个计算机网络主题的智能刷题 + AI 辅导平台，采用前后端分离的轻量架构。

---

## 架构图

```
┌─────────────────────────────────────────────────┐
│                    浏览器                        │
│  login.html → dashboard.html (iframe 容器)      │
│  ├── exam.html (做题 iframe)                     │
│  ├── (内联) 能力画像 / 错题管理                  │
│  └── chat.html (AI 对话 iframe)                  │
│  + exam.html / chat.html / admin.html (独立页面)  │
└──────────────┬──────────────────────────────────┘
               │ HTTP REST API (port 3001)
               │ SSE Stream (AI 讲解/对话)
               ▼
┌─────────────────────────────────────────────────┐
│              Flask 后端 (server/app.py)           │
│  ┌──────────┐ ┌──────────┐ ┌────────────────┐  │
│  │ 认证模块  │ │ 题目模块  │ │  AI 模块       │  │
│  │ signup   │ │ problems │ │ explain/stream  │  │
│  │ login    │ │ submit   │ │ chat (SSE)      │  │
│  └──────────┘ └──────────┘ └────────────────┘  │
│  ┌──────────┐ ┌──────────┐ ┌────────────────┐  │
│  │ 画像模块  │ │ 错题模块  │ │  管理后台       │  │
│  │ profile  │ │ wrong    │ │ admin CRUD      │  │
│  │ trend    │ │ redo     │ │ import/export   │  │
│  └──────────┘ └──────────┘ └────────────────┘  │
│  ┌──────────────────────────────────────────┐   │
│  │     后台清理守护线程 (每小时)              │   │
│  └──────────────────────────────────────────┘   │
└──────┬────────────────────┬─────────────────────┘
       │                    │
       ▼                    ▼
┌─────────────┐   ┌─────────────────┐
│  MySQL 8.x  │   │  DeepSeek API   │
│ wzyProjectDb│   │  deepseek-chat  │
│  5 张表      │   │  同步 + SSE 流式 │
└─────────────┘   └─────────────────┘
```

---

## 核心模块

### 后端模块

| 模块 | 文件 | 职责 |
|------|------|------|
| 认证 | `app.py` (login/signup) | 注册、登录、密码哈希、明文兼容迁移 |
| 题目 | `app.py` (problems) | 游客随机选题、登录用户个性化推荐、知识点筛选 |
| 答题 | `app.py` (submit_answer) | 判题、画像更新、会话聚合、实力刷新 |
| 画像 | `app.py` (profile) | 能力画像查询、实力趋势、AI 分析报告 |
| 错题 | `app.py` (wrong_answers) | 错题分页、排序、重做选题 |
| AI | `app.py` (explain/chat) | 同步讲解、流式讲解、流式对话 |
| 管理 | `app.py` (admin) | 题目 CRUD、批量导入、统计面板 |
| 选题引擎 | `AI_operate/exam.py` | 个性化推荐策略（70%弱点+30%强点） |
| 画像系统 | `AI_operate/Ability_Profile.py` | 熟练度更新、会话聚合、实力计算 |
| LLM 封装 | `AI_operate/deepseek_chat.py` | DeepSeek API 调用（同步+流式） |
| 数据库连接 | `database/db_connector.py` | 连接池管理（size=5） |
| 数据导入 | `deepseek_importer/` | DOCX → LLM 解析 → 数据库（断点续传） |

### 前端模块

| 页面 | 文件 | 职责 |
|------|------|------|
| 登录 | `login.html` + `auth.js` | 登录/注册翻转卡片 UI |
| 仪表盘 | `dashboard.html` + `dashboard.js` | iframe 容器 + 模块切换 + 跨模块通信 |
| 做题 | `exam.html` + `exam.js` | 题目展示、答案提交、AI 讲解流式渲染 |
| 聊天 | `chat.html` + `chat.js` | AI 多轮对话、SSE 打字机效果、历史管理 |
| 管理 | `admin.html` + `admin.js` | 题目 CRUD、批量导入、统计面板 |
| 渲染 | `renderer.js` | Markdown + Prism.js 代码高亮 + KaTeX 公式 |

---

## 数据流

### 答题流程
```
用户选择答案 → POST /api/submit_answer
  → 判题（对比正确答案）
  → 流水线（非阻塞）:
      ├── 记录答题 (user_answers) ← 核心步骤，立即 commit
      ├── 更新能力画像 (ability_profile) ← 失败不阻塞
      ├── 聚合学习会话 (learning_sessions) ← 失败不阻塞
      └── 更新用户实力 (user.user_strength) ← 失败不阻塞
  → 返回判题结果 + 正确答案
```

### AI 讲解流程
```
前端发起 → POST /api/explain/stream
  → 构建 Prompt（含题目、知识点、难度、用户答案、正确答案）
  → DeepSeek API (stream=True)
  → SSE 逐块返回 → 前端 ReadableStream 打字机渲染
```

---

## 设计决策

### 为什么不用前端框架？
- 项目规模适中，原生 JS 够用
- 降低学习门槛（目标用户是学生，开发维护者也可能非专业前端）
- 无构建工具链，即改即刷新

### 为什么用 iframe 嵌入架构？
- 模块隔离：做题和聊天可独立打开
- 懒加载：首次切换到该模块时才加载
- 跨页面通信：通过 postMessage 实现仪表盘和各模块的数据交互

### 为什么 DeepSeek？
- 中文能力强，适合计算机网络教学场景
- API 兼容 OpenAI 格式，切换成本低
- 成本适中
