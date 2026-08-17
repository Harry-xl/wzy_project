---
name: session-2026-08-06-textbook-reimport-and-export
description: 2026-08-06 会话 — 完整教材重新导入、多格式导出（MD/Word/PDF）、前端交互修复
metadata:
  type: project
---

# 2026-08-06 会话：教材重新导入 + 多格式导出 + 交互修复

## 会话目标

用户提供完整版《计算机网络（第8版）谢希仁》PDF（485页全可渲染），替换之前损坏版本，并给前端导出按钮增加 Word 和 PDF 格式。

## 已完成工作

### 1. 旧数据清理
- 删除 14 个旧 PDF 副本（`uploads/system/` + `uploads/1/` + `uploads/378/` + root `textbook.pdf`）
- ChromaDB 清空 190 条向量（metadata 损坏，全部 doc_id='unknown'）
- MySQL 清空 `knowledge_documents`(doc_id=14)、`knowledge_chunks`(190条)、`library_tasks`(1条)
- 手动启动 MySQL：`D:/Application/MySQL/MySQL Server 8.0/bin/mysqld.exe`（需注册表查询路径）

### 2. 教材上传与 OCR 处理
- 新 PDF 485 页全部可渲染（旧版仅 66 页），122MB → 128MB（略大）
- 上传 API：`POST /api/library/upload` → task_id=`8740f1d9...`
- OCR 引擎：EasyOCR + 250 DPI
- 处理时长：~3 小时（250 DPI 高精度，速度从 0.8 页/分钟逐步提升至 5 页/分钟）
- 结果：doc_id=15，1532 chunks，342 chunks 已映射知识点（50% 覆盖 71 子知识点）
- 中文标题在 MySQL 中正确存储为 `计算机网络（第8版）谢希仁`

### 3. RAG 检索验证
- 测试查询 "TCP三次握手的过程是什么"（`knowledge_scope=system`）
- 返回 5 个来源引用，相关度 0.741~0.805
- 来源正确标注为 `[计算机网络（第8版）谢希仁]`

### 4. 多格式导出功能（新增 Word + PDF）

**后端**（`server/library_api.py`）：
- 改造 `GET /api/library/documents/<doc_id>/export` 支持 `?format=md|docx|pdf`
- `_export_markdown()` — Markdown 文本导出（已有）
- `_export_docx()` — Word 文档导出（python-docx），自动识别章节标题，Microsoft YaHei 字体
- `_export_pdf()` — 文字版 PDF（fpdf2），使用 SimHei 中文字体，页眉页脚+页码

**依赖新增**：`fpdf2==2.8.7`（PDF生成）

**导出版本大小对比**（doc_id=15, 1532 chunks）：
| 格式 | 大小 |
|------|------|
| Markdown (.md) | 1.59 MB |
| Word (.docx) | 667 KB |
| PDF (.pdf) | 1.79 MB |

### 5. 前端交互修复

**导出按钮无反应** — 两个原因+修复：
- `window.open()` 被浏览器弹窗拦截 → 改用创建隐藏 `<a>` 元素 + `click()` 下载
- `DS.SysLibrary.loadDocuments()` 缺少导出事件绑定 → 补充完整绑定代码

**系统知识库删除按钮** — 按用户要求移除：
- 系统库文档卡片中移除 `<i class="ri-delete-bin-line">` 
- 系统库 `loadDocuments()` 中移除删除事件绑定

**文件改动**：
- `static/js/dashboard-library.js` — 导出下载方式、SysLibrary 事件绑定、移除删除按钮

### 6. fpdf2 安装排错
- 问题：`pip install fpdf2` 装到了另一个项目的 venv（`d:\2025_term1_latter\Python_programming\WeiZuyi_Project\.venv\`）
- 根因：pip 配置指向了错误的 site-packages
- 解决：`python.exe -m pip install fpdf2 --target=<正确路径>`

## 当前系统状态

| 组件 | 状态 |
|------|:--:|
| Flask API + MySQL | ✅ 运行中 |
| 系统知识库 | ✅ doc_id=15 计算机网络第8版 (485页, 1532 chunks) |
| ChromaDB 向量 | ✅ 1532 条已索引 |
| RAG 检索 | ✅ 正常工作，5源引用 |
| Markdown 导出 | ✅ |
| Word 导出 | ✅ |
| PDF 导出 | ✅ |
| 前端导出下拉菜单 | ✅ 三格式可选 |
| 系统库删除按钮 | 🚫 已移除 |

## 下次会话接入

1. 如有新版第7版教材 → 通过管理后台上传即可（覆盖当前）
2. 编写自动化测试（Phase 5）
3. 代码审查（Phase 6）
4. 端到端冒烟测试（11 条验收标准）

**Why:** 本次会话完成了完整教材的重新导入（替代损坏版本）并验证了 RAG 系统正常工作。为前端导出按钮增加了 Word 和 PDF 两种导出格式，修复了导出按钮无响应和系统库删除权限问题。
**How to apply:** 下次会话应首先确认系统运行状态，然后推进 Phase 5 测试编写。参考 [[session-2026-08-05-textbook-ocr-and-fixes]] 了解上次教材导入背景，参考 [[session-2026-08-04-library-implementation]] 了解架构全貌。
