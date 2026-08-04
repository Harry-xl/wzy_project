# 知识库 + RAG 系统 — 完整操作指南

> **适用版本**：v0.3.0+ | **更新日期**：2026-08-03
>
> 本文档覆盖知识库与 RAG（检索增强生成）系统的完整生命周期：部署、验证、使用、维护。

---

## 目录

1. [系统概览](#1-系统概览)
2. [环境要求](#2-环境要求)
3. [首次部署（三步走）](#3-首次部署三步走)
4. [验证检查清单](#4-验证检查清单)
5. [如何看到效果](#5-如何看到效果)
6. [架构详解](#6-架构详解)
7. [API 参考](#7-api-参考)
8. [添加/更新知识内容](#8-添加更新知识内容)
9. [故障排查](#9-故障排查)
10. [配置参考](#10-配置参考)

---

## 1. 系统概览

### 1.1 什么是 RAG？

**RAG (Retrieval-Augmented Generation，检索增强生成)** 的核心思路：在 AI 大模型回答用户问题之前，先从知识库中检索相关资料，把资料注入 Prompt，让大模型"开卷答题"。

```
以前（无 RAG）： 用户提问 → DeepSeek API → 凭记忆回答（可能幻觉、无法溯源）
现在（有 RAG）： 用户提问 → 知识库检索 → 资料注入 Prompt → DeepSeek API → 带来源引用的回答
```

### 1.2 系统架构一览

```
┌──────────────────────────────────────────────────────────────────┐
│                         前端（浏览器）                            │
│  ┌─────────────────────┐  ┌──────────────────────────────────┐   │
│  │ AI 对话 (chat)       │  │ 题目讲解 (explain)               │   │
│  │ · 参考来源卡片展示   │  │ · 自动检索题目关联知识点        │   │
│  │ · 相关性百分比       │  │ · 基于教材内容生成讲解          │   │
│  └─────────┬───────────┘  └────────────────┬─────────────────┘   │
└────────────┼──────────────────────────────┼──────────────────────┘
             │          HTTP API (Flask :3001)                      │
             ▼                          ▼
┌─────────────────────────┬─────────────────────────────────────────┐
│  AI 业务层               │  数据存储层                             │
│                          │                                        │
│  ┌───────────────────┐   │  ┌──────────────┐  ┌──────────────┐   │
│  │ RAGService        │   │  │ MySQL 8.x    │  │ ChromaDB     │   │
│  │ · 混合检索        │◄──┼──│ · 4张知识表  │  │ · 向量索引   │   │
│  │ · Prompt 组装     │   │  │ · 完整文本   │  │ · 32个块     │   │
│  │ · 相似度排序      │   │  │ · 元数据     │  │ · 384维      │   │
│  └────────┬──────────┘   │  └──────────────┘  └──────────────┘   │
│           │               │                                        │
│  ┌────────┴──────────┐   │                                        │
│  │ EmbeddingService  │   │  数据现状（种子数据）                   │
│  │ · 文本→向量       │   │  · 71 个子知识点                       │
│  │ · 文档智能分块    │   │  · 47 条知识关系                       │
│  └───────────────────┘   │  · 12 篇文档（6教材章+5RFC+1条目）     │
│                          │  · 32 个知识块（已索引）                │
└─────────────────────────┴─────────────────────────────────────────┘
```

### 1.3 关键文件清单

| 文件 | 作用 |
|------|------|
| `server/config.py` | 全局配置（数据库、API Key、ChromaDB、RAG参数） |
| `AI_operate/rag_service.py` | RAG 核心引擎：混合检索 + Prompt 组装 + 索引管理 |
| `AI_operate/embedding_service.py` | 文本嵌入：向量化 + 文档分块 + 内容哈希 |
| `database/migrations/002_knowledge_base.sql` | 知识库 4 张表 + 2 张表扩展 |
| `scripts/seed_knowledge.py` | 种子数据导入脚本（~86个子知识点、12篇文档等） |
| `server/app.py`（修改部分） | 5 个知识 API + chat/explain RAG 改造 + 预热逻辑 |
| `static/js/dashboard-chat.js` | 仪表盘聊天：SSE 解析 sources → 渲染参考来源卡片 |
| `static/assets/starpal-chat-style.css` | 来源引用卡片样式（`.sources-card`） |

---

## 2. 环境要求

### 2.1 软件依赖

| 组件 | 版本要求 | 说明 |
|------|---------|------|
| Python | 3.11+ | |
| MySQL | 8.x | 本地运行，端口 3306 |
| ChromaDB | 0.4.x | 嵌入式部署，无需单独安装服务 |
| sentence-transformers | 2.2+ | 本地嵌入模型 |
| 嵌入模型 | paraphrase-multilingual-MiniLM-L12-v2 | 首次自动下载 ~120MB |

### 2.2 网络要求

- **国内用户**：已配置 HuggingFace 镜像 `https://hf-mirror.com`（在 `embedding_service.py` 中），用于下载嵌入模型
- **DeepSeek API**：需能访问 `https://api.deepseek.com`
- 嵌入模型采用本地推理，**无需联网**

### 2.3 磁盘空间

| 存储 | 占用 | 位置 |
|------|------|------|
| 嵌入模型文件 | ~120 MB | `C:\Users\<用户名>\.cache\huggingface\hub\` |
| ChromaDB 向量索引 | ~420 KB（32块） | 项目根目录 `chroma_data/` |
| MySQL 知识数据 | 可忽略 | `wzyProjectDb` 数据库 |

---

## 3. 首次部署（三步走）

> **前提**：MySQL 服务已启动，Python 虚拟环境已创建。

### 第一步：安装依赖

```bash
cd "d:/WZYproject/WeiZuyi_Project_0.2.7 20260801"
.venv/Scripts/pip install chromadb sentence-transformers python-dotenv
```

如果 `requirements.txt` 已包含这些包，直接：

```bash
.venv/Scripts/pip install -r requirements.txt
```

### 第二步：创建知识库表

```bash
.venv/Scripts/python database/init_db.py
```

**预期输出**：
```
==> 执行 create_db.sql（建库/建表） ...
==> 执行 insert_test_data.sql（测试数据） ...
==> 执行 add_user_strength.sql（用户实力字段与初始化） ...
==> 执行 002_knowledge_base.sql（知识库表与字段） ...
=== 数据库初始化完成 ===
```

**验证建表成功**：
```sql
-- 连接 MySQL 执行
USE wzyProjectDb;
SHOW TABLES;
-- 应该看到 9 张表（原有的5张 + knowledge_documents/chunks/relations/sub_topics）
```

### 第三步：导入种子数据

```bash
.venv/Scripts/python scripts/seed_knowledge.py
```

**预期输出**：
```
[EmbeddingService] 正在加载模型: paraphrase-multilingual-MiniLM-L12-v2
[EmbeddingService] 使用镜像: https://hf-mirror.com
[EmbeddingService] 本地模型已加载: paraphrase-multilingual-MiniLM-L12-v2
[RAGService] 已索引 N 个块到 ChromaDB
=== 种子数据导入完成 ===
```

**首次运行注意**：
- 嵌入模型首次下载需 8-15 秒（取决于网络速度）
- 如果网络不通，模型下载失败，数据仅写入 MySQL（ChromaDB 索引为空），后续可通过 `seed_knowledge.py` 重新索引

**幂等性保证**：
- `seed_knowledge.py` 使用 `INSERT IGNORE` 或先查后插，重复执行不会产生重复数据
- 子知识点通过 `(sub_topic_name, parent_kp)` 唯一约束去重
- 知识块通过 `(doc_id, content_hash)` 去重

---

## 4. 验证检查清单

按顺序逐项验证，确保系统完整可用。

### 4.1 数据库验证

```sql
-- 验证 4 张知识表存在
SELECT TABLE_NAME, TABLE_COMMENT
FROM INFORMATION_SCHEMA.TABLES
WHERE TABLE_SCHEMA = 'wzyProjectDb'
  AND TABLE_NAME LIKE 'knowledge%';
```

预期输出：
```
knowledge_documents   知识库文档元数据表
knowledge_chunks      知识块表——RAG检索的最小单元
knowledge_relations   知识点关系图
knowledge_sub_topics  子知识点表——细粒度知识组织
```

```sql
-- 验证数据量
SELECT 'documents' AS t, COUNT(*) AS n FROM knowledge_documents
UNION ALL SELECT 'chunks', COUNT(*) FROM knowledge_chunks
UNION ALL SELECT 'sub_topics', COUNT(*) FROM knowledge_sub_topics
UNION ALL SELECT 'relations', COUNT(*) FROM knowledge_relations;
```

预期：documents=12, chunks=32, sub_topics=71, relations=47

### 4.2 ChromaDB 验证

```bash
.venv/Scripts/python -c "
import chromadb
client = chromadb.PersistentClient(path='chroma_data')
coll = client.get_collection('knowledge_chunks')
print(f'集合名称: {coll.name}')
print(f'已索引块数: {coll.count()}')
print(f'向量维度: {len(coll.peek(1)[\"embeddings\"][0]) if coll.count() > 0 else \"N/A\"}')
"
```

预期输出：
```
集合名称: knowledge_chunks
已索引块数: 32
向量维度: 384
```

### 4.3 知识库 API 验证

启动服务器后运行：

```bash
# 1. 语义搜索
curl "http://127.0.0.1:3001/api/knowledge/search?q=TCP三次握手&top_k=3"
```
预期：返回 3 个知识块 JSON，每个包含 `chunk_id`, `content`, `doc_title`, `source`, `score`。

```bash
# 2. 文档列表
curl "http://127.0.0.1:3001/api/knowledge/documents?page=1&page_size=5"
```
预期：返回 5 篇文档，`total` 应为 12。

```bash
# 3. 子知识点（按父知识点筛选）
curl "http://127.0.0.1:3001/api/knowledge/sub-topics?parent_kp=TCP连接管理"
```
预期：返回 3 个子知识点（三次握手、四次挥手、TCP状态转换）。

```bash
# 4. 知识关系图
curl "http://127.0.0.1:3001/api/knowledge/relations?kp=TCP连接管理"
```
预期：返回多条关系（前置/扩展/组成等）。

### 4.4 RAG 对话验证

在 AI 对话界面（仪表盘内嵌聊天）中测试：

1. 提问："TCP 三次握手的过程是怎样的？"
2. 观察 AI 回复气泡下方是否出现 **"📖 参考来源"** 卡片
3. 卡片应显示来源信息，如 `[1] 《计算机网络》(谢希仁第8版) · 第5章 (92%)`

### 4.5 服务器启动日志验证

启动 server/app.py 时，观察以下日志：

```
[config] MySQL: localhost:3306/wzyProjectDb
[config] ChromaDB: d:\WZYproject\WeiZuyi_Project_0.2.7 20260801\chroma_data
[config] RAG: top_k=5, threshold=0.3
[warmup] 正在预热 RAG 服务（加载嵌入模型）...
[EmbeddingService] 正在加载模型: paraphrase-multilingual-MiniLM-L12-v2
[EmbeddingService] 本地模型已加载: paraphrase-multilingual-MiniLM-L12-v2
[warmup] RAG 服务预热完成
 * Running on http://127.0.0.1:3001
```

---

## 5. 如何看到效果

### 5.1 方式一：API 直接查知识库（最直观）

```bash
curl "http://127.0.0.1:3001/api/knowledge/search?q=OSI七层模型&top_k=3" | python -m json.tool
```

返回的 JSON 中，每个 chunk 都有**来源信息**和**相似度分数**——这直接证明向量检索+内容查询链路是通的。

### 5.2 方式二：仪表盘聊天看来源卡片

**入口**：`http://127.0.0.1:8888/login.html` → 登录 → 进入仪表盘 → AI 对话 tab

**效果**：问计算机网络问题时，AI 回复下方出现蓝色参考来源卡片：
```
┌─────────────────────────────────────────────┐
│ 📖 参考来源                                  │
│ [1] 《计算机网络》(第8版)·第5章 (92%)        │
│ [2] RFC 793·传输控制协议 (87%)              │
└─────────────────────────────────────────────┘
```

> **⚠️ 注意**：目前**只有仪表盘内嵌聊天**（dashboard → iframe chat）支持来源卡片展示。
> 独立聊天页 `chat.html` 尚未适配 RAG 来源显示（计划在后续版本补齐）。

### 5.3 方式三：题目讲解自动关联

做题 → 点击 **"AI 讲解"** → 后端自动以"知识点 + 题目内容"检索知识库 → 讲解内容基于教材资料生成。

### 5.4 方式四：查看 MySQL 中的知识内容

直接用数据库客户端查 `knowledge_documents` 和 `knowledge_chunks` 表，可以看到完整的知识文本和来源元数据。

---

## 6. 架构详解

### 6.1 双层存储设计

| | ChromaDB（向量层） | MySQL（内容层） |
|---|---|---|
| **存什么** | 384维嵌入向量 + chunk_id | 完整文本 + 文档元数据（来源/章节/知识点） |
| **负责** | 语义相似度检索（"TCP连接建立"≈"三次握手"） | 精确关键词匹配 + 内容返回 |
| **为什么这样** | ChromaDB 只做向量检索最快 | 矢量数据库不擅长存大量元数据 |
| **关联方式** | 通过 chunk_id 与 MySQL 关联 | 通过 chunk_id 与 ChromaDB 关联 |

### 6.2 混合检索流程

```
用户查询 "TCP三次握手的过程"
         │
         ▼
┌────────────────────────────────────────────┐
│  1. EmbeddingService.embed_single()        │
│     文本 → 384维归一化向量                  │
│     模型: paraphrase-multilingual-MiniLM   │
└────────────────┬───────────────────────────┘
                 │
     ┌───────────┴───────────┐
     ▼                       ▼
┌──────────────┐    ┌──────────────────┐
│ 2a. 向量检索  │    │ 2b. 关键词检索    │
│ ChromaDB     │    │ MySQL LIKE       │
│ 取 top 10    │    │ 基准分 0.25      │
└──────┬───────┘    └────────┬─────────┘
       │                     │
       └────── 合并去重 ─────┘
                 │
                 ▼
┌────────────────────────────────────────────┐
│  3. 混合打分                                │
│     · 向量命中基础分 = 1.0 - 余弦距离/2     │
│     · 同时被关键词命中 → +0.1 加分          │
│     · 仅关键词命中 → 基础分 0.25-0.3        │
│     · 过滤低于 threshold(0.3) 的结果        │
│     · 按分数降序 → 截取 Top K               │
└────────────────┬───────────────────────────┘
                 │
                 ▼
┌────────────────────────────────────────────┐
│  4. MySQL 查询完整内容 + 元数据             │
│     SELECT content, title, source,          │
│            source_page, knowledge_points    │
│     FROM knowledge_chunks                   │
│     JOIN knowledge_documents USING (doc_id) │
│     WHERE chunk_id IN (3,7,12)              │
└────────────────┬───────────────────────────┘
                 │
                 ▼
┌────────────────────────────────────────────┐
│  5. build_context_block() 格式化           │
│     【参考资料】（来自星伴知识库检索）       │
│     [1] 《计算机网络》(第8版)·第5章         │
│         传输控制协议 TCP 是...              │
│     [2] RFC 793 · 传输控制协议              │
│         The Transmission Control Protocol.. │
└────────────────┬───────────────────────────┘
                 │
                 ▼
┌────────────────────────────────────────────┐
│  6. DeepSeek API + RAG Prompt              │
│     System: "你必须基于以下参考资料回答"    │
│     + 引用规则（标注[1][2]，末尾列来源）    │
│     + 组装后的参考资料                      │
│     + 用户问题                              │
│     → SSE 流式返回                          │
└────────────────┬───────────────────────────┘
                 │
                 ▼
┌────────────────────────────────────────────┐
│  7. 前端解析 SSE → 提取 sources             │
│     渲染 .sources-card 参考来源卡片         │
└────────────────────────────────────────────┘
```

### 6.3 降级保护机制

| 场景 | 降级策略 |
|------|---------|
| 嵌入模型加载失败 | 回退到 DeepSeek Embedding API |
| ChromaDB 检索异常 | 回退到 MySQL 关键词检索 |
| 向量检索结果为空 | 自动切换到关键词检索 |
| RAG 全程失败 | 回退到纯对话模式（无知识增强） |
| 嵌入生成失败 | 数据存入 MySQL，ChromaDB 索引稍后补建 |

### 6.4 文档智能分块算法

```
长文档
  │
  ▼
按段落切分 (\n\n)
  │
  ├─ 短段落(<512字符) → 合并到当前块，满了就起新块
  │
  └─ 长段落(>512字符)
      │
      ▼
    按句子切分 (。！？\n)
      │
      ▼
    逐句填充，块间 64 字符重叠窗口
    （保持上下文连贯）
```

每个块的 SHA-256 哈希用于增量更新时检测内容是否变化。

### 6.5 RAG 服务生命周期

```
服务器启动
    │
    ▼
[app.py] _get_rag_service()  ← 懒加载单例
    │
    ├─ RAGService.__init__()
    │   ├─ ChromaDB 客户端初始化（chroma_data/）
    │   └─ EmbeddingService 引用
    │
    ▼
[warmup] rag.search('warmup query', top_k=1)
    │  触发 EmbeddingService 模型加载（首次 8-15s）
    ▼
 就绪 ← 此后所有请求复用同一个实例
```

---

## 7. API 参考

### 7.1 知识库检索

```
GET /api/knowledge/search
```

| 参数 | 类型 | 必填 | 默认 | 说明 |
|------|------|:--:|------|------|
| `q` | string | ✅ | — | 搜索关键词（中文自然语言） |
| `top_k` | int | | 5 | 返回结果数（1-20） |
| `doc_type` | string | | — | 文档类型过滤：textbook/rfc/knowledge_entry/... |

**示例**：
```bash
curl "http://127.0.0.1:3001/api/knowledge/search?q=拥塞控制算法&top_k=3"
```

**响应**：
```json
{
  "success": true,
  "chunks": [
    {
      "chunk_id": 25,
      "content": "TCP拥塞控制是TCP协议的核心机制之一...",
      "chunk_index": 0,
      "doc_title": "第5章 传输层",
      "doc_type": "textbook",
      "source": "《计算机网络》(谢希仁 第8版)",
      "source_page": "第5章",
      "knowledge_points": ["TCP拥塞控制"],
      "sub_topic_name": "慢启动",
      "score": 0.8542
    }
  ],
  "total": 3,
  "query": "拥塞控制算法"
}
```

### 7.2 知识库搜索（流式聊天集成）

```
POST /api/chat
```

| 参数 | 类型 | 必填 | 默认 | 说明 |
|------|------|:--:|------|------|
| `message` | string | ✅ | — | 用户消息 |
| `username` | string | | — | 用户名 |
| `chat_id` | string | | — | 对话 ID |
| `use_rag` | bool | | true | 是否启用 RAG 检索 |

**RAG 开关**：前端请求中传 `"use_rag": false` 可关闭知识增强，退回到纯 LLM 模式。

**SSE 流结束标记**（含来源引用）：
```json
{"reply": "", "done": true, "sources": [
  {"index": 1, "title": "第5章 传输层", "source": "《计算机网络》(第8版)", "source_page": "第5章", "score": 0.92}
]}
```

### 7.3 题目讲解（自动 RAG）

```
POST /api/explain
POST /api/explain/stream
```

后端自动以 `knowledge_point + problem_text` 作为查询条件检索知识库，无需前端额外传参。

### 7.4 文档管理

| 端点 | 方法 | 说明 |
|------|------|------|
| `/api/knowledge/documents` | GET | 文档列表（分页），参数 `page`, `page_size`, `doc_type` |
| `/api/knowledge/documents/<id>` | GET | 文档详情 + 所有分块列表 |
| `/api/knowledge/sub-topics` | GET | 子知识点列表，参数 `parent_kp`（可选，筛选父知识点） |
| `/api/knowledge/relations` | GET | 知识关系图，参数 `kp`（可选，筛选关联知识点） |

---

## 8. 添加/更新知识内容

### 8.1 方式一：通过脚本批量导入（推荐）

编辑 `scripts/seed_knowledge.py`，在 `TEXTBOOK_CHAPTERS`、`RFC_SUMMARIES` 或 `KNOWLEDGE_ENTRIES` 中添加新内容，格式如下：

```python
{
    "title": "第X章 XXX",
    "source": "《计算机网络》(谢希仁 第8版)",
    "source_page": "第X章 第X节",
    "doc_type": "textbook",        # textbook / rfc / knowledge_entry
    "knowledge_points": ["知识点1", "知识点2"],
    "difficulty": "基础",           # 基础 / 进阶 / 高级
    "content": """
    这里是完整的知识内容...
    支持多段落，会自动分块处理。
    """,
}
```

然后重新运行：

```bash
.venv/Scripts/python scripts/seed_knowledge.py
```

- 已有内容（通过 SHA-256 哈希检测）会被跳过
- 新增内容会被自动分块、存入 MySQL、生成向量、写入 ChromaDB

### 8.2 方式二：通过 API 管理（计划中，尚未实现）

未来将提供：
- `POST /api/knowledge/documents` — 创建文档
- `PUT /api/knowledge/documents/<id>` — 更新文档
- `DELETE /api/knowledge/documents/<id>` — 删除文档及关联块

### 8.3 重新索引

如果 ChromaDB 数据损坏或嵌入模型更换，重新索引现有 MySQL 数据：

```python
# 在 Python 交互环境中执行
from AI_operate.rag_service import RAGService
from database.db_connector import get_connection

rag = RAGService()
conn = get_connection()
cursor = conn.cursor(dictionary=True)
cursor.execute("SELECT doc_id, chunk_id, content FROM knowledge_chunks")
rows = cursor.fetchall()

for row in rows:
    rag.index_chunks(row['doc_id'], [{
        'chunk_index': 0,
        'content': row['content']
    }])
```

---

## 9. 故障排查

### 9.1 知识库表不存在

**现象**：API 返回 500，日志显示 `Table 'wzyProjectDb.knowledge_documents' doesn't exist`

**解决**：
```bash
.venv/Scripts/python database/init_db.py
```

### 9.2 ChromaDB 索引为空

**现象**：知识搜索无结果，或仅有 MySQL 关键词匹配的低分结果

**排查**：
```bash
.venv/Scripts/python -c "
import chromadb
c = chromadb.PersistentClient(path='chroma_data')
print(c.get_collection('knowledge_chunks').count())
"
```
如果输出 0，说明种子数据导入时嵌入模型未就绪。

**解决**：重新运行种子数据导入：
```bash
.venv/Scripts/python scripts/seed_knowledge.py
```

### 9.3 嵌入模型下载失败

**现象**：`[EmbeddingService] 本地模型加载失败`

**排查**：
- 检查 HuggingFace 镜像是否可达：`curl -I https://hf-mirror.com`
- 检查磁盘空间（模型 ~120MB）

**解决**：
- 如镜像不可达，修改 `AI_operate/embedding_service.py` 中的 `_HF_MIRROR` 为其他镜像或官方源
- 或手动下载模型放到 `C:\Users\<用户名>\.cache\huggingface\hub\`

### 9.4 服务器启动慢

**现象**：服务器启动时卡在 `[warmup] 正在预热 RAG 服务...` 超过 30 秒

**原因**：嵌入模型首次下载或加载异常

**解决**：
- 首次启动耐心等待（下载 ~120MB 模型，8-15 秒正常）
- 如超过 1 分钟，检查网络连接到 `hf-mirror.com`
- 预热失败不会阻止服务器启动，RAG 功能在首次请求时降级

### 9.5 前端聊天不显示来源卡片

**现象**：AI 对话能正常回复，但没有参考来源卡片

**原因**（按可能性排序）：

1. **使用了独立聊天页 `chat.html`** — 该页面尚未适配 RAG 来源显示，只有仪表盘内嵌聊天支持
2. **ChromaDB 索引为空** — 向量检索无结果，MySQL 关键词也没命中（参见 9.2 节排查）
3. **use_rag 被关闭** — 检查请求中是否传了 `"use_rag": false`

**排查**：
```bash
# 先用 API 验证知识库是否能搜到内容
curl "http://127.0.0.1:3001/api/knowledge/search?q=计算机网络&top_k=3"
```

### 9.6 端口冲突

**现象**：`Address already in use` 或 `Port 3001 is already in use`

**解决**：
```bash
# Windows PowerShell
netstat -ano | findstr :3001
taskkill /PID <PID> /F

# Git Bash
taskkill //PID <PID> //F
```

---

## 10. 配置参考

所有配置在 `server/config.py` 中，优先读取环境变量，有合理默认值。

| 配置项 | 环境变量 | 默认值 | 说明 |
|--------|---------|--------|------|
| ChromaDB 持久化目录 | `CHROMADB_PERSIST_DIR` | `./chroma_data` | 向量数据存储路径 |
| ChromaDB 集合名 | `CHROMADB_COLLECTION_NAME` | `knowledge_chunks` | 向量集合名称 |
| RAG 默认返回数 | `RAG_DEFAULT_TOP_K` | `5` | 每次检索返回的知识块数 |
| RAG 最大返回数 | `RAG_MAX_TOP_K` | `20` | top_k 参数上限 |
| RAG 相似度阈值 | `RAG_SIMILARITY_THRESHOLD` | `0.3` | 低于此分数的结果被过滤 |
| 嵌入模型 | — | `paraphrase-multilingual-MiniLM-L12-v2` | 384维，中英文 |
| HF 镜像 | — | `https://hf-mirror.com` | 国内下载加速 |

---

## 附录 A：当前种子数据内容清单

### 子知识点（71个，按粗粒度知识点分组）

| 粗粒度知识点 | 子知识点数量 | 示例 |
|-------------|:---------:|------|
| 计算机网络概述 | 4 | 网络定义与分类、拓扑结构、交换方式、性能指标 |
| 网络体系结构 | 3 | OSI七层、TCP/IP四层、五层协议体系 |
| 物理层基础 | 3 | 接口特性、信道复用、PCM数字传输 |
| 数据链路层基础 | 3 | 链路层功能、PPP协议、CSMA/CD |
| 滑动窗口与可靠传输 | 3 | 停等协议、GBN、选择重传 |
| MAC子层与以太网 | 3 | 帧格式、交换机MAC表、VLAN |
| ARP协议 | 3 | ARP原理、报文格式、Gratuitous ARP |
| IPv4与IPv6 | 3 | IPv4报文、IP分片重组、IPv6 |
| IP地址与子网划分 | 4 | 分类编址、子网掩码、CIDR、VLSM |
| 路由算法与协议 | 4 | DV算法、RIP、OSPF、BGP |
| ICMP协议 | 2 | 报文类型、Ping/Traceroute |
| NAT与DHCP | 2 | NAT转换、DHCP配置 |
| 多播与移动IP | 2 | IGMP多播、移动IP |
| UDP协议 | 2 | 报文格式、特点与应用 |
| TCP连接管理 | 3 | 三次握手、四次挥手、状态转换 |
| TCP可靠传输与流量控制 | 3 | 序列号确认号、滑动窗口、零窗口探测 |
| TCP拥塞控制 | 4 | 慢启动、拥塞避免、快重传快恢复、Tahoe/Reno/CUBIC |
| DNS系统 | 3 | 解析流程、记录类型、缓存与安全 |
| HTTP与HTTPS | 4 | 请求响应、持久连接、TLS握手、缓存策略 |
| 高级Web协议 | 2 | HTTP/2+HTTP/3、WebSocket |
| FTP与电子邮件 | 2 | FTP协议、SMTP/POP3/IMAP |
| CDN与负载均衡 | 2 | CDN分发、负载均衡策略 |
| 零拷贝与传输优化 | 2 | 零拷贝技术、TCP优化参数 |
| QoS与流量管理 | 2 | QoS模型、流量整形调度 |
| 网络安全与防火墙 | 3 | 加密基础、防火墙ACL、攻击防御 |

### 知识文档（12篇）

| 标题 | 类型 | 来源 |
|------|------|------|
| 第1章 计算机网络概述 | textbook | 谢希仁 第8版 |
| 第2章 物理层 | textbook | 谢希仁 第8版 |
| 第3章 数据链路层 | textbook | 谢希仁 第8版 |
| 第4章 网络层 | textbook | 谢希仁 第8版 |
| 第5章 传输层 | textbook | 谢希仁 第8版 |
| 第6章 应用层 | textbook | 谢希仁 第8版 |
| RFC 793 — TCP | rfc | IETF |
| RFC 791 — IP | rfc | IETF |
| RFC 792 — ICMP | rfc | IETF |
| RFC 826 — ARP | rfc | IETF |
| RFC 2616 — HTTP/1.1 | rfc | IETF |
| TCP拥塞控制算法综述 | knowledge_entry | 综合整理 |

### 知识关系（47条）

| 关系类型 | 数量 | 含义 |
|---------|:---:|------|
| prerequisite | 22 | 前置知识（需先学A才能学B） |
| extension | 4 | 扩展知识（在A基础上的深化） |
| related | 7 | 相关（A和B有紧密关联） |
| part_of | 14 | 组成（A是B的一部分） |

---

## 附录 B：与 chat.js 的已知差异

| 功能 | dashboard-chat.js | chat.js（独立页面） |
|------|:---:|:---:|
| RAG 来源解析 | ✅ 解析 done.sources | ❌ 忽略 |
| 参考来源卡片 | ✅ `.sources-card` 渲染 | ❌ 无 |
| 相关性百分比 | ✅ 显示 | ❌ 无 |
| 聊天历史管理 | ✅ | ✅ |
| SSE 流式读取 | ✅ | ✅ |
| 停止生成 | ✅ | ✅ |

**计划**：v0.3.1 将为 `chat.js` 补齐 RAG 来源展示功能。

---

> **相关文档**：
> - 项目 PRD：[PRD-智能助学升级.md](PRD-智能助学升级.md)
> - 会话记录：[session-2026-08-02-phase1-implementation.md](../memory/session-2026-08-02-phase1-implementation.md)
> - API 设计规范：[api-design.md](../.claude/rules/api-design.md)
> - 数据库设计规范：[database-design.md](../.claude/rules/database-design.md)
