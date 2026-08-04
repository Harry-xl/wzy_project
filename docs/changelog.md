# 更新日志 (Changelog)

---

## v0.3.0 (2026-08-03)

### 🧠 知识库 + RAG 智能助学升级 (Phase 1)
- 新增 ChromaDB 向量数据库（嵌入式，32个知识块已索引）
- 新增 RAG 检索增强生成管道（`AI_operate/rag_service.py`）
- 新增文本嵌入服务（本地 sentence-transformers 模型，384维）
- MySQL 新增 4 张知识表（documents/chunks/sub_topics/relations）
- 种子数据：71子知识点、47知识关系、12篇文档、32知识块
- 新增 5 个知识库 API 端点（`/api/knowledge/*`）
- 改造 `/api/chat`、`/api/explain` 支持 RAG（可溯源回答）
- 前端新增来源引用卡片展示
- 新增全局配置模块 `server/config.py`

### 🧪 测试与运维
- 新增 `scripts/verify_rag.py` 一键验证脚本（39项检查，7层覆盖）
- 新增 `docs/知识库RAG系统-操作指南.md` 完整操作文档
- 修复 `chat.js` + `renderer.js` RAG来源显示

---

## v0.2.6 (2026-08-01)

### 🏗️ 工程化
- 初始化 Git 版本控制
- 创建 `.gitignore`、`.env.example`、`.editorconfig`
- 创建 `.claude/` AI 开发基础设施（rules/skills/agents/templates/prompts）
- 创建项目根目录 `CLAUDE.md`（AI 开发指南）
- 新增 10 个领域规则文件（编码/API/数据库/安全/测试/Git/错误处理/需求工程）
- 新增 10 个可复用 AI 技能定义
- 新增 6 个专用 Agent 角色配置
- 新增 6 个文档模板（PRD/技术规格/代码审查清单/测试计划/发布清单/任务分解）
- 创建模块化文档目录 `docs/`（架构/API参考/数据库/前端/部署/变更日志）
- 搭建 pytest 测试框架基础设施
- 创建 `scripts/` 运维脚本目录
- 新增 `requirements-dev.txt`（pytest, black, isort）

---

## v0.2.5 (2026-07-29)

### 功能
- ✅ 用户注册/登录（PBKDF2-SHA256 密码哈希 + 明文密码兼容迁移）
- ✅ 游客随机做题模式
- ✅ 登录用户个性化选题（70%弱点 + 30%强点）
- ✅ 按知识点/难度筛选题目
- ✅ 提交答案自动判题
- ✅ 能力画像系统（熟练度更新 + 雷达图/条形图/环形图可视化）
- ✅ AI 分析报告（DeepSeek 生成个性化学习建议）
- ✅ 用户实力趋势折线图
- ✅ 错题本（分页浏览、排序、错题重做、同知识点/同难度重练）
- ✅ AI 流式讲解（打字机效果，SSE 流式传输）
- ✅ AI 伴学对话（计算机网络助教角色，多轮对话，Markdown+代码高亮+KaTeX 公式）
- ✅ 管理后台（题目 CRUD、JSON 批量导入、统计面板）
- ✅ 后台自动清理过期数据（守护线程，每小时）
- ✅ 学习会话自动聚合（24h 窗口）
- ✅ DOCX 题目批量导入工具（LLM 解析 + 断点续传）
- ✅ 一键启动脚本（run_all.bat）

### 技术细节
- 后端：Python 3.11 + Flask 2.0.1
- 数据库：MySQL 8.x，5 张表（user, problems, ability_profile, user_answers, learning_sessions）
- AI 模型：DeepSeek Chat API（同步 + SSE 流式）
- 前端：原生 HTML/CSS/JS，iframe 嵌入架构，RemixIcon 图标，marked.js + Prism.js + KaTeX
- 密码安全：Werkzeug PBKDF2-SHA256
- CORS：全局 `*`（开发环境）
