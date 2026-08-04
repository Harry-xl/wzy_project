---
name: 2026-08-03 PDF OCR工具开发与个人资料库PRD
description: 完成PDF OCR工具开发、自动化脚本、个人资料库需求文档；下一步进入技术设计和实施
metadata:
  type: project
---

## 本次会话完成的工作

### 1. PDF OCR 工具（已完成 ✅）

独立工具目录 `tools/pdf_ocr/`，将扫描版中文 PDF 转换为 Markdown + Word：

- **7 个源文件**：ocr_tool.py (CLI)、pdf_processor.py、ocr_engine.py、checkpoint.py、output_writer.py、ingest_to_rag.py、requirements.txt
- **5 个测试文件**：conftest + test_pdf_processor + test_ocr_engine + test_output_writer + test_checkpoint
- **测试结果**：51/51 全部通过
- **核心技术选型**：PyMuPDF (PDF渲染) + PaddleOCR (中文OCR) + python-docx (Word输出)
- **关键设计**：
  - 针对 400+ 页文档设计：每页保存进度、MD流式追加+fsync、50页清理PaddleOCR缓存、SIGINT优雅退出
  - 默认 200 DPI，预估 12-20 分钟处理 400 页
  - 断点续传：原子写入 .ocr_checkpoint.json，支持 --resume
  - DOCX 分卷：--split 100 每 100 页生成一个文件
  - Mini-batch 处理：batch_size=5，利用 PaddleOCR 内部并行

### 2. 自动化脚本（已完成 ✅）

- `setup.bat` — 一键安装环境（选择镜像源 → 安装依赖 → 运行测试）
- `run_ocr.bat` — 交互式 OCR 处理（支持拖拽 PDF，4 种模式选择）
- `run_full_pipeline.bat` — 全流程：OCR → RAG 入库（引导式配置）

### 3. RAG 集成文档（已完成 ✅）

- `tools/pdf_ocr/README.md` — 完整使用与集成指南
- `tools/pdf_ocr/ingest_to_rag.py` — OCR→RAG 入库脚本，5 步管线

### 4. 个人资料库 PRD（🟡 评审中）

文档：`docs/PRD-个人资料库.md`

**核心概念**：个人资料库 = 两个并列能力

| 能力 | 说明 | 关键功能 |
|------|------|---------|
| **能力A：知识整理可视化** | 帮用户直观理解资料 | 📋 知识清单（资料→知识点自动映射）、🗺️ 知识图谱（ECharts力导向图+覆盖热力图）、覆盖度环形图、推荐补充 |
| **能力B：RAG检索增强** | AI对话引用用户资料 | 检索范围切换（系统库/我的资料）、来源标注、后台异步处理 |

**MVP 范围确认**：
- 三种格式：扫描PDF(OCR) + 文字PDF(提取) + Word(提取)
- 上传→自动处理→知识清单+图谱→AI可问答，核心链路
- 后台异步处理 + SSE 进度推送
- 仪表盘新增「我的资料库」板块
- AI 对话检索范围手动切换

**技术要点**：
- 知识点自动映射：chunk → embedding → 与 71 个子知识点描述做余弦相似度 → 超阈值关联
- 知识图谱可视化：ECharts graph 类型（与现有仪表盘图表技术栈统一）
- knowledge_documents 增加 user_id 列区分个人/系统资料
- 新增 library_tasks 表追踪异步任务
- 8 项验收标准覆盖两个能力面

## 已确认的关键决策

1. PaddleOCR 作为中文 OCR 引擎（用户选定）
2. 个人资料库 MVP 含三种格式 + 两个能力面
3. 后台异步处理模式
4. 仪表盘新增板块作为反馈界面
5. AI 检索范围手动切换

## 下一步 (Phase 2 实施)

1. **PRD 评审通过后** → 技术设计（`.claude/templates/tech-spec-template.md`）
2. **数据库迁移**：`database/migrations/003_library.sql`
3. **后端 API**：新增 Flask Blueprint `server/library_api.py`
4. **前端页面**：仪表盘新增「我的资料库」板块
5. **AI 对话增强**：检索范围切换 + 来源标注
6. **知识图谱**：ECharts 可视化 + 知识点映射管线
7. **集成测试**：端到端验证上传→处理→知识清单→图谱→AI问答

## 关联记忆

- [[2026-08-02-phase1-implementation]] — Phase 1 知识库+RAG 基础设施
