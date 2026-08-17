# 任务分解: 个人资料库 (Personal Library)

> 关联 PRD: [PRD-个人资料库.md](PRD-个人资料库.md) | 版本: 1.1 | 创建日期: 2026-08-04
>
> **目标**: 一次性交付双轨知识库系统（系统知识库 + 个人资料库），含：管理员上传系统教材、用户上传个人资料、统一知识图谱+维度下钻（方案C）、双Tab知识清单、RAG检索范围切换。完整测试覆盖、代码审查、排错机制。

---

## 目录

- [Agent 分工总览](#agent-分工总览)
- [依赖关系图](#依赖关系图)
- [Phase 0: 架构设计](#phase-0-架构设计)
- [Phase 1: 数据库迁移](#phase-1-数据库迁移)
- [Phase 2: 后端服务层](#phase-2-后端服务层)
- [Phase 3: 后端 API 路由层](#phase-3-后端-api-路由层)
- [Phase 4: 前端页面](#phase-4-前端页面)
- [Phase 5: 测试](#phase-5-测试)
- [Phase 6: 代码审查](#phase-6-代码审查)
- [Phase 7: 集成验证与交付](#phase-7-集成验证与交付)
- [排错机制](#排错机制)
- [统计总览](#统计总览)

---

## Agent 分工总览

| Agent | 角色 | 负责 Phase | 核心职责 |
|-------|------|-----------|---------|
| **architect** | 系统架构师 | Phase 0 | 技术规格设计、架构决策、接口定义 |
| **requirement-analyst** | 需求分析师 | Phase 0 | PRD 评审、验收标准确认、边缘场景补充 |
| **backend-developer** | 后端开发者 | Phase 1-3 | 数据库迁移、服务层、API 路由（全部 Python 代码） |
| **frontend-developer** | 前端开发者 | Phase 4 | HTML/CSS/JS 页面与组件（全部前端代码） |
| **tester** | 测试工程师 | Phase 5 | 测试策略、单元测试、集成测试、手动测试清单 |
| **reviewer** | 代码审查员 | Phase 6 | 6 维度全面审查（安全/正确性/性能/风格/文档/测试） |

### 协作模式

```
architect + requirement-analyst  →  Phase 0（并行，产出 tech-spec）
              │
              ▼
      backend-developer  →  Phase 1 → Phase 2 → Phase 3（串行，DB→服务→路由）
              │
              ├──→  frontend-developer  →  Phase 4（可与 Phase 2-3 有限并行，依赖 API 签名确定后）
              │
              ▼
          tester  →  Phase 5（Phase 3+4 完成后全量测试）
              │
              ▼
         reviewer  →  Phase 6（Phase 5 全部通过后审查）
              │
              ▼
     architect + tester  →  Phase 7（集成验证 + 冒烟测试）
```

---

## 依赖关系图

```
Phase 0 (架构设计)
  │
  ├─→ Phase 1 (数据库迁移)
  │     │
  │     └─→ Phase 2 (后端服务层)
  │           │
  │           ├─→ Phase 3 (后端 API 路由层)
  │           │     │
  │           │     └─→ Phase 4 (前端页面) ──→ Phase 5 (测试) ──→ Phase 6 (审查) ──→ Phase 7 (交付)
  │           │
  │           └─→ (Phase 4 可在 API 签名冻结后并行启动)
  │
  └─→ (Phase 5 的测试计划可在 Phase 0 后提前编写)
```

---

## Phase 0: 架构设计

> **Agent**: architect + requirement-analyst（并行执行）
> **退出条件**: 技术规格文档获用户批准

### T0.1 — PRD 最终评审
- **Agent**: requirement-analyst
- **输入**: `docs/PRD-个人资料库.md`
- **产出**: PRD 评审报告（确认/修正/补充项清单）
- **检查点**:
  - 验收标准是否可量化、可验证？
  - 边缘场景覆盖是否完整（空状态/失败/重复/超大文件/不支持格式）？
  - 与现有系统（知识库 API、RAG 服务、做题流程）的交互点是否明确？
- **预估**: 不产出代码，纯审查

### T0.2 — 技术规格设计
- **Agent**: architect
- **输入**: PRD + 现有代码库分析
- **产出**: 技术规格文档（写入 `docs/tech-spec-个人资料库.md`）
- **必须覆盖的决策点**:
  1. **文件存储策略**: 上传目录路径（`uploads/<user_id>/`）、非 Web 可访问保证
  2. **后台处理架构**: threading 线程 vs 后续迁移 Celery（推荐：当前用 threading，预留 Celery 接口）
  3. **ChromaDB 多用户隔离**: 单 collection + metadata 过滤 `{"user_id": str}`，系统资料 `user_id="system"`，个人资料 `user_id="<真实ID>"`
  4. **知识点映射算法**: 嵌入向量预计算 + 缓存策略
  5. **前端架构**:
     - Dashboard 内联 section「我的资料库」（与 exam/profile/wrong/chat 平级）
     - 管理后台 (admin.html) 新增「系统知识库」板块（仅管理员可见）
  6. **SSE 进度推送**: 复用现有 SSE 模式（参考 `/api/explain/stream`）
  7. **文件类型检测**: MIME type + python-magic 文件头双重验证
  8. **双轨知识架构**: `user_id` 参数区分系统/个人（`NULL`=系统, 具体值=个人），共用同一套处理管线
  9. **统一知识图谱（方案C）**: 所有同轨资料合并为一张图谱，节点点击下钻查看各文档贡献
- **预估**: 不产出代码，纯设计

### Phase 0 检查点
```bash
# 验证 PRD 与技术规格一致性
grep -c "AC-" docs/PRD-个人资料库.md   # 应输出 11（11 条验收标准: AC-S01~S02 + AC-01~03 + AC-A01~A06 + AC-B01~B03）
grep -c "API" docs/tech-spec-个人资料库.md  # 应覆盖全部 API 端点（含新增的节点下钻端点）
```

---

## Phase 1: 数据库迁移

> **Agent**: backend-developer
> **依赖**: Phase 0 完成
> **关键约束**: 迁移必须幂等（可重复执行不报错）

### T1.1 — 创建迁移文件 `003_library.sql`
- **文件**: `database/migrations/003_library.sql`
- **内容**:
  1. 创建 `library_tasks` 表（含所有字段、索引、外键）
  2. `knowledge_documents` 新增 `user_id` 列（含外键、索引）
  3. 使用 `IF NOT EXISTS` / 动态列检测保证幂等
- **预估**: ~60 行
- **验证**: 
  ```sql
  -- 迁移后可检查
  DESC library_tasks;
  SHOW COLUMNS FROM knowledge_documents LIKE 'user_id';
  ```

### T1.2 — 更新 `init_db.py`
- **文件**: `database/init_db.py`
- **内容**: 添加 `003_library.sql` 到迁移执行列表
- **预估**: ~3 行
- **验证**: `python database/init_db.py` 无报错，9→11 张表

### Phase 1 检查点
```bash
python database/init_db.py
# 预期输出: 迁移 003_library.sql 执行成功
# MySQL 表数: 5(原有) + 4(knowledge) + 1(library_tasks) = 10 张表
# knowledge_documents 新增 user_id 列
```

---

## Phase 2: 后端服务层

> **Agent**: backend-developer
> **依赖**: Phase 1 完成
> **原则**: 每个服务文件 < 200 行，独立可测

### T2.1 — 文件处理服务 `file_handler.py`
- **文件**: `server/file_handler.py`（新建）
- **职责**: 文件类型检测 + 文本提取调度
- **核心函数**:
  - `detect_file_type(file_path, mime_type) -> str`: 返回 `'scanned_pdf'|'text_pdf'|'word'`
  - `extract_text(file_path, file_type) -> str`: 调度到对应提取器
  - `validate_file(file_path, mime_type, max_size_mb=200) -> tuple[bool, str]`: 安全校验
- **依赖**: PyMuPDF, python-docx, PaddleOCR（从 `tools/pdf_ocr/` 复用）
- **预估**: ~120 行
- **关键安全措施**:
  - MIME type + 文件头魔数双重校验
  - 白名单：仅 `application/pdf`, `application/vnd.openxmlformats-officedocument.wordprocessingml.document`
  - 文件大小限制 200MB

### T2.2 — 知识点映射服务 `knowledge_mapper.py`
- **文件**: `server/knowledge_mapper.py`（新建）
- **职责**: 文本块 → 知识点自动映射
- **核心逻辑**:
  1. 从 MySQL 加载 71 个子知识点及其描述
  2. 调用 `EmbeddingService` 批量生成文本块向量
  3. 计算余弦相似度 → 取 top-3（阈值 0.6）
  4. 写入 `knowledge_chunks.sub_topic_id`
  5. 汇总生成覆盖报告
- **关键设计**:
  - 子知识点向量在首次调用时预计算并内存缓存（避免每次映射重复计算）
  - 支持 `analyze_document(doc_id)` 和 `get_user_coverage(user_id)` 两个入口
- **预估**: ~150 行
- **依赖**: `AI_operate/embedding_service.py` 和 `AI_operate/rag_service.py`

### T2.3 — 文档处理管线编排器 `library_pipeline.py`
- **文件**: `server/library_pipeline.py`（新建）
- **职责**: 端到端处理管线编排 + 进度追踪
- **核心类**: `LibraryPipeline`
  - `process_upload(task_id, user_id, file_path, file_name, file_type, doc_type)` — 完整管线
  - 管线步骤:
    1. 创建/更新 `library_tasks` 记录（status=processing）
    2. 文本提取（`file_handler.extract_text`）
    3. 创建 `knowledge_documents` 记录
    4. 智能分块（`EmbeddingService.chunk_document`）
    5. 写入 `knowledge_chunks`（MySQL） + 向量索引（ChromaDB，带 `user_id` metadata）
    6. 知识点映射（`knowledge_mapper.analyze_document`）
    7. 更新 `library_tasks`（status=completed, progress=100）
  - 每步通过回调更新进度 `progress_callback(pct, detail)`
  - 异常捕获：任何步骤失败 → 标记 status=failed + error_message
- **预估**: ~180 行

### T2.4 — 复用/适配现有模块
- **文件**: `AI_operate/rag_service.py`（修改）
- **内容**: `search()` 方法新增 `user_id` 参数支持
  - `user_id=None` → 检索系统知识库（现有行为）
  - `user_id=int` → ChromaDB 查询加 `where={"user_id": str(user_id)}` 过滤
- **预估**: ~30 行修改
- **文件**: `tools/pdf_ocr/` → 复用 `ocr_engine.py`, `pdf_processor.py`，不修改

### Phase 2 检查点
```bash
# 单元级验证（每个服务文件可独立导入）
python -c "from server.file_handler import detect_file_type, validate_file; print('OK')"
python -c "from server.knowledge_mapper import KnowledgeMapper; print('OK')"
python -c "from server.library_pipeline import LibraryPipeline; print('OK')"

# RAG 服务 user_id 过滤验证
python -c "
from AI_operate.rag_service import RAGService
r = RAGService()
# 验证 search 方法签名接受 user_id 参数
import inspect
sig = inspect.signature(r.search)
assert 'user_id' in sig.parameters, 'search() 缺少 user_id 参数'
print('OK')
"
```

---

## Phase 3: 后端 API 路由层

> **Agent**: backend-developer
> **依赖**: Phase 2 完成
> **原则**: 每个端点遵守 RESTful 规范，参数验证在路由入口完成

### T3.1 — 资料库 Blueprint `library_api.py`
- **文件**: `server/library_api.py`（新建）
- **内容**: 8 个 API 端点（详见下方），注册为 Flask Blueprint `library_bp`
- **预估**: ~180 行

#### T3.1.1 — `POST /api/library/upload`
- **请求**: multipart/form-data
  - `file`: 文件（必填）
  - `user_id`: 0=系统知识库（管理员），其他=个人用户（必填）
  - `doc_type`: textbook/rfc/paper/note/other（可选，默认 other）
  - `title`: 文档标题（可选，默认取文件名）
- **处理流程**:
  1. 文件验证（类型+大小）
  2. `user_id=0` → 保存到 `uploads/system/<uuid>_<filename>`，`knowledge_documents.user_id = NULL`
  3. `user_id>0` → 保存到 `uploads/<user_id>/<uuid>_<filename>`，`knowledge_documents.user_id = user_id`
  4. 生成 task_id（UUID）
  5. 插入 `library_tasks` 记录（status=pending）
  6. 启动后台线程执行 `LibraryPipeline.process_upload(task_id, ...)`
  7. 立即返回 `{"success": true, "task_id": "..."}`
- **响应时间**: < 2s（仅文件保存+记录创建，不等待处理）

#### T3.1.2 — `GET /api/library/progress/<task_id>`
- **响应**: SSE 流式推送进度
  ```
  data: {"progress_pct": 15, "detail": {"step": "extracting", "page": 3, "total": 20}}
  data: {"progress_pct": 50, "detail": {"step": "chunking"}}
  data: {"progress_pct": 80, "detail": {"step": "indexing"}}
  data: {"progress_pct": 100, "detail": {"step": "completed"}, "doc_id": 42}
  data: [DONE]
  ```
- **实现**: 轮询 `library_tasks` 表 progress_pct（500ms 间隔），或订阅 threading.Event

#### T3.1.3 — `GET /api/library/documents`
- **参数**: `user_id` (必填), `page` (默认 1), `page_size` (默认 20)
  - `user_id=0` → 系统知识库文档（`knowledge_documents.user_id IS NULL`）
  - `user_id>0` → 个人资料库文档（`knowledge_documents.user_id = user_id`）
- **响应**:
  ```json
  {
    "success": true,
    "documents": [{
      "doc_id": 42, "title": "计算机网络第5章",
      "doc_type": "textbook", "file_size_bytes": 15200000,
      "status": "completed", "chunk_count": 32,
      "uploaded_at": "2026-08-04 10:30:00"
    }],
    "total": 3, "page": 1, "page_size": 20
  }
  ```

#### T3.1.4 — `DELETE /api/library/documents/<doc_id>`
- **处理**: 级联删除
  1. 从 ChromaDB 删除该文档所有 chunk 向量
  2. MySQL `knowledge_chunks` ON DELETE CASCADE（由外键自动处理）
  3. MySQL `knowledge_documents` 删除
  4. 物理文件删除（`uploads/<user_id>/` 下对应文件）
  5. `library_tasks` 关联记录标记为已删除（或物理删除）
- **权限**: 验证 `knowledge_documents.user_id` == 请求 `user_id`

#### T3.1.5 — `GET /api/library/knowledge-coverage`
- **参数**: `user_id` (必填)
- **响应**:
  ```json
  {
    "success": true,
    "coverage": {
      "total_sub_topics": 71,
      "covered_count": 23,
      "coverage_pct": 32.4,
      "details": [
        {
          "sub_topic_id": 1, "sub_topic_name": "TCP三次握手",
          "parent_kp": "TCP连接管理", "status": "covered",
          "chunk_count": 5, "doc_count": 2
        },
        {
          "sub_topic_id": 2, "sub_topic_name": "UDP协议特点",
          "parent_kp": "传输层协议", "status": "uncovered",
          "chunk_count": 0, "doc_count": 0
        }
      ]
    }
  }
  ```

#### T3.1.6 — `GET /api/library/knowledge-graph`
- **参数**: `user_id` (必填)
- **响应**:
  ```json
  {
    "success": true,
    "nodes": [
      {"id": "TCP连接管理", "name": "TCP连接管理", "category": 0, "symbolSize": 50, "coverage": 0.8},
      {"id": "UDP协议", "name": "UDP协议", "category": 0, "symbolSize": 20, "coverage": 0.1}
    ],
    "links": [
      {"source": "TCP连接管理", "target": "UDP协议", "label": "对比"}
    ],
    "categories": [
      {"name": "已覆盖", "itemStyle": {"color": "#22C55E"}},
      {"name": "部分覆盖", "itemStyle": {"color": "#F59E0B"}},
      {"name": "未覆盖", "itemStyle": {"color": "#6B7280"}}
    ]
  }
  ```

#### T3.1.7 — `POST /api/library/analyze/<doc_id>`
- **用途**: 手动触发或重试知识点映射（处理管线自动调用，此端点作为手动重试入口）
- **响应**: 返回映射结果摘要
- **幂等**: 已映射的 chunk 可被覆盖更新

#### T3.1.8 — `GET /api/library/knowledge-node-detail`
- **参数**: `sub_topic_id` (必填), `user_id` (必填，0=系统)
- **用途**: 知识图谱节点点击 → 下钻查看该知识点关联的所有文档及内容
- **响应**:
  ```json
  {
    "success": true,
    "sub_topic_name": "TCP三次握手",
    "documents": [
      {
        "doc_id": 42, "title": "计算机网络第5章",
        "doc_type": "textbook", "chunk_count": 3,
        "chunks_preview": [
          {"chunk_id": 101, "content": "TCP连接建立需要经过三次握手..."},
          {"chunk_id": 102, "content": "第一次握手：客户端发送SYN=1..."}
        ]
      },
      {
        "doc_id": 57, "title": "TCP协议笔记",
        "doc_type": "note", "chunk_count": 1,
        "chunks_preview": [{"chunk_id": 203, "content": "三次握手的关键是..."}]
      }
    ]
  }
  ```

### T3.2 — 注册 Blueprint
- **文件**: `server/app.py`（修改）
- **内容**:
  1. 导入 `library_bp` 
  2. `app.register_blueprint(library_bp)`
  3. 配置上传目录 `UPLOAD_FOLDER`
- **预估**: ~15 行修改

### T3.3 — 改造 `/api/chat` 支持知识范围切换
- **文件**: `server/app.py`（修改，chat 路由部分）
- **内容**: 
  1. `POST /api/chat` 新增 `knowledge_scope` 参数（`"system"|"personal"`，默认 `"system"`）
  2. `knowledge_scope="personal"` 时调用 `rag.search(..., user_id=user_id)`
  3. SSE 流中 sources 标注来源类型（`source_type: "system"|"personal"`）
- **预估**: ~30 行修改

### Phase 3 检查点
```bash
# 启动 Flask 后验证 Blueprint 注册
curl -s http://127.0.0.1:3001/ | head -1

# 验证每个端点（需登录态/参数）
curl -s -o /dev/null -w "%{http_code}" "http://127.0.0.1:3001/api/library/documents?user_id=1"
# 预期: 200

# 验证 chat knowledge_scope 参数
curl -s -X POST http://127.0.0.1:3001/api/chat \
  -H "Content-Type: application/json" \
  -d '{"user_id":1,"question":"测试","knowledge_scope":"system"}' | head -5
# 预期: 200 + SSE 流
```

---

## Phase 4: 前端页面

> **Agent**: frontend-developer
> **依赖**: Phase 3 API 签名冻结（T3.1 完成后即可开始，与 T3.2/T3.3 可有限并行）
> **原则**: 每个 JS 类 < 200 行，使用 ES6 class 封装

### T4.1 — 侧边栏入口 + CSS 样式
- **文件**: `static/dashboard.html`（修改）
- **内容**: 侧边栏新增「📚 我的资料库」导航项
  ```html
  <button class="nav-item" data-section="library">
    <i class="ri-folder-2-line"></i> <span>我的资料库</span>
  </button>
  ```
- **预估**: ~5 行

- **文件**: `static/assets/starpal-style.css`（修改）
- **内容**: 新增资料库页面全部样式
  - `.library-upload-zone` — 拖拽上传区域（虚线边框 + hover 高亮）
  - `.library-doc-list` — 文档列表卡片
  - `.library-doc-status` — 状态标签（processing/completed/failed 三色）
  - `.library-progress-bar` — 进度条组件
  - `.library-coverage-ring` — 覆盖度环形图容器
  - `.library-graph-container` — 知识图谱全屏容器
  - `.library-empty-state` — 空状态引导页
  - `.library-scope-toggle` — 检索范围切换控件
- **预估**: ~150 行

### T4.2 — 资料库 JS 模块 `dashboard-library.js`
- **文件**: `static/js/dashboard-library.js`（新建）
- **核心类**: `LibraryModule`
- **功能清单**:
  - `init()` — 初始化上传区域事件（drag/drop/click）
  - `handleFileSelect(file)` — 文件类型/大小前端预检
  - `uploadFile(file, metadata)` — FormData 上传 + 启动进度监听
  - `subscribeProgress(taskId)` — EventSource SSE 进度订阅 → UI 更新
  - `loadDocumentList()` — 加载并渲染文档列表
  - `deleteDocument(docId)` — 确认对话框 + 删除 + 刷新列表
  - `renderEmptyState()` — 空状态引导
  - `renderDocumentCard(doc)` — 单个文档卡片渲染
- **预估**: ~180 行

### T4.3 — 知识清单 + 覆盖度 `dashboard-library-knowledge.js`
- **文件**: `static/js/dashboard-library-knowledge.js`（新建）
- **核心类**: `LibraryKnowledgeModule`
- **功能清单**:
  - **双 Tab 视图切换**：
    - Tab「🏷️ 按知识点」：知识点覆盖清单表格（默认视图，所有资料合并），展开行显示各文档贡献（**下钻**）
    - Tab「📄 按资料」：每份资料独立覆盖的知识点列表（反向视图）
  - `loadCoverage()` — 加载覆盖数据 → 渲染知识清单表格 + 环形图
  - `renderCoverageRing(pct)` — ECharts 环形图
  - `renderKnowledgeTable(coverageData)` — 按知识点视图
  - `renderDocView(docId)` — 按资料视图
  - `expandRow(subTopicId)` — 展开行 → 加载节点下钻详情（调用 `/api/library/knowledge-node-detail`）
  - `filterByParentKp(kp)` — 按粗粒度知识点筛选
- **预估**: ~170 行

### T4.4 — 知识图谱 `dashboard-library-graph.js`
- **文件**: `static/js/dashboard-library-graph.js`（新建）
- **核心类**: `LibraryGraphModule`
- **技术选型**: ECharts `type: 'graph'`（力导向图）
- **核心设计**: **统一知识图谱** — 所有同轨资料（系统/个人）合并为**一张图**
- **功能清单**:
  - `loadGraph(userId)` — 加载图谱数据（所有资料合并的节点+连线） → ECharts 渲染
  - `initChart()` — ECharts 初始化 + 力导向参数 + 颜色映射（绿/黄/灰=覆盖度）
  - `onNodeClick(node)` — **节点下钻**：点击节点 → 调用 `/api/library/knowledge-node-detail` → 弹出详情面板
    - 展示：关联文档列表、各文档贡献 chunk 数、前 3 块内容摘要
    - 「查看完整内容」链接可跳转到对应文档
  - `highlightUncovered()` — 高亮按钮：闪烁未覆盖的核心知识点节点 → 引导用户上传
  - `renderLegend()` — 图例：绿色=已覆盖 / 黄色=部分覆盖 / 灰色=未覆盖
- **预估**: ~180 行

### T4.5 — AI 对话检索切换
- **文件**: `static/js/dashboard-chat.js`（修改）
- **内容**:
  1. 输入框上方新增 SegmentedControl：「🌐 系统知识库 | 📚 我的资料」
  2. 发送消息时携带 `knowledge_scope` 参数
  3. 切换时检查：若切到「我的资料」且用户无资料 → 显示引导提示
  4. 来源卡片区分系统/个人标签颜色
- **预估**: ~50 行修改

### T4.6 — Dashboard 集成
- **文件**: `static/dashboard.html`（修改）
- **内容**: 新增 `<section id="section-library">` 区域，含 HTML 骨架：
  - 上传区域（drag-drop zone）
  - 文档列表容器
  - 知识清单双 Tab（🏷️ 按知识点 / 📄 按资料）+ 环形图 + 统一知识图谱大容器
- **预估**: ~60 行
- **文件**: `static/js/dashboard.js`（修改）
- **内容**:
  1. 注册 `library` section 切换逻辑
  2. 首次点击「我的资料库」→ 延迟初始化 LibraryModule
  3. 懒加载 ECharts（与现有能力画像图表加载逻辑一致）
- **预估**: ~30 行修改

### T4.7 — 管理后台系统知识库上传
- **文件**: `static/admin.html`（修改）
- **内容**: 新增「系统知识库」板块
  - 上传区域（拖拽 + 点击选择），面向扫描 PDF/文字 PDF/Word
  - 系统文档列表（处理状态、进度条、删除/重传）
  - 上传提示：「请上传权威教材资料，如《计算机网络》(谢希仁 第8版) 扫描版 PDF」
- **文件**: `static/js/admin.js`（修改）
- **内容**:
  - 复用 `LibraryModule` 的核心逻辑（或独立内联实现）
  - `initSystemLibrary()` — 初始化系统知识库模块
  - `uploadSystemDoc(file, metadata)` — 上传时 `user_id=0`
  - `loadSystemDocuments()` — 加载系统文档列表
  - `deleteSystemDoc(docId)` — 删除系统文档
- **预估**: ~100 行（HTML ~40 + JS ~60）

### Phase 4 检查点
```bash
# 验证所有新文件存在
ls static/js/dashboard-library.js
ls static/js/dashboard-library-knowledge.js
ls static/js/dashboard-library-graph.js

# JS 语法检查
node --check static/js/dashboard-library.js
node --check static/js/dashboard-library-knowledge.js
node --check static/js/dashboard-library-graph.js
node --check static/js/admin.js

# 验证 HTML 中 CSS/JS 引用正确
grep "dashboard-library" static/dashboard.html
grep "section-library" static/dashboard.html
grep "system-library" static/admin.html
```

---

## Phase 5: 测试

> **Agent**: tester
> **依赖**: Phase 3（后端 API）+ Phase 4（前端页面）完成
> **原则**: 新代码覆盖率 ≥ 90%，关键路径覆盖率 100%

### T5.1 — 测试基础设施搭建
- **文件**: `tests/conftest.py`（修改/新建）
- **内容**:
  - `test_app` fixture: 创建带 `library_bp` 的测试 Flask 应用
  - `test_db` fixture: 使用 `wzyProjectDb_test` 测试数据库，自动建表/拆表
  - `mock_embedding` fixture: Mock `EmbeddingService` 返回固定 384 维向量
  - `mock_deepseek` fixture: Mock DeepSeek API 响应
  - `sample_pdf` fixture: 生成最小合法 PDF 用于上传测试
  - `sample_docx` fixture: 生成最小合法 DOCX 用于上传测试
  - `test_user` fixture: 创建测试用户并返回 user_id
- **预估**: ~120 行

### T5.2 — 后端单元测试

#### T5.2.1 — `tests/unit/test_file_handler.py`
- **测试用例** (~80 行):
  - `test_detect_pdf_by_mime` — MIME 识别 PDF
  - `test_detect_docx_by_mime` — MIME 识别 DOCX
  - `test_reject_exe_file` — 拒绝可执行文件
  - `test_reject_oversize_file` — 拒绝 >200MB 文件
  - `test_reject_empty_file` — 拒绝 0 字节文件
  - `test_validate_whitelist_mime` — 白名单校验
  - `test_extract_text_pdf_success` — 文字 PDF 提取
  - `test_extract_text_docx_success` — Word 提取
- **预估**: ~100 行

#### T5.2.2 — `tests/unit/test_knowledge_mapper.py`
- **测试用例** (~80 行):
  - `test_map_chunk_to_subtopic_above_threshold` — 相似度 >0.6 正确映射
  - `test_map_chunk_below_threshold_returns_none` — 相似度 <0.6 无映射
  - `test_map_chunk_top3_candidates` — 返回 top-3 候选
  - `test_get_user_coverage_empty` — 新用户覆盖度为 0
  - `test_get_user_coverage_with_data` — 有资料后计算正确
  - `test_coverage_pct_calculation` — 百分比计算正确
  - `test_cache_subtopic_embeddings` — 向量缓存（二次调用不重复计算）
- **预估**: ~110 行

#### T5.2.3 — `tests/unit/test_library_pipeline.py`
- **测试用例** (~60 行):
  - `test_pipeline_text_pdf_success` — 文字 PDF 完整管线
  - `test_pipeline_word_success` — Word 完整管线
  - `test_pipeline_progress_callbacks` — 进度回调触发正确
  - `test_pipeline_failure_marks_error` — 异常时标记 failed
  - `test_pipeline_creates_chroma_metadata` — ChromaDB user_id metadata
  - `test_pipeline_idempotent_reanalyze` — 重复分析幂等
- **预估**: ~130 行

### T5.3 — 后端集成测试

#### T5.3.1 — `tests/integration/test_api_library.py`
- **测试用例** (~100 行):
  - `test_upload_valid_pdf_returns_task_id` — 上传合法 PDF → 201 + task_id
  - `test_upload_no_file_returns_400` — 无文件 → 400
  - `test_upload_invalid_type_returns_400` — 不支持格式 → 400
  - `test_upload_oversize_returns_400` — 超大文件 → 400
  - `test_progress_returns_sse` — SSE 进度端点流式响应
  - `test_progress_invalid_task_returns_404` — 无效 task_id → 404
  - `test_documents_list_pagination` — 文档列表分页正确
  - `test_documents_list_empty` — 新用户空列表
  - `test_delete_document_cascade` — 删除文档级联清理
  - `test_delete_other_user_document_returns_403` — 不能删别人文档
  - `test_coverage_endpoint` — 覆盖度数据结构正确
  - `test_graph_endpoint` — 图谱数据结构正确
  - `test_chat_personal_scope` — chat knowledge_scope=personal 正常
  - `test_chat_system_scope` — chat knowledge_scope=system 正常
  - `test_chat_personal_no_data_returns_hint` — 无资料提示
- **预估**: ~180 行

### T5.4 — 前端手动测试清单
- **文件**: `docs/test-checklist-个人资料库.md`（新建）
- **内容**: 按验收标准逐条列出操作步骤和预期结果（见 Phase 7 冒烟测试清单）
- **预估**: ~60 行

### Phase 5 检查点
```bash
# 运行全部测试
python -m pytest tests/ -v --tb=short

# 覆盖率报告
python -m pytest tests/ --cov=server --cov=AI_operate --cov-report=term --cov-report=html

# 预期结果:
# - 全部测试通过（0 failed, 0 error）
# - 新代码覆盖率 ≥ 90%
# - 关键路径覆盖率 100%

# 前端语法检查
node --check static/js/dashboard-library.js
node --check static/js/dashboard-library-knowledge.js
node --check static/js/dashboard-library-graph.js
```

---

## Phase 6: 代码审查

> **Agent**: reviewer
> **依赖**: Phase 5 全部测试通过
> **原则**: 安全问题 = 阻塞合并，正确性问题 = 阻塞合并

### T6.1 — 安全审查（阻塞级）
审查清单（基于 `.claude/templates/code-review-checklist.md`）:
- [ ] 上传文件类型白名单（MIME + 魔数双重校验）
- [ ] 上传文件大小限制（200MB）
- [ ] 文件存储目录非 Web 可访问
- [ ] 用户只能操作自己的资料（user_id 权限校验）
- [ ] SQL 全部参数化
- [ ] 删除操作级联完整（MySQL + ChromaDB + 物理文件）
- [ ] API 入口参数验证完整（类型/范围/必填）
- [ ] 错误响应不泄露文件路径/内部堆栈
- [ ] SSE 流正确发送 `[DONE]` 结束

### T6.2 — 正确性审查（阻塞级）
- [ ] 文件类型检测覆盖 3 种类型 + 拒绝边缘情况
- [ ] 处理管线 7 步骤顺序正确，任一步骤失败→整体标记 failed
- [ ] 知识点映射阈值 0.6 合理，边界情况处理
- [ ] ChromaDB user_id metadata 正确写入和过滤
- [ ] 级联删除: MySQL(FK CASCADE) + ChromaDB(手动) + 物理文件(手动)
- [ ] SSE 进度推送: 连接断开时后台线程不崩溃
- [ ] chat knowledge_scope 切换逻辑正确
- [ ] 并发: 同一用户上传多个文件不冲突（独立 task_id）

### T6.3 — 性能审查（警告级）
- [ ] `library_tasks` 查询有 `(user_id, status)` 复合索引
- [ ] `knowledge_documents.user_id` 有索引
- [ ] 子知识点向量预计算缓存（避免每次映射重复计算）
- [ ] 文档列表分页（默认 20 条）
- [ ] OCR 处理在独立线程，不阻塞 API 响应
- [ ] 大文件上传使用流式写入

### T6.4 — 风格审查（建议级）
- [ ] Python: PEP 8, 类型提示完整, snake_case
- [ ] JavaScript: ES6+, const/let, camelCase, class 封装
- [ ] CSS: kebab-case, CSS 变量, BEM-lite
- [ ] 无 `console.log` / `print` 残留
- [ ] 无注释掉的废弃代码

### T6.5 — 文档审查（警告级）
- [ ] `docs/api-reference.md` 新增 7 个端点文档
- [ ] `docs/database-schema.md` 更新 `library_tasks` 表说明
- [ ] 复杂算法（知识点映射、级联删除）有注释说明

### T6.6 — 测试审查（阻塞级）
- [ ] 单元测试覆盖全部服务层函数
- [ ] 集成测试覆盖全部 API 端点（正常+异常路径）
- [ ] 边缘场景测试: 空文件/超大文件/不支持格式/损坏文件
- [ ] 外部依赖已 Mock（DeepSeek API, PaddleOCR）
- [ ] 手动测试清单覆盖 8 条验收标准

### Phase 6 输出
审查报告写入 `docs/code-review-report-个人资料库.md`，含:
- 审查结论: 🔴阻塞 / 🟡条件通过 / 🟢通过
- 问题清单（如有）: 严重度、位置、修复建议
- 修复验证记录

---

## Phase 7: 集成验证与交付

> **Agent**: architect（集成验证）+ tester（冒烟测试）
> **依赖**: Phase 6 审查通过，所有阻塞项已修复
> **目标**: 全链路端到端验证，确认可交付

### T7.1 — 端到端集成测试
```bash
# 1. 重置测试环境
python database/init_db.py

# 2. 启动服务器
python server/app.py &
sleep 15  # 等待嵌入模型预热

# 3. 运行全量测试
python -m pytest tests/ -v --tb=long

# 4. 运行 RAG 验证脚本
python scripts/verify_rag.py --quick --offline

# 5. 预期: 全部通过
```

### T7.2 — 手动冒烟测试（11 条验收标准逐条验证）

| AC | 操作步骤 | 预期结果 |
|----|---------|---------|
| AC-S01 | 管理后台 → 上传《计算机网络》第8版扫描 PDF → 等待处理 | 进度条实时更新 → 状态「已就绪」→ AI 对话切「系统知识库」可检索到教材内容 |
| AC-S02 | 管理后台 → 查看系统资料列表 → 删除一篇 → 重传 | 删除成功，重新上传正常处理 |
| AC-01 | 登录 → 我的资料库 → 上传文字 PDF → 等待处理完成 | 进度条实时更新 → 状态变为「已就绪」✅ |
| AC-02 | 上传 .exe 文件 / 空文件 | 即时拒绝 → 红色 Toast 提示原因 |
| AC-03 | 删除一篇文档 → 查看知识清单 + AI 对话搜索 | 相关知识点覆盖降为 0，AI 检索不到该文档内容 |
| AC-A01 | 上传多份资料 → 知识清单「按知识点」Tab | 合并展示覆盖情况，展开行可查看各文档贡献 |
| AC-A02 | 知识清单切换到「按资料」Tab | 每份资料显示独立覆盖的知识点列表 |
| AC-A03 | 切换到知识图谱 Tab | 统一力导向图，节点颜色反映覆盖度（绿/黄/灰），可缩放拖拽 |
| AC-A04 | 点击知识图谱某个节点 | 弹出详情面板：关联文档列表 + 各文档贡献块数 + 内容摘要 |
| AC-A05 | 查看覆盖度总览 | 环形图显示「已覆盖 X/71 (Y%)」 |
| AC-A06 | 点击「推荐补充」按钮 | 未覆盖但重要性高的知识点节点高亮闪烁 |
| AC-B01 | AI 伴学 → 切到「我的资料」→ 提问资料相关内容 | 回答引用用户资料，来源卡片标注「📚」标签 |
| AC-B02 | AI 伴学 → 切到「系统知识库」→ 提问 | 回答引用系统知识库，不含用户资料 |
| AC-B03 | 新用户（无资料）→ AI 伴学切到「我的资料」 | 提示「还没有上传资料，点击前往资料库」 |

### T7.3 — 交付清单
- [ ] 所有代码已提交到 Git（分支 `feature/personal-library`）
- [ ] 数据库迁移执行成功（`init_db.py` 无报错）
- [ ] 后端全部测试通过（unit + integration）
- [ ] 前端 JS 语法检查通过
- [ ] 代码审查报告通过（无 🔴 阻塞项）
- [ ] 8 条验收标准冒烟测试全部通过
- [ ] `docs/api-reference.md` 已更新
- [ ] `docs/changelog.md` 已更新
- [ ] 会话记忆已写入 `memory/` 目录

---

## 排错机制

> 交付后如遇问题，按以下流程有序排查。每个检查点独立可执行。

### 故障诊断决策树

```
用户报告问题
    │
    ▼
┌─────────────────────────────────┐
│ L1: 快速健康检查 (~30秒)         │
│ python scripts/verify_rag.py    │
│ --quick --offline                │
└──────────┬──────────────────────┘
           │
     ┌─────┴─────┐
     │ 通过?      │
     └─────┬─────┘
      ┌────┴────┐
      │ 是      │ 否 → 按 verify_rag 报告逐项修复
      ▼         ▼
┌─────────────────────────────────┐
│ L2: 分层诊断 (~2分钟)            │
└─────────────────────────────────┘
```

### L1: 快速健康检查
```bash
# 一键检查 7 层（依赖/MySQL/ChromaDB/嵌入模型/RAG/API/前端）
python scripts/verify_rag.py --quick --offline
```

### L2: 分层诊断

#### L2.1 — 数据库层
```bash
# 检查表是否存在
mysql -u root -e "USE wzyProjectDb; SHOW TABLES LIKE 'library%';"
# 预期: library_tasks

mysql -u root -e "USE wzyProjectDb; SHOW COLUMNS FROM knowledge_documents LIKE 'user_id';"
# 预期: 1 row

# 检查迁移是否执行
mysql -u root -e "USE wzyProjectDb; SELECT COUNT(*) FROM library_tasks;"
```

#### L2.2 — 后端服务层
```bash
# 验证所有模块可导入
python -c "
from server.file_handler import detect_file_type, validate_file, extract_text
from server.knowledge_mapper import KnowledgeMapper
from server.library_pipeline import LibraryPipeline
from server.library_api import library_bp
print('All modules OK')
"

# 验证 Blueprint 注册
python -c "
from server.app import app
bps = [bp.name for bp in app.blueprints.values()]
assert 'library_bp' in bps, f'library_bp not found: {bps}'
print('Blueprint OK')
"
```

#### L2.3 — API 端点层
```bash
# 使用诊断脚本（如有）或 curl 逐端点测试
# 1. 文档列表
curl -s http://127.0.0.1:3001/api/library/documents?user_id=1 | python -m json.tool

# 2. 覆盖度
curl -s http://127.0.0.1:3001/api/library/knowledge-coverage?user_id=1 | python -m json.tool

# 3. 知识图谱
curl -s http://127.0.0.1:3001/api/library/knowledge-graph?user_id=1 | python -m json.tool

# 4. 上传（需 multipart）
curl -s -X POST http://127.0.0.1:3001/api/library/upload \
  -F "file=@tests/fixtures/sample.pdf" \
  -F "user_id=1" \
  -F "doc_type=textbook" | python -m json.tool
```

#### L2.4 — 前端层
```bash
# 浏览器 Console 检查:
# 1. F12 → Network → 确认 API 请求 200
# 2. F12 → Console → 无 JS 错误
# 3. 检查 DS.Library 对象是否存在: 在 Console 输入 DS.Library
```

#### L2.5 — ChromaDB 层
```bash
# 验证用户资料向量已入库
python -c "
from chromadb import PersistentClient
c = PersistentClient(path='./chroma_data')
col = c.get_collection('knowledge_chunks')
# 查询带 user_id 的向量
r = col.get(where={'user_id': '1'}, limit=5)
print(f'User 1 vectors: {len(r[\"ids\"])}')
"
```

### L3: 常见故障模式与修复

| 症状 | 可能原因 | 诊断命令 | 修复方案 |
|------|---------|---------|---------|
| 上传后立即报错 | 上传目录无写权限 | `ls -la uploads/` | `mkdir -p uploads && chmod 755 uploads` |
| 处理一直显示 pending | 后台线程未启动 | 检查 Flask 日志 | 确认 `threaded=True`；重启服务器 |
| 处理很快失败 | PaddleOCR 模型未安装 | `python -c "from paddleocr import PaddleOCR"` | `pip install paddleocr` |
| 知识清单全显示「未覆盖」 | 知识点映射未执行或阈值过高 | `SELECT COUNT(*) FROM knowledge_chunks WHERE sub_topic_id IS NOT NULL AND doc_id IN (SELECT doc_id FROM knowledge_documents WHERE user_id IS NOT NULL)` | 手动调用 `POST /api/library/analyze/<doc_id>` |
| AI 切「我的资料」无结果 | ChromaDB user_id metadata 未写入 | 见 L2.5 ChromaDB 诊断 | 重新处理文档；检查 `library_pipeline.py` 中向量写入逻辑 |
| 知识图谱不显示 | ECharts 未加载 或 数据格式不匹配 | F12 Console → 检查报错 | 确认 `echarts` CDN 引用 + 数据结构符合 `{nodes, links, categories}` |
| 级联删除后仍能检索 | ChromaDB 删除未执行 | 见 L2.5 ChromaDB 诊断 | 检查 `DELETE /api/library/documents/` 中 ChromaDB delete 逻辑 |
| Flask 启动慢（>30s） | 嵌入模型重新下载 | 检查 `HF_HOME` 环境变量 | 设置 `HF_ENDPOINT=https://hf-mirror.com`；确认模型已缓存 |

### L4: 紧急回滚方案
如果整体功能严重阻塞且短期无法修复：
```bash
# 1. 回滚数据库迁移（如有数据需先备份）
mysql -u root wzyProjectDb -e "DROP TABLE IF EXISTS library_tasks;"
mysql -u root wzyProjectDb -e "ALTER TABLE knowledge_documents DROP COLUMN IF EXISTS user_id;"

# 2. 回滚代码
git checkout main  # 或恢复 feature 分支前的状态

# 3. 重启服务
python server/app.py
```

### 诊断工具清单
| 工具 | 路径 | 用途 |
|------|------|------|
| RAG 验证脚本 | `scripts/verify_rag.py` | 7 层全链路健康检查 |
| API 诊断页面 | `static/test_api.html` | 前端独立测试每个 API 端点 |
| Chrome DevTools | F12 | Network 面板检查请求、Console 面板检查 JS 错误 |
| MySQL 命令行 | `mysql -u root wzyProjectDb` | 直接验证表结构、数据完整性 |
| ChromaDB 诊断 | Python 脚本（L2.5） | 验证向量数据入库和过滤 |

---

## 统计总览

| 指标 | 数值 |
|------|------|
| **总任务数** | 24 个原子任务（T0.1-T7.3） |
| **Phase 数** | 8 个（Phase 0-7） |
| **Agent 参与** | 6 个 Agent 各司其职 |
| **新增文件** | ~14 个（1 迁移 + 4 服务 + 1 路由 + 3 前端 JS + 1 CSS 修改 + 4 测试） |
| **修改文件** | ~8 个（init_db.py, app.py, dashboard.html, dashboard.js, dashboard-chat.js, rag_service.py, admin.html, admin.js） |
| **API 端点** | 8 个新增 + 1 个改造 |
| **预估总代码行数** | ~2,000 行（含测试 ~700 行） |
| **预估开发时间** | 8-12 小时（含测试和审查） |
| **测试用例数** | ~38 个（单元 ~22 + 集成 ~16） |
| **验收标准** | 11 条（AC-S01~S02 + AC-01~03 + AC-A01~A06 + AC-B01~B03） |

---

## 附录 A: 文件清单

### 新增文件
```
database/migrations/003_library.sql              # 数据库迁移
server/file_handler.py                            # 文件处理服务
server/knowledge_mapper.py                        # 知识点映射服务
server/library_pipeline.py                        # 处理管线编排
server/library_api.py                             # API Blueprint (8个端点)
static/js/dashboard-library.js                    # 资料库主模块
static/js/dashboard-library-knowledge.js          # 知识清单+覆盖度(双Tab)
static/js/dashboard-library-graph.js              # 统一知识图谱+下钻
tests/conftest.py                                 # (修改/新建) 测试fixtures
tests/unit/test_file_handler.py                   # 文件处理单元测试
tests/unit/test_knowledge_mapper.py               # 知识点映射单元测试
tests/unit/test_library_pipeline.py               # 管线编排单元测试
tests/integration/test_api_library.py             # API集成测试
docs/tech-spec-个人资料库.md                      # (Phase 0产出) 技术规格
docs/test-checklist-个人资料库.md                 # 手动测试清单
docs/code-review-report-个人资料库.md             # (Phase 6产出) 审查报告
```

### 修改文件
```
database/init_db.py                               # +3行: 添加003迁移
server/app.py                                     # +45行: 注册Blueprint + chat改造 + 上传配置
AI_operate/rag_service.py                         # +30行: search()支持user_id过滤
static/dashboard.html                             # +65行: 侧边栏入口 + section骨架(双Tab+图谱)
static/assets/starpal-style.css                   # +180行: 资料库全部样式
static/js/dashboard.js                            # +30行: section切换 + 懒加载
static/js/dashboard-chat.js                       # +50行: 检索范围切换 + 来源标签
static/admin.html                                 # +40行: 系统知识库板块
static/js/admin.js                                # +60行: 系统知识库上传管理
```

---

## 附录 B: 任务状态追踪

| ID | 任务 | Agent | 预估行数 | 依赖 | 状态 |
|----|------|-------|---------|------|------|
| T0.1 | PRD 最终评审 | requirement-analyst | 0 | - | ⬜ |
| T0.2 | 技术规格设计 | architect | 0 | - | ⬜ |
| T1.1 | 创建迁移 003_library.sql | backend | ~60 | T0 | ⬜ |
| T1.2 | 更新 init_db.py | backend | ~3 | T1.1 | ⬜ |
| T2.1 | file_handler.py | backend | ~120 | T1 | ⬜ |
| T2.2 | knowledge_mapper.py | backend | ~150 | T1 | ⬜ |
| T2.3 | library_pipeline.py | backend | ~180 | T2.1, T2.2 | ⬜ |
| T2.4 | 修改 rag_service.py | backend | ~30 | T1 | ⬜ |
| T3.1 | library_api.py (8端点) | backend | ~180 | T2 | ⬜ |
| T3.2 | 注册 Blueprint | backend | ~15 | T3.1 | ⬜ |
| T3.3 | 改造 /api/chat | backend | ~30 | T2.4 | ⬜ |
| T4.1 | 侧边栏 + CSS | frontend | ~155 | T3.1 | ⬜ |
| T4.2 | dashboard-library.js | frontend | ~180 | T3.1 | ⬜ |
| T4.3 | dashboard-library-knowledge.js | frontend | ~170 | T3.1 | ⬜ |
| T4.4 | dashboard-library-graph.js | frontend | ~180 | T3.1 | ⬜ |
| T4.5 | 修改 dashboard-chat.js | frontend | ~50 | T3.3 | ⬜ |
| T4.6 | 修改 dashboard.html + dashboard.js | frontend | ~90 | T4.1-4.4 | ⬜ |
| T4.7 | 管理后台系统知识库上传 | frontend | ~100 | T3.1 | ⬜ |
| T5.1 | 测试基础设施 | tester | ~120 | T0 | ⬜ |
| T5.2 | 后端单元测试 (3文件) | tester | ~340 | T2, T3 | ⬜ |
| T5.3 | 后端集成测试 | tester | ~180 | T3 | ⬜ |
| T5.4 | 前端手动测试清单 | tester | ~60 | T4 | ⬜ |
| T6 | 代码审查 | reviewer | 0 | T5 | ⬜ |
| T7 | 集成验证与交付 | architect+tester | 0 | T6 | ⬜ |

---

> **文档版本**: 1.1 | **创建日期**: 2026-08-04 | **作者**: Claude
> 
> 🤖 Generated with [Claude Code](https://claude.com/claude-code)
