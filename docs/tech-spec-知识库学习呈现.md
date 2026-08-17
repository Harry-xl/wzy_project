# 技术规格: 知识库学习呈现 + 学练打通

> 关联 PRD: [PRD-知识库学习呈现.md](PRD-知识库学习呈现.md) | 版本: 0.1 | 日期: 2026-08-07

---

## 1. 文档信息

| 字段 | 内容 |
|------|------|
| 版本 | 0.1 |
| 创建日期 | 2026-08-07 |
| 状态 | 🟡 评审中 |
| 关联 PRD | [PRD-知识库学习呈现.md](PRD-知识库学习呈现.md) v0.2 |

---

## 2. 架构变更

### 2.1 影响范围图

```
┌──────────────────────────────────────────────────────────────┐
│                        前端 (Dashboard SPA)                    │
│                                                              │
│  dashboard.html  ← 新增学习卡片 Modal 骨架                     │
│  dashboard.js    ← 新增学练跳转协调逻辑                         │
│  dashboard-library.js       ← 新增 LearningCardModal 类       │
│  dashboard-library-graph.js ← 节点点击→卡片 (替代旧下钻面板)    │
│  dashboard-library-knowledge.js ← 行点击→卡片                  │
│  dashboard-profile.js (内联) ← 薄弱项操作按钮                  │
│  starpal-style.css           ← 学习卡片+打通按钮样式 (~120行)   │
│                                                              │
│  exam.html / exam.js ← 新增「查看学习资料」按钮 + postMessage   │
└──────────────────────────┬───────────────────────────────────┘
                           │ HTTP/SSE
                           ▼
┌──────────────────────────────────────────────────────────────┐
│                    Flask API (server/)                         │
│                                                              │
│  library_api.py  ← 新增 4 个学习卡片端点                       │
│  app.py          ← (无需修改，Blueprint 已注册)                │
└──────────────────────────┬───────────────────────────────────┘
                           │
                           ▼
┌──────────────────────────────────────────────────────────────┐
│                   Service Layer (server/)                      │
│                                                              │
│  learning_card_service.py  ← NEW: 卡片生成+缓存+AI调用 (~200行)│
│  knowledge_mapper.py       ← MODIFY: 映射后触发卡片失效 (~20行)│
│  library_pipeline.py       ← MODIFY: 处理后触发卡片失效 (~5行) │
└──────────────────────────┬───────────────────────────────────┘
                           │
                           ▼
┌──────────────────────────────────────────────────────────────┐
│                      MySQL (wzyProjectDb)                      │
│                                                              │
│  knowledge_learning_cards ← NEW: 学习卡片缓存                   │
│  problems.sub_topic_id    ← NEW: 可选题目标子知识点FK           │
│  ability_profile.parent_kp_ref ← NEW: 标准知识点名称引用        │
│  problems 种子数据         ← REPLACE: C语言→计算机网络 (~25题)  │
└──────────────────────────────────────────────────────────────┘
```

### 2.2 受影响的模块

| 模块 | 变更类型 | 文件数 |
|------|:--:|:--:|
| `database/migrations/` | 新增 2 个迁移 | 2 |
| `database/init_db.py` | 修改 | 1 |
| `server/` (服务层) | 新增 1 + 修改 2 | 3 |
| `server/` (API层) | 修改 1 | 1 |
| `static/` (前端 JS) | 修改 5 | 5 |
| `static/` (前端 HTML) | 修改 2 | 2 |
| `static/` (前端 CSS) | 修改 1 | 1 |
| `tests/` | 新增 2 + 修改 1 | 3 |

---

## 3. 关键架构决策 (ADR)

### ADR-1: 知识体系统一 — 软对齐 + 可选 FK

**背景**: 题库 `knowledge_point VARCHAR(100)` 和知识库 `knowledge_sub_topics.parent_kp VARCHAR(200)` 是两个独立体系。

**决策**: 采用**软对齐**策略：
- 保留 `problems.knowledge_point` 字段不变（向后兼容）
- 约定其取值必须是 `knowledge_sub_topics.parent_kp` 的有效值
- 新增 `problems.sub_topic_id` 可选 FK（精确映射到子知识点）
- 新增 `ability_profile.parent_kp_ref` 可选字段

