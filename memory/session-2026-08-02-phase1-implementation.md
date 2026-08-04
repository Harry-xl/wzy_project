---
name: session-2026-08-02-phase1-implementation
description: 2026-08-02 会话完整记录 — Phase 1 知识库+RAG 实施全过程、技术决策、已完成工作、待办事项
metadata:
  type: project
---

# 2026-08-02 会话：Phase 1 知识库 + RAG 智能助学升级实施

## 会话背景

用户要求围绕"助学场景"（学习路径规划、知识问答与讲解、学习过程陪伴）和三大技术（知识库构建、模型微调、RAG）对现有 StarPal 项目进行需求分析和实施。

## 已完成的核心工作

### 1. 项目全面分析 + PRD 生成
- 深入分析了项目现有状态（1374 行 Flask 后端、5 张数据库表、6 个前端页面、8 个 AI 模块）
- 生成了完整 PRD：[docs/PRD-智能助学升级.md](docs/PRD-智能助学升级.md)
- PRD 包含 6 大模块、30+ 功能点、4 个实施阶段

### 2. 6 项关键决策确认（见 PRD 1.3 节）
| # | 决策 | 结论 |
|---|------|------|
| 1 | 核心知识源 | 《计算机网络》(谢希仁 第8版) + RFC 标准 |
| 2 | 微调方案 | 优先 DeepSeek 官方微调服务（Phase 3 实施） |
| 3 | 向量数据库 | ChromaDB（嵌入式，pip install 即用），与 MySQL 互补不冲突 |
| 4 | 知识点粒度 | 双层结构：保留 25 个粗粒度（画像+选题不动）+ ~85 个子知识点（知识库+学习路径） |
| 5 | 提醒推送 | 仅前端页面内提醒 |
| 6 | 外部资源 | 无现成库，采用 LLM 生成搜索建议模式 |

### 3. Phase 1 全部实施完成

#### 基础设施
- `requirements.txt`：新增 chromadb, python-dotenv, sentence-transformers
- `.env.example`：新增 ChromaDB + RAG 配置项
- HuggingFace 国内镜像：`HF_ENDPOINT=https://hf-mirror.com`（嵌入模型下载用）
- 嵌入模型：`paraphrase-multilingual-MiniLM-L12-v2`（384维，中英文支持）

#### 数据库（已验证）
- 4 张新表：`knowledge_documents`, `knowledge_chunks`, `knowledge_relations`, `knowledge_sub_topics`
- 4 个字段扩展：`user_answers.error_attribution`, `user_answers.attribution_detail`, `ability_profile.confidence`, `ability_profile.learning_speed`
- 迁移文件：`database/migrations/002_knowledge_base.sql`

#### 新增核心模块
- `server/config.py`：全局配置（环境变量 + 默认回退值）
- `AI_operate/embedding_service.py`：文本嵌入 + 文档智能分块（本地模型优先，API 回退）
- `AI_operate/rag_service.py`：ChromaDB + MySQL 混合检索 + RAG Prompt 增强
- `scripts/seed_knowledge.py`：种子数据导入（幂等，支持 --dry-run 和 --skip-embeddings）

#### 种子数据（已入库 MySQL + ChromaDB）
- 71 个子知识点
- 47 条知识关系
- 12 篇知识文档（6 教材章 + 5 RFC + 1 知识条目）
- 32 个知识块（已生成嵌入向量并索引到 ChromaDB）

#### API 路由新增（5 个）
- `GET /api/knowledge/search` — 语义搜索（?q=&top_k=&doc_type=）
- `GET /api/knowledge/documents` — 文档列表（分页）
- `GET /api/knowledge/documents/<id>` — 文档详情 + 分块列表
- `GET /api/knowledge/sub-topics` — 子知识点列表（?parent_kp=）
- `GET /api/knowledge/relations` — 知识关系图（?kp=）

#### API 路由改造
- `POST /api/chat`：新增 `use_rag` 参数（默认 true），RAG 检索 → Prompt 增强 → 来源返回
- `POST /api/explain`：自动检索题目知识点相关块，注入讲解 Prompt
- `POST /api/explain/stream`：同上，流式场景

#### 前端变更
- `static/assets/starpal-chat-style.css`：新增 `.sources-card` 等引用卡片样式
- `static/js/dashboard-chat.js`：SSE 流中提取 sources → 渲染来源引用卡片
- RAG 服务采用懒加载单例（`_get_rag_service()`）避免重复加载模型
- 服务器启动时同步预热 RAG 服务（加载嵌入模型）

### 4. 已验证通过的功能
- ✅ ChromaDB 初始化和集合创建
- ✅ 嵌入模型加载和向量生成（384维）
- ✅ 知识检索 API 返回正确结果（搜索"TCP三次握手"命中 RFC 793 + 第5章）
- ✅ Flask 全部 27 个路由注册正常
- ✅ Python 语法检查通过
- ✅ 服务器冷启动 + 预热 + 请求处理全流程

## 重要技术注意事项

### 嵌入模型加载
- 首次启动服务器时，嵌入模型加载约需 8-12 秒（`paraphrase-multilingual-MiniLM-L12-v2`, ~120MB）
- 已实现同步预热：服务器在 `app.run()` 前完成模型加载
- 国内用户必须设置 `HF_ENDPOINT=https://hf-mirror.com`（已在 `server/app.py` 中硬编码设置）
- 模型缓存路径：`C:\Users\泫岚\.cache\huggingface\hub\`

### ChromaDB
- 持久化目录：`项目根目录/chroma_data/`
- 集合名称：`knowledge_chunks`
- 向量维度：384（cosine 相似度）
- 32 个知识块已索引

### Flask 调试注意事项
- `use_reloader=False`（已设置）
- 多个 Python 进程同时运行会导致端口冲突和死锁——重启前务必 `pkill -f "python server/app.py"`
- 暖启动后搜索响应时间 < 1 秒

## 当前知识库内容的局限

种子数据中的教材章节和 RFC 摘要 **不是从真实资料中提取的**，而是我根据知识储备编写的概括性内容。这意味着：
1. 内容可能与实际教材表述有出入
2. 引用无法标注精确页码
3. 缺少原书原文

**用户需要提供《计算机网络》(谢希仁 第8版) 电子版或其他资料来替换当前占位内容。**

## 模型微调状态

微调 **尚未实施**，仅在 PRD 中规划为 Phase 3。需要：
1. 系统运行积累训练数据（问答对、题目讲解对、错题分析对）
2. DeepSeek 官方微调服务是否可用待确认
3. 备选方案：Qwen-2.5-7B + LoRA

## 待办事项

### 高优先级
- [ ] 用户提供真实教材资料 → 替换种子数据中的占位内容
- [ ] 完成知识库内容导入和重新索引

### 中优先级
- [ ] Phase 2 实施：学习路径规划 + 深度错题归因
- [ ] `server/app.py` Blueprint 分层重构（从 1374 行拆分为 ~8 个文件）

### 低优先级
- [ ] Phase 3：模型微调（需先积累训练数据）
- [ ] Phase 4：持续优化（向量数据库迁移到 Milvus、移动端适配等）

## 关键文件清单

| 文件 | 操作 | 说明 |
|------|------|------|
| `docs/PRD-智能助学升级.md` | 新增 | 完整产品需求文档 |
| `requirements.txt` | 修改 | 新增 chromadb, python-dotenv, sentence-transformers |
| `.env.example` | 修改 | 新增 ChromaDB + RAG 配置 |
| `database/migrations/002_knowledge_base.sql` | 新增 | 4 张表 + 4 字段扩展 |
| `database/init_db.py` | 修改 | 添加新迁移执行 |
| `server/config.py` | 新增 | 全局配置模块 |
| `AI_operate/embedding_service.py` | 新增 | 文本嵌入 + 文档分块 |
| `AI_operate/rag_service.py` | 新增 | ChromaDB + MySQL 混合检索 |
| `scripts/seed_knowledge.py` | 新增 | 种子数据导入脚本 |
| `server/app.py` | 修改 | 新增 RAG 导入、5 个知识路由、chat/explain RAG 改造、同步预热 |
| `static/assets/starpal-chat-style.css` | 修改 | 新增来源引用卡片样式 |
| `static/js/dashboard-chat.js` | 修改 | 新增 sources 提取和渲染 |

## 启动命令

```bash
# 确保 MySQL 运行
# 启动后端（会自动预热 RAG）
cd "d:/WZYproject/WeiZuyi_Project_0.2.7 20260801"
.venv/Scripts/python server/app.py

# 新终端：启动前端
.venv/Scripts/python -m http.server 8888 --directory static
```

浏览器打开 `http://127.0.0.1:8888/login.html`

## 测试知识库

```bash
# 搜索知识库
curl "http://127.0.0.1:3001/api/knowledge/search?q=TCP三次握手&top_k=3"

# 获取子知识点
curl "http://127.0.0.1:3001/api/knowledge/sub-topics?parent_kp=TCP连接管理"

# 获取知识关系
curl "http://127.0.0.1:3001/api/knowledge/relations?kp=TCP连接管理"
```

## 下次会话建议从这里开始

1. 启动项目验证当前状态：`run_all.bat` 或手动启动
2. 确认知识库搜索 API 正常工作
3. 根据用户是否提供了真实教材资料，决定下一步：
   - 有资料 → 导入真实知识内容替换占位数据
   - 无资料 → 进入 Phase 2（学习路径规划 + 错题归因）

**Why:** 本次会话完成了 PRD 编写、6 项技术决策确认、Phase 1 全部实施（知识库 + RAG），是项目的重大架构升级。
**How to apply:** 下次会话时，AI 应首先读取本文件了解已完成工作，然后基于当前状态继续推进。
