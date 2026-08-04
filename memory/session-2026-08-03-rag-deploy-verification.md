---
name: session-2026-08-03-rag-deploy-verification
description: 2026-08-03 会话 — RAG 系统部署验证、chat.js/renderer.js 修复、验证脚本编写、操作文档交付
metadata:
  type: project
---

# 2026-08-03 会话：Phase 1 知识库+RAG 部署验证与完善

## 会话目标

用户要求验证 Phase 1 知识库+RAG 升级是否真正可用，并建立完善的测试和纠错机制。

## 发现与修复的问题

### 问题1：知识库表不存在（用户反馈）
- **现象**：用户 MySQL 中只能看到 5 张表，没有 `knowledge_*` 表
- **原因**：`database/migrations/002_knowledge_base.sql` 迁移文件存在，`init_db.py` 也已包含执行代码（第110-113行），但从未重新运行过 `init_db.py`
- **解决**：运行 `python database/init_db.py` 创建了 4 张知识表
- **结果**：当前 MySQL 有 9 张表，数据完整（12文档/32块/72子知识点/141关系）

### 问题2：AI 聊天不显示 RAG 来源卡片
- **根因分析**：
  - `chat.html` 实际只是一个重定向页（→ dashboard.html）
  - `chat.js` 是遗留代码，未被任何 HTML 加载（仅 `dashboard-chat.js` 被 `dashboard.html` 引用）
  - `dashboard-chat.js` 已有完整的 sources 解析和渲染（第96-106行、第155行）
  - 用户看不到来源是因为之前知识表不存在 → RAG 检索无结果
- **修复**：虽然 `chat.js` 未被使用，但仍做了防御性修复：
  - `chat.js`：SSE 解析增加 `data.done && data.sources` 提取、finishAiReply 保留 sources、stopBtn 保留 sources
  - `renderer.js`：`createMessageElement` 增加 `.sources-card` 渲染（~20行）

### 问题3：ChromaDB 单进程限制
- **现象**：验证脚本全量运行时 RAGService 初始化失败
- **原因**：Flask 服务器已持有 ChromaDB (SQLite)，第二个进程无法同时打开
- **解决**：验证脚本 `--quick` 模式不初始化 RAGService，仅检查 ChromaDB 元数据和向量维度

## 已完成的核心工作

### 1. 系统状态确认
- MySQL：9 张表，知识数据完整 ✅
- ChromaDB：32 块索引，384维向量 ✅
- 嵌入模型：`paraphrase-multilingual-MiniLM-L12-v2` 正常加载（~15s）✅
- API 端点：5 个知识 API + chat RAG 流式全部通过 ✅

### 2. 新增文件

| 文件 | 行数 | 说明 |
|------|:---:|------|
| `scripts/verify_rag.py` | 497 | 一键完整性验证脚本，7层39个检查点 |
| `docs/知识库RAG系统-操作指南.md` | ~600 | 完整操作文档（10章+2附录） |

### 3. 修改文件

| 文件 | 改动 | 说明 |
|------|------|------|
| `static/js/chat.js` | 3处修改 | SSE sources解析、finishAiReply保留、stopBtn保留 |
| `static/js/renderer.js` | +20行 | `createMessageElement` 添加 sources-card 渲染 |

## 验证脚本说明

`scripts/verify_rag.py` 检查 7 层：

```
依赖 → MySQL(表+数据) → ChromaDB(索引+维度) → 嵌入模型 → RAG管道 → API端点 → 前端文件
```

### 用法

```bash
# 日常快速自检（不关服务器，~10秒）
python scripts/verify_rag.py --quick --offline

# 深度排查（需先关Flask服务器，~40秒）
python scripts/verify_rag.py --offline

# 全量在线检查（需服务器运行，~40秒）
python scripts/verify_rag.py
```

### 最后一次运行结果（quick+offline）
```
总计: 35项 | 通过: 29 | 失败: 0 | 跳过: 6
全部检查通过！RAG 系统运行正常。
```

### 最后一次运行结果（full, 服务器在线）
```
总计: 39项 | 通过: 38 | 失败: 1（RAGService被服务器占用-预期行为）
API端点全部通过，chat RAG流式返回sources确认正常
```

## 关键技术要点

### 数据存储位置
- **MySQL** (`wzyProjectDb`)：4张 `knowledge_*` 表存完整文本+元数据
- **ChromaDB** (`chroma_data/`)：向量索引，384维余弦相似度
- **嵌入模型缓存**：`C:\Users\泫岚\.cache\huggingface\hub\`

### RAG 工作流程
```
用户提问 → 嵌入向量化 → ChromaDB语义检索(top10) + MySQL关键词检索
→ 合并打分排序 → MySQL查完整内容 → Prompt组装注入 → DeepSeek API
→ SSE流式返回 → 前端解析sources → 渲染来源卡片
```

### 关键配置（server/config.py）
- `RAG_DEFAULT_TOP_K=5` — 每次检索返回5个知识块
- `RAG_SIMILARITY_THRESHOLD=0.3` — 相似度低于0.3的结果被过滤
- `CHROMADB_PERSIST_DIR=./chroma_data` — 向量数据目录
- 嵌入模型：`paraphrase-multilingual-MiniLM-L12-v2` (384维)

## 当前局限（待后续解决）

1. **种子数据为AI生成**：12篇文档内容非真实教材提取，需用户提供《计算机网络》(谢希仁第8版)电子版替换
2. **chat.js 未被使用**：`chat.html` 仅作重定向，实际只有 `dashboard-chat.js` 活跃
3. **ChromaDB 单进程**：验证脚本全量模式需先关Flask服务器

## 下次会话建议

1. 用户提供真实教材资料 → 更新 `scripts/seed_knowledge.py` 中 `TEXTBOOK_CHAPTERS` → 重新导入
2. Phase 2 实施：学习路径规划 + 深度错题归因
3. `server/app.py` Blueprint 分层重构（从1374行拆分为多个文件）
4. 或用户提出其他优先级需求

## 关键文件索引

| 文件 | 说明 |
|------|------|
| `docs/知识库RAG系统-操作指南.md` | 完整操作文档 |
| `scripts/verify_rag.py` | 一键验证脚本 |
| `AI_operate/rag_service.py` | RAG 核心引擎 |
| `AI_operate/embedding_service.py` | 嵌入+分块服务 |
| `server/config.py` | 全局配置 |
| `database/migrations/002_knowledge_base.sql` | 知识库表DDL |
| `scripts/seed_knowledge.py` | 种子数据导入 |
| `static/js/dashboard-chat.js` | 仪表盘聊天（已有完整RAG支持） |
| `static/js/renderer.js` | 消息渲染器（已添加sources-card） |
| `static/assets/starpal-chat-style.css` | 来源卡片样式 |

**Why:** 本次会话完成了 RAG 系统的全面验证、chat.js/renderer.js 的防御性修复、验证脚本编写、操作文档交付。系统当前状态：数据库+ChromaDB+嵌入模型+API+前端全链路正常。
**How to apply:** 下次会话时，AI 应首先读取本文件了解已完成工作，然后基于当前状态继续推进。用户可通过 `scripts/verify_rag.py --quick --offline` 快速确认系统状态。