**理由**:
- 不破坏现有选题策略和画像算法（它们基于 `knowledge_point` 字符串工作）
- 未来可渐进迁移到通过 `sub_topic_id` 精确关联
- 应用层通过 `knowledge_point` 字符串匹配即可关联两个体系

### ADR-2: 学习卡片缓存 — MySQL 持久化 + 变更自动失效

**背景**: 卡片由 AI 生成，成本高（每次 API 调用 ~2000 tokens），需要缓存。

**决策**: 
- 生成后写入 `knowledge_learning_cards` 表持久化
- 当资料更新时（新文档处理完成）→ 找到受影响的 `sub_topic_id` → 标记 `is_regenerating=1` → 下次访问时自动重新生成
- 不预生成所有 71 张卡片（浪费），采用**首次访问时生成**（lazy generation）

**替代方案**: 
- Redis 缓存：引入了额外依赖，StarPal 目前没有 Redis → 不选
- 预生成全部：浪费 API 调用（用户可能只访问 20% 的知识点）→ 不选

### ADR-3: 学练打通通信 — postMessage + 全局事件

**背景**: 做题在 iframe（exam.html）中，学习卡片在 Dashboard 主窗口。需要跨窗口通信。

**决策**:
- **exam → dashboard**: 使用现有 `window.parent.postMessage()` 机制，新增消息类型 `openLearningCard`
- **dashboard → exam**: 使用现有 postMessage，新增消息类型 `loadProblemsByKnowledgePoint`
- **dashboard 内联模块**（画像、知识图谱）: 直接调用 `DS.Library.openLearningCard(knowledgePoint)`

**现有 postMessage 协议参考**:
```javascript
// dashboard → exam (已有)
{type: 'loadProblemsByFilter', knowledgePoints: [...], difficulties: [...]}
{type: 'setProblems', problems: [...]}

// exam → dashboard (已有)  
{type: 'examFinished', ...}

// 新增: exam → dashboard
{type: 'openLearningCard', knowledgePoint: 'TCP连接管理'}

// 新增: dashboard → exam
{type: 'loadProblemsByKnowledgePoint', knowledgePoint: 'TCP连接管理'}
```

### ADR-4: AI 生成卡片 — 两阶段（同步 + SSE 流式）

**背景**: 精简版卡片内容短（~200 tokens 输出），完整版内容长（~1000+ tokens）。

**决策**:
- **精简版**: 同步 DeepSeek API 调用（用户等待 ~5-10s），因为内容短且必须立即可见
- **完整版**: SSE 流式 API 调用（首字节 < 3s，逐字渲染），用户可边等边读精简版
- 两种模式都复用现有的 DeepSeek 客户端（`AI_operate/deepseek_chat.py`）

**理由**: 精简版异步会导致骨架屏等待时间更长（先看到空白再等），同步等待在内容短时体验更好。

### ADR-5: 资料正文阅读 — AI 整理 + Markdown 缓存

**背景**: OCR 文本碎片化，需要整理成可读格式。

**决策**:
- 在现有 `knowledge_documents` 表新增 `readable_content MEDIUMTEXT` 列
- 用户首次点击「阅读」→ AI 接收所有 chunks → 整理段落/标题/图表占位 → 写入 `readable_content` → 前端 marked.js 渲染
- 同一文档多次阅读秒开（缓存命中）
- 与学习卡片共用同一 DeepSeek 客户端，使用同步调用（~20-30s 处理时间，显示进度条）

---

## 4. 数据模型变更

### 4.1 迁移 004: 知识体系统一

