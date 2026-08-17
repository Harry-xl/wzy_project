---
name: session-2026-08-07-learning-card-debug
description: 学习卡片 404 调试 — 修复导入bug、发现迁移未执行、多进程端口冲突
metadata:
  type: project
---

## 背景

v0.3.0 知识库学习呈现功能实施完成后，用户测试时浏览器报 404 错误：
`GET http://127.0.0.1:3001/api/library/learning-card?sub_topic_id=1&user_id=378 404 (NOT FOUND)`

## 发现的 3 个问题

### Bug 1: 导入错误 (library_api.py:1067)

`generate_readable` 端点中使用了错误的导入：
```python
from AI_operate.deepseek_chat import chat_with_deepseek  # ❌ 无法导入
```
`chat_with_deepseek` 是 `deepseek_chat` 类的实例方法，不能直接从模块导入。

**修复**：改为 `from AI_operate.deepseek_chat import deepseek_chat as _dc`，调用 `_dc.chat_with_deepseek(prompt)`。

### Bug 2: 迁移 005 未执行

数据库 `knowledge_sub_topics` 有 72 行数据（正常），但 `knowledge_learning_cards` 表不存在。

**原因**：`init_db.py` 中注册了迁移 005，但用户尚未执行 `python database/init_db.py`。

**影响**：卡片无法缓存到 MySQL（每次访问都重新调 DeepSeek 生成），但不影响卡片生成和返回——`get_card()` 在 `_save_card` 失败时仍能正常返回生成的卡片内容。

**修复**：运行 `python database/init_db.py`。

### Bug 3: 多进程端口冲突（根因）

两台 Python 进程同时监听 3001 端口：
- PID 22852（系统 Python `D:\Application\Python11_6\`）— 2026/8/6 启动，旧代码
- PID 34144（venv Python）— 2026/8/7 启动，新代码

旧进程持有端口并处理所有请求，新进程的 14 个端点无法生效。请求 `/api/library/learning-card` 命中 `app.py:1095` 兜底路由 `/<path:any_path>`，返回 `{"success": false, "message": "Not Found"}`。

**诊断方法**：对比运行中服务器和源代码的端点列表发现不一致；用 `netstat -ano` 和 `Get-Process` 定位多个 Python 进程。

**修复**：`taskkill /F /IM python.exe` 后重启。

## 调试过程中的关键发现

1. 兜底路由 `app.py:1095 @app.route('/<path:any_path>')` 返回 `{"message": "Not Found"}` 而非 library_api 的 `{"message": "知识点不存在"}` → 说明请求未到达 blueprint 处理器
2. `/api/library/documents` 等老端点正常工作但新端点全部 404 → 说明服务器运行的是旧版本 library_api.py
3. `get_card(sub_topic_id, user_id)` 直接调用测试完全正常 → 确认问题在 HTTP 路由层而非业务逻辑层
4. `knowledge_sub_topics` 表有 72 行，`sub_topic_id=1` 存在 → 确认种子数据正常（来自 `scripts/seed_knowledge.py`）

## 后续建议

- 在 `run_all.bat` 中添加启动前检查是否有旧进程占用端口
- 考虑在 Flask 启动时打印 PID 和启动时间戳，便于诊断多进程问题