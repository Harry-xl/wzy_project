---
name: session-2026-08-03-bugfix-ai-features
description: 2026-08-03 会话记录 — 排查并修复 AI 讲解和 AI 伴学功能不可用的 4 个 bug
metadata:
  type: project
---

# 2026-08-03 会话：AI 功能 Bug 修复

## 问题描述

用户反馈：错题本的 AI 讲解功能和 AI 伴学的对话功能均不可用。

## 排查过程

### 第一步：验证后端

用 Python `requests` 和 `curl` 直接调用后端 API，全部正常：
- `POST /api/explain` — 200，返回 3200+ 字讲解
- `POST /api/explain/stream` — 200，2747 行 SSE 正常推送
- `POST /api/chat` — 200，1698 个 SSE chunks 正常返回
- `GET /api/knowledge/search` — RAG 检索正常
- CORS 预检 OPTIONS — 返回正确跨域头
- 全部 7 个 JS 文件和 CDN 资源均 200

结论：**后端 100% 正常，问题在前端**。

### 第二步：创建诊断页面

创建 `static/test_api.html`，5 个按钮直接调用 API。用户反馈全部返回 200——确认 API 可从前端访问，问题在 dashboard 代码。

## 修复的 4 个 Bug

### Bug 1：CORS Authorization 头冲突

**文件**：`static/js/api.js` — `chatStream()` 方法

**现象**：登录用户聊天功能不可用。

**根因**：`chatStream()` 在登录用户时会添加 `Authorization: Bearer <email>` 头。后端 CORS 配置为 `Access-Control-Allow-Origin: *`。根据 CORS 规范，`*` 通配符不允许携带认证信息（Authorization 头），浏览器会直接拒绝请求。

**修复**：移除 `Authorization` 头（后端不使用它做认证），改为普通跨域请求。

### Bug 2：Chat init() 竞态条件

**文件**：`static/js/dashboard-chat.js`

**现象**：AI 伴学发送按钮点击无任何反应，控制台无报错。

**根因**：HTML 脚本加载顺序：
```html
<script src="js/dashboard.js"></script>        <!-- line 323: 调用 DS.Chat.init() -->
<script src="js/dashboard-chat.js"></script>    <!-- line 327: 注册 DS.Chat = {init, sendMessage} -->
```
`dashboard.js` 先加载，其 IIFE 中 `DS.Chat.init()` 执行时 `DS.Chat` 尚为 `undefined`，调用被跳过。`dashboard-chat.js` 后加载，注册了 `DS.Chat` 但未主动调用 `init()`。事件监听器从未绑定。

**修复**：在 `dashboard-chat.js` 末尾 `DS.Chat = { init, sendMessage }` 之后立即调用 `init()`。

### Bug 3：Flask 单线程阻塞

**文件**：`server/app.py` — `app.run()` 调用

**现象**：AI 讲解请求挂起（"正在生成讲解..." 之后无反应）。

**根因**：`debug=True` 时 Flask 开发服务器默认为**单线程**。流式 API（如 explain/stream）占住唯一线程后，后续请求（包括同一个 explain 请求中 RAG 内部的 ChromaDB 操作）被阻塞。

**修复**：`app.run()` 添加 `threaded=True`。

### Bug 4：typewriterRender typing 标志 bug

**文件**：`static/js/dashboard-wrong.js` — `typewriterRender()` 函数

**现象**：AI 讲解显示"正在生成讲解…"后不再更新。用户看到初始提示文字但看不到后续内容。

**根因**：打字机效果的状态机 bug：
```
1. 首个 SSE 事件到达 → typing=true, tick() 启动
2. 初始短内容（"正在生成讲解…"的下一帧）快速打完
3. buffer 为空 → tick() 停止，但 typing 仍为 true
4. 后续 SSE 事件到达 → if (!typing) 永远为 false
5. tick() 无法重启 → buffer 堆积，页面无变化
```

**修复**：`tick()` 中 buffer 清空时将 `typing` 重置为 `false`：
```javascript
} else {
    typing = false;  // 缓冲区已空，允许新内容重启打字
}
```

## 最终状态

| 功能 | 状态 |
|------|------|
| AI 伴学（聊天） | ✅ 已确认可用 |
| AI 讲解（错题） | ✅ 已修复，待用户验证 |
| 知识库检索 | ✅ 正常 |
| 后端 API | ✅ 全部正常 |

## 本次修改的文件清单

| 文件 | 修改内容 |
|------|---------|
| `static/js/api.js` | 移除 chatStream 中的 Authorization 头 |
| `static/js/dashboard-chat.js` | 末尾补调 init()；添加 console.error 日志；修复 finishReply sources 保存 |
| `static/js/dashboard-wrong.js` | 修复 typewriterRender typing 标志 bug；添加 console.error 日志 |
| `server/app.py` | `app.run()` 添加 `threaded=True` |
| `static/test_api.html` | 新增：API 诊断页面 |

## 新增诊断工具

`static/test_api.html` — 5 个按钮独立测试每个 API 端点。下次如遇类似问题，首先打开此页面排查。

## Why

本次会话投入大量时间排查前端 bug，根因分散在 CORS 规范、JS 模块加载顺序、Flask 线程模型、打字机状态机 4 个不同层面。修复后 AI 伴学已确认可用，AI 讲解修复完待用户验证。

## How to apply

下次会话时，AI 应：
1. 首先确认用户是否已验证 AI 讲解可用
2. 如仍有问题，打开 `test_api.html` 诊断
3. 参考 [[session-2026-08-02-phase1-implementation]] 了解项目当前架构