```sql
-- ============================================================
-- 迁移: 004_unify_knowledge_points
-- 描述: 统一题库与知识库知识点体系 + 替换测试数据
-- 日期: 2026-08-07
-- 回滚: 
--   ALTER TABLE problems DROP COLUMN sub_topic_id;
--   ALTER TABLE ability_profile DROP COLUMN parent_kp_ref;
--   重新执行 insert_test_data.sql 恢复 C 语言测试数据
-- ============================================================

-- Step 1: problems 表新增可选的子知识点外键
SET @col_exists := (
    SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS
    WHERE TABLE_SCHEMA = 'wzyProjectDb' AND TABLE_NAME = 'problems' AND COLUMN_NAME = 'sub_topic_id'
);
SET @sql := IF(@col_exists = 0,
    'ALTER TABLE problems ADD COLUMN sub_topic_id INT DEFAULT NULL COMMENT ''关联的子知识点ID（可选精确映射）'' AFTER knowledge_point,
     ADD INDEX idx_sub_topic (sub_topic_id)',
    'SELECT 1'
);
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

-- Step 2: ability_profile 新增标准知识点名称引用
SET @col2_exists := (
    SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS
    WHERE TABLE_SCHEMA = 'wzyProjectDb' AND TABLE_NAME = 'ability_profile' AND COLUMN_NAME = 'parent_kp_ref'
);
SET @sql2 := IF(@col2_exists = 0,
    'ALTER TABLE ability_profile ADD COLUMN parent_kp_ref VARCHAR(200) DEFAULT NULL COMMENT ''标准知识点名称（与knowledge_sub_topics.parent_kp对齐）'' AFTER knowledge_point',
    'SELECT 1'
);
PREPARE stmt2 FROM @sql2; EXECUTE stmt2; DEALLOCATE PREPARE stmt2;

-- Step 3: 清空旧 C 语言测试数据（外键级联）
SET FOREIGN_KEY_CHECKS = 0;
TRUNCATE TABLE user_answers;
TRUNCATE TABLE ability_profile;
TRUNCATE TABLE problems;
SET FOREIGN_KEY_CHECKS = 1;
UPDATE user SET user_strength = 0.5;

-- Step 4: 插入计算机网络测试题（25 题，覆盖主要知识点）
-- (具体题目由 backend-developer 编写，knowledge_point 使用 parent_kp 有效值)
```

### 4.2 迁移 005: 学习卡片表

```sql
-- ============================================================
-- 迁移: 005_learning_cards
-- 描述: 创建知识点学习卡片缓存表
-- 日期: 2026-08-07
-- 回滚: DROP TABLE IF EXISTS knowledge_learning_cards;
-- ============================================================

CREATE TABLE IF NOT EXISTS knowledge_learning_cards (
    card_id         INT AUTO_INCREMENT PRIMARY KEY COMMENT '卡片ID',
    sub_topic_id    INT NOT NULL COMMENT '关联的子知识点ID',
    user_id         INT DEFAULT NULL COMMENT 'NULL=系统级（使用系统资料），非NULL=个人级（使用个人资料）',
    
    -- 两级内容
    slim_content    JSON COMMENT '精简版: {definition, key_points[], source_docs[]}',
    full_content    MEDIUMTEXT COMMENT '完整版: Markdown格式完整讲解',
    
    -- 溯源
    source_chunk_ids JSON COMMENT '生成此卡片引用的chunk ID列表',
    generation_model VARCHAR(100) COMMENT '生成使用的模型标识',
    
    -- 状态
    slim_generated_at   TIMESTAMP NULL COMMENT '精简版生成时间',
    full_generated_at   TIMESTAMP NULL COMMENT '完整版生成时间',
    is_regenerating     TINYINT(1) DEFAULT 0 COMMENT '标记为待重新生成',
    
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    
    UNIQUE KEY uq_card_topic_user (sub_topic_id, user_id),
    FOREIGN KEY (sub_topic_id) REFERENCES knowledge_sub_topics(sub_topic_id) ON DELETE CASCADE,
    FOREIGN KEY (user_id) REFERENCES user(user_id) ON DELETE CASCADE,
    INDEX idx_user (user_id),
    INDEX idx_regenerating (is_regenerating)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='知识点学习卡片（AI生成的结构化学习内容）';
```

### 4.3 资料阅读内容缓存（扩展现有表）

```sql
-- 在 knowledge_documents 表新增阅读内容缓存列
ALTER TABLE knowledge_documents
ADD COLUMN readable_content MEDIUMTEXT COMMENT 'AI整理后的可读正文（Markdown）' AFTER status,
ADD COLUMN readable_generated_at TIMESTAMP NULL COMMENT '阅读版本生成时间' AFTER readable_content;
```

---

## 5. API 设计

### 5.1 新增端点总览

| 端点 | 方法 | 说明 | 响应类型 |
|------|------|------|:--:|
| `/api/library/learning-card/<sub_topic_id>` | GET | 获取/自动生成精简版学习卡片 | JSON |
| `/api/library/learning-card/<sub_topic_id>/expand` | GET | 生成/获取完整版卡片 | SSE 流 |
| `/api/library/learning-card/<sub_topic_id>/regenerate` | POST | 强制重新生成卡片 | JSON |
| `/api/library/documents/<doc_id>/readable` | GET | 获取/生成文档可读版本 | JSON/SSE |
| `/api/knowledge/parent-kps` | GET | 获取 25 个标准 parent_kp 列表 | JSON |

### 5.2 端点详情

#### `GET /api/library/learning-card/<sub_topic_id>`

**Query 参数**: `user_id` (0=系统, 其他=个人)

**逻辑**:
1. 查 `knowledge_learning_cards` 缓存
2. 命中且 `is_regenerating=0` → 直接返回 `slim_content`
3. 未命中或标记重新生成 → 收集该知识点关联 chunks → 调用 DeepSeek 同步生成 → 写入缓存 → 返回

**成功响应 (缓存命中)**:
```json
{
  "success": true,
  "card": {
    "sub_topic_id": 55,
    "sub_topic_name": "三次握手机制",
    "parent_kp": "TCP连接管理",
    "slim_content": {
      "definition": "TCP三次握手是...",
      "key_points": ["要点1", "要点2", "..."],
      "source_docs": [
        {"doc_id": 13, "title": "计算机网络（第8版）", "chunk_count": 5}
      ]
    },
    "has_full_content": true,
    "is_regenerating": false,
    "from_cache": true
  }
}
```

**成功响应 (首次生成)**:
```json
{
  "success": true,
  "card": { /* 同上 */ },
  "from_cache": false,
  "generated_in_ms": 8234
}
```

#### `GET /api/library/learning-card/<sub_topic_id>/expand`

**Query 参数**: `user_id`

**响应**: `text/event-stream` SSE 流

```
data: {"type": "start"}
data: {"type": "chunk", "content": "## 📖 详细讲解\n\nTCP..."}
data: {"type": "chunk", "content": "协议是一种面向连接的..."}
...
data: {"type": "done", "card_id": 42}
```

**逻辑**:
1. 检查 `full_content` 缓存 → 命中直接作为单个 chunk 返回
2. 未命中 → 加载精简版 + 原始 chunks → 流式调用 DeepSeek → 逐字推送 → 完成后写入缓存

#### `POST /api/library/learning-card/<sub_topic_id>/regenerate`

**Body**: `{"user_id": 0}`

**响应**:
```json
{"success": true, "message": "卡片已标记为重新生成，下次访问时将自动更新"}
```

**逻辑**: 标记 `is_regenerating=1`，清除 `slim_generated_at` 和 `full_generated_at`，不立即生成（下次用户访问时触发 lazy generation）。

#### `GET /api/library/documents/<doc_id>/readable`

**Query 参数**: `user_id`

**逻辑**:
1. 查 `knowledge_documents.readable_content` → 有则直接返回
2. 无 → 收集该文档所有 chunks（按 `chunk_index` 排序）→ 调用 AI 整理 → 写入 `readable_content` → 返回

**响应**: JSON，包含 Markdown 格式的可读内容。

#### `GET /api/knowledge/parent-kps`

**响应**:
```json
{
  "success": true,
  "parent_kps": [
    {"name": "计算机网络概述", "sub_topic_count": 4},
    {"name": "网络体系结构", "sub_topic_count": 3},
    ...
  ]
}
```

### 5.3 修改的端点

无现有端点行为变更。所有新增端点追加到 `library_api.py`。

---

## 6. 前端设计

### 6.1 新增组件: LearningCardModal

**文件**: `static/js/dashboard-library.js` (追加到现有 `DS.Library` 命名空间)

**核心类**:
```javascript
DS.Library.LearningCardModal = {
  _currentSubTopicId: null,
  _currentUserId: null,
  
  // 打开卡片（主入口）
  async open(subTopicId, userId, options = {}) {
    // options.from: 'graph' | 'list' | 'exam' | 'profile'
    // 1. 显示 Modal 骨架
    // 2. fetch /api/library/learning-card/<id>?user_id=...
    // 3. 渲染精简版内容
    // 4. 绑定「展开详细」按钮
  },
  
  // 展开完整版
  async _expandFull() {
    // 1. EventSource SSE 连接
    // 2. 逐字渲染 Markdown
    // 3. 完成后显示「收起」按钮
  },
  
  // 查看原始资料片段
  _showSourceChunks() { /* 展开被引用的原始 chunk 文本 */ },
  
  // 降级显示
  _renderFallback(chunks) { /* AI生成失败时显示原始拼接文本 */ },
  
  // 关闭
  close() { /* 隐藏 Modal，清理 SSE 连接 */ }
};
```

**Modal HTML 骨架** (放在 `dashboard.html` 中):
```html
<div id="learningCardModal" class="learning-card-modal" style="display:none;">
  <div class="learning-card-overlay"></div>
  <div class="learning-card-panel">
    <div class="learning-card-header">
      <h2 id="learningCardTitle">📌 知识点名称</h2>
      <div class="learning-card-header-actions">
        <button id="learningCardExpandBtn" class="btn-sm btn-outline">展开详细</button>
        <button id="learningCardCloseBtn" class="btn-icon"><i class="ri-close-line"></i></button>
      </div>
    </div>
    <div class="learning-card-body" id="learningCardBody">
      <!-- 精简版: 定义 + 要点 + 来源 -->
      <div id="learningCardSlim"></div>
      <!-- 完整版: SSE 流式渲染 -->
      <div id="learningCardFull" style="display:none;"></div>
      <!-- 降级: 原始 chunks -->
      <div id="learningCardFallback" style="display:none;"></div>
    </div>
    <div class="learning-card-footer">
      <button id="learningCardSourceBtn" class="btn-sm btn-text">查看原始资料片段</button>
      <button id="learningCardPracticeBtn" class="btn-sm btn-primary">📝 练习相关题目</button>
      <button id="learningCardChatBtn" class="btn-sm btn-outline">💬 不懂就问AI</button>
    </div>
  </div>
</div>
```

### 6.2 改造: 知识图谱节点点击

**文件**: `static/js/dashboard-library-graph.js`

**变更**: `onNodeClick(node)` 方法重写
```javascript
// 旧: 调用 /api/library/knowledge-node-detail → 展示关联文档列表
// 新: 调用 DS.Library.LearningCardModal.open(subTopicId, userId, {from: 'graph'})
// 学习卡片已内置了来源文档信息（slim_content.source_docs），不再需要旧的"下钻面板"
```

同时保留旧的 `/api/library/knowledge-node-detail` 端点用于卡片生成时的溯源。

### 6.3 改造: 知识清单行点击

**文件**: `static/js/dashboard-library-knowledge.js`

**变更**: 知识点行增加点击事件
```javascript
// 「按知识点」Tab 中的每一行
row.addEventListener('click', () => {
  const subTopicId = row.dataset.subTopicId;
  DS.Library.LearningCardModal.open(subTopicId, DS.userId || 0, {from: 'list'});
});
```

### 6.4 学练打通: 做题页 → 学习资料

**文件**: `static/exam.html` + `static/js/exam.js`

**变更**: 题目卡片下方增加知识点标签链接
```html
<!-- exam.html 题目区域增加 -->
<div class="exam-kp-link">
  知识点：<a href="#" id="examKpLink">TCP连接管理</a> 📚
</div>
```

```javascript
// exam.js
document.getElementById('examKpLink')?.addEventListener('click', (e) => {
  e.preventDefault();
  const kp = currentProblem.knowledge_point;
  window.parent.postMessage({
    type: 'openLearningCard',
    knowledgePoint: kp
  }, '*');
});
```

**Dashboard 接收**:
```javascript
// dashboard.js 的 message 监听器中新增
if (data.type === 'openLearningCard') {
  // 根据 knowledge_point 查找对应的 sub_topic_id → 打开卡片
  DS.Library.openLearningCardByKp(data.knowledgePoint);
}
```

### 6.5 学练打通: 学习卡片 → 选题

**实现**: 学习卡片 Modal 底部的 `[📝 练习相关题目]` 按钮
```javascript
// LearningCardModal 中
_practiceRelated() {
  const kp = this._currentParentKp;
  // 如果 exam 是 iframe
  const examFrame = document.getElementById('iframe-exam');
  examFrame?.contentWindow?.postMessage({
    type: 'loadProblemsByKnowledgePoint',
    knowledgePoint: kp
  }, '*');
  // 切换到做题 section
  DS.switchSection('exam');
  this.close();
}
```

### 6.6 学练打通: 能力画像 → 学习/练题

**文件**: `static/js/dashboard.js` (画像内联渲染部分)

**变更**: 薄弱知识点（proficiency < 0.6）旁增加操作按钮
```javascript
// 渲染能力画像知识点列表时
if (proficiency < 0.6) {
  return `
    <span class="kp-name">${kp}</span>
    <span class="kp-level weak">${proficiency.toFixed(1)}</span>
    <button class="kp-action-btn" data-action="learn" data-kp="${kp}">📖</button>
    <button class="kp-action-btn" data-action="practice" data-kp="${kp}">📝</button>
  `;
}
```

---

## 7. 服务层设计

### 7.1 `learning_card_service.py` 核心函数签名

```python
from typing import Optional, Dict, Generator

class LearningCardService:
    """知识点学习卡片服务：生成、缓存、失效管理。"""
    
    @staticmethod
    def get_or_generate_slim(
        sub_topic_id: int, 
        user_id: Optional[int] = None
    ) -> Dict:
        """
        获取或生成精简版卡片。
        
        1. 查 MySQL 缓存 → 命中且未标记重新生成 → 返回
        2. 收集该知识点 chunks（按 user_id 过滤来源文档）
        3. 拼接 chunks 文本
        4. 同步调用 DeepSeek API 生成结构化 JSON
        5. 写入 knowledge_learning_cards
        6. 返回 {slim_content, has_full_content, from_cache, ...}
        """
    
    @staticmethod
    def generate_full_stream(
        sub_topic_id: int,
        user_id: Optional[int] = None
    ) -> Generator[str, None, None]:
        """
        SSE 流式生成完整版卡片。
        
        1. 检查 full_content 缓存 → 有则一次性 yield
        2. 加载 slim_content + 原始 chunks
        3. 流式调用 DeepSeek
        4. 逐 chunk yield SSE 格式字符串
        5. 完成后写入 MySQL full_content
        """
    
    @staticmethod
    def mark_for_regeneration(sub_topic_id: int, user_id: Optional[int] = None) -> bool:
        """标记卡片为待重新生成。"""
    
    @staticmethod
    def invalidate_cards_for_document(doc_id: int) -> int:
        """
        文档更新后，找到所有引用此文档的卡片并标记重新生成。
        返回受影响的卡片数量。
        
        SQL:
        UPDATE knowledge_learning_cards 
        SET is_regenerating = 1 
        WHERE JSON_CONTAINS(source_chunk_ids, 
            (SELECT JSON_ARRAYAGG(chunk_id) FROM knowledge_chunks WHERE doc_id = %s)
        )
        """
    
    @staticmethod
    def get_batch_status(user_id: Optional[int] = None) -> list[Dict]:
        """获取所有子知识点的卡片生成状态（用于管理/预生成）。"""

    @staticmethod
    def _build_slim_prompt(sub_topic_name, parent_kp_desc, chunks_text) -> str:
        """构造精简版 AI prompt。"""

    @staticmethod
    def _build_full_prompt(sub_topic_name, parent_kp_desc, chunks_text, slim_content) -> str:
        """构造完整版 AI prompt。"""
```

### 7.2 知识映射→卡片失效的联动

**文件**: `server/knowledge_mapper.py`

在 `analyze_document()` 完成后追加：
```python
# 知识点映射完成后，失效该文档覆盖的所有知识点的学习卡片
from server.learning_card_service import LearningCardService
affected = LearningCardService.invalidate_cards_for_document(doc_id)
if affected > 0:
    print(f"[knowledge_mapper] {affected} 张学习卡片已标记为待重新生成")
```

**文件**: `server/library_pipeline.py`

在 `process_upload()` 的最后一步（知识点映射完成后）同样调用。

---

## 8. 测试策略

| 测试类型 | 测试内容 | 覆盖文件 | Agent |
|---------|---------|---------|:--:|
| 单元测试 | `LearningCardService` 缓存命中/未命中/失效逻辑 | `tests/unit/test_learning_card_service.py` | tester |
| 单元测试 | `_build_slim_prompt` / `_build_full_prompt` 输出格式 | 同上 | tester |
| 单元测试 | `invalidate_cards_for_document` SQL 正确性 | 同上 | tester |
| 集成测试 | `GET /api/library/learning-card/<id>` 返回结构 | `tests/integration/test_api_learning_cards.py` | tester |
| 集成测试 | SSE 展开端点流式响应格式 | 同上 | tester |
| 集成测试 | 重新生成端点标记逻辑 | 同上 | tester |
| 集成测试 | 学练跳转 API 参数正确性 | `tests/integration/test_api_library.py` (追加) | tester |
| 手动测试 | 8 条验收标准 (AC-C01~C07 + AC-D01~D04) | 验收清单 | tester |

**Mock 策略**:
- DeepSeek API: 使用 `responses` 库 mock，返回固定 JSON（精简版）和固定 Markdown（完整版）
- ChromaDB: 不涉及（卡片基于 MySQL chunks 生成）
- 数据库: 使用 `wzyProjectDb_test` 独立库

---

## 9. 安全审查清单

- [ ] `learning_card_service.py` 中 DeepSeek API Key 从环境变量读取（复用现有 `AI_operate/deepseek_chat.py`）
- [ ] API 端点参数验证：`sub_topic_id` 整数范围、`user_id` 权限校验
- [ ] 个人卡片仅本人可访问（`user_id` 参数校验）
- [ ] SQL 全部参数化（无字符串拼接）
- [ ] AI 生成内容在前端渲染前做 XSS 过滤（marked.js 默认转义 HTML）
- [ ] 错误响应不泄露 API Key / 文件路径 / 堆栈

---

## 10. Agent 分工总览

```
Phase 0: architect          → 技术规格评审 (本轮已完成)
                               
Phase 1: backend-developer  → 数据库迁移 (2个迁移文件 + init_db更新)
         使用 skill: add-database-migration
                               
Phase 2: backend-developer  → 服务层 (learning_card_service.py + 联动修改)
                               
Phase 3: backend-developer  → API层 (4个新端点 + parent-kps端点)
         使用 skill: add-api-endpoint
                               
Phase 4: frontend-developer → 前端全部变更 (6个JS文件 + 2个HTML + CSS)
         使用 skill: add-frontend-page
                               
Phase 5: tester             → 测试 (单元 + 集成 + 手动清单)
         使用 skill: write-tests
                               
Phase 6: reviewer           → 代码审查 (6维度)
         使用 skill: code-review
                               
Phase 7: architect + tester → 集成验证 + 冒烟测试
```

**并行机会**:
- Phase 4 (前端) 可在 Phase 3 (API签名冻结后) 启动，与 Phase 5 (测试计划) 并行
- Phase 5 的测试计划可在 Phase 0 后提前编写

---

> **下一步**: 确认技术规格 → 进入任务分解 → 启动 Phase 1 开发