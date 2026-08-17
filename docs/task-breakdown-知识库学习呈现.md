# 任务分解: 知识库学习呈现 + 学练打通 (Phase 2.5)

> 关联: [PRD-知识库学习呈现.md](PRD-知识库学习呈现.md) v0.2 | [tech-spec-知识库学习呈现.md](tech-spec-知识库学习呈现.md) v0.1
> 版本: 1.0 | 创建日期: 2026-08-07

---

## Agent 分工总览

| Agent | 角色 | Phase | 使用 Skill | 核心职责 |
|-------|------|:--:|------|---------|
| **architect** | 系统架构师 | 0 | — | 技术规格最终评审、关键决策确认 |
| **backend-developer** | 后端开发者 | 1-3 | `add-database-migration` `add-api-endpoint` | 迁移→服务→API 全部后端代码 |
| **frontend-developer** | 前端开发者 | 4 | `add-frontend-page` | 学习卡片组件 + 图谱改造 + 学练打通 UI |
| **tester** | 测试工程师 | 5 | `write-tests` | 单元测试 + 集成测试 + 手动测试清单 |
| **reviewer** | 代码审查员 | 6 | `code-review` | 6 维度全面审查 |
| **architect + tester** | 联合 | 7 | — | 集成验证 + 冒烟测试 |

---

## 依赖关系图

```
Phase 0 (架构评审)
  │
  └─→ Phase 1 (数据库迁移)
        │
        └─→ Phase 2 (服务层)
              │
              └─→ Phase 3 (API 层)
                    │
                    ├─→ Phase 4 (前端) ──→ Phase 5 (测试) ──→ Phase 6 (审查) ──→ Phase 7 (交付)
                    │
                    └─→ (Phase 5 测试计划可在 Phase 3 完成后提前启动)
```

**并行说明**: Phase 4 (前端) 与 Phase 5 (测试用例编写) 可在 Phase 3 API 签名冻结后并行执行。

---

## Phase 0: 架构评审

> **Agent**: architect | **Skill**: — | **依赖**: 无
> **退出条件**: 技术规格评审通过

### T0.1 — 技术规格最终评审
- **产出**: 评审记录（确认/修正/补充列表）
- **检查点**:
  - [ ] 知识体系统一策略（软对齐）是否足够？是否需要更强的约束？
  - [ ] 学习卡片缓存策略是否覆盖所有边缘场景？
  - [ ] 学练打通 postMessage 协议是否与现有通信机制兼容？
  - [ ] AI Prompt 设计是否包含所有必要上下文？
  - [ ] 预估工作量是否合理？
- **预估**: 不产出代码，纯设计评审

---

## Phase 1: 数据库迁移

> **Agent**: backend-developer | **Skill**: `add-database-migration` | **依赖**: Phase 0
> **关键约束**: 迁移必须幂等，可重复执行不报错

### T1.1 — 迁移 004: 知识体系统一
- **文件**: `database/migrations/004_unify_knowledge_points.sql` (NEW, ~100 行)
- **内容**:
  1. `problems` 表新增 `sub_topic_id INT`（可选，含索引）
  2. `ability_profile` 表新增 `parent_kp_ref VARCHAR(200)`（可选）
  3. 清空旧 C 语言测试数据（TRUNCATE user_answers, ability_profile, problems）
  4. 插入 ~25 道计算机网络测试题（knowledge_point 使用 parent_kp 有效值，覆盖主要知识点）
  5. 插入配套 ability_profile 种子数据
  6. 使用 `IF NOT EXISTS` / 动态列检测保证幂等
- **验证**: `DESC problems` 确认 sub_topic_id 列存在；`SELECT DISTINCT knowledge_point FROM problems` 确认值都在 parent_kp 范围内

### T1.2 — 迁移 005: 学习卡片表
- **文件**: `database/migrations/005_learning_cards.sql` (NEW, ~30 行)
- **内容**: 创建 `knowledge_learning_cards` 表（含所有字段、唯一约束、外键、索引）
- **验证**: `DESC knowledge_learning_cards`

### T1.3 — knowledge_documents 扩展
- **文件**: `database/migrations/005_learning_cards.sql` (追加, ~10 行)
- **内容**: `knowledge_documents` 新增 `readable_content MEDIUMTEXT` 和 `readable_generated_at TIMESTAMP` 列
- **验证**: `SHOW COLUMNS FROM knowledge_documents LIKE 'readable_content'`

### T1.4 — 更新 init_db.py
- **文件**: `database/init_db.py` (MODIFY, ~5 行)
- **内容**: 添加 `004_unify_knowledge_points.sql` 和 `005_learning_cards.sql` 到迁移执行列表
- **验证**: `python database/init_db.py` 无报错

---

## Phase 2: 后端服务层

> **Agent**: backend-developer | **Skill**: — | **依赖**: Phase 1
> **原则**: 每个服务文件 < 250 行，独立可测

### T2.1 — learning_card_service.py (核心)
- **文件**: `server/learning_card_service.py` (NEW, ~220 行)
- **类**: `LearningCardService`
- **核心函数**:

| 函数 | 职责 | 预估行数 |
|------|------|:--:|
| `get_or_generate_slim()` | 缓存检查/未命中→AI同步生成→写入缓存 | ~50 |
| `generate_full_stream()` | 缓存检查/未命中→SSE流式生成→写入缓存 | ~60 |
| `mark_for_regeneration()` | 标记单张卡片为待重新生成 | ~10 |
| `invalidate_cards_for_document()` | 文档更新后批量失效关联卡片 | ~25 |
| `get_batch_status()` | 获取所有卡片生成状态（管理用） | ~15 |
| `_build_slim_prompt()` | 构造精简版 AI Prompt | ~20 |
| `_build_full_prompt()` | 构造完整版 AI Prompt | ~25 |
| `_parse_slim_response()` | 解析 AI 返回的 JSON | ~15 |

- **关键依赖**: `AI_operate/deepseek_chat.py`（复用现有同步+流式调用）、`database/db_connector.py`
- **AI 调用方式**:
  - 同步: 复用 `deepseek_chat.py` 的同步调用函数
  - 流式: 复用 `deepseek_chat.py` 的 SSE 流式调用函数
- **错误处理**: AI 调用失败 → 抛出明确异常 → API 层捕获 → 降级返回原始 chunks

### T2.2 — 修改 knowledge_mapper.py (卡片失效联动)
- **文件**: `server/knowledge_mapper.py` (MODIFY, ~15 行)
- **变更**: 在 `analyze_document()` 完成后追加调用 `LearningCardService.invalidate_cards_for_document(doc_id)`
- **导入**: `from server.learning_card_service import LearningCardService`

### T2.3 — 修改 library_pipeline.py (卡片失效联动)
- **文件**: `server/library_pipeline.py` (MODIFY, ~5 行)
- **变更**: 在 `process_upload()` 的知识点映射步骤后追加失效调用

### T2.4 — 修改 rag_service.py (user_id 过滤，如未完成)
- **文件**: `AI_operate/rag_service.py` (MODIFY, ~30 行，可能在之前会话已完成)
- **内容**: `search()` 方法确认支持 `user_id` 参数过滤（个人资料库检索）

---

## Phase 3: 后端 API 层

> **Agent**: backend-developer | **Skill**: `add-api-endpoint` | **依赖**: Phase 2
> **原则**: 参数验证在路由入口完成，响应格式统一 `{success, data?, message?}`

### T3.1 — 学习卡片端点 (4 个)
- **文件**: `server/library_api.py` (MODIFY, ~130 行追加)

#### 端点 1: `GET /api/library/learning-card/<sub_topic_id>`
- 参数: `user_id` (query, 默认 0)
- 逻辑: 调用 `LearningCardService.get_or_generate_slim()` → 返回 JSON
- 错误: 400(缺少参数), 404(子知识点不存在), 500(AI生成失败→降级)

#### 端点 2: `GET /api/library/learning-card/<sub_topic_id>/expand`
- 参数: `user_id` (query)
- 逻辑: 调用 `LearningCardService.generate_full_stream()` → SSE 流式返回
- 响应类型: `text/event-stream`

#### 端点 3: `POST /api/library/learning-card/<sub_topic_id>/regenerate`
- Body: `{"user_id": 0}`
- 逻辑: 调用 `LearningCardService.mark_for_regeneration()` → 返回确认信息

#### 端点 4: `GET /api/library/learning-cards/status`
- 参数: `user_id` (query)
- 逻辑: 调用 `LearningCardService.get_batch_status()` → 返回所有卡片状态列表
- 用途: 管理后台监控卡片生成进度

### T3.2 — 知识点列表端点
- **文件**: `server/library_api.py` (MODIFY, ~25 行追加)

#### 端点 5: `GET /api/knowledge/parent-kps`
- 逻辑: `SELECT parent_kp, COUNT(*) FROM knowledge_sub_topics GROUP BY parent_kp` → 返回 25 个标准知识点列表
- 用途: 前端学练打通时根据 knowledge_point 查找对应的 sub_topic_id

### T3.3 — 文档阅读端点
- **文件**: `server/library_api.py` (MODIFY, ~40 行追加)

#### 端点 6: `GET /api/library/documents/<doc_id>/readable`
- 参数: `user_id` (query)
- 逻辑: 检查 `readable_content` 缓存 → 未命中则 AI 整理 → 返回 Markdown
- 降级: AI 调用失败 → 返回原始 chunks 拼接文本

---

## Phase 4: 前端页面

> **Agent**: frontend-developer | **Skill**: `add-frontend-page` | **依赖**: Phase 3 (API 签名冻结)
> **原则**: 每个 JS 类 < 200 行，ES6 class 封装，全局命名空间 `DS.*`

### T4.1 — 学习卡片 Modal (核心组件)
- **文件**: `static/dashboard.html` (MODIFY, ~40 行)
- **内容**: 学习卡片 Modal HTML 骨架（overlay + panel + header/body/footer 三段结构）

- **文件**: `static/js/dashboard-library.js` (MODIFY, ~180 行追加)
- **新增**: `DS.Library.LearningCardModal` 对象
- **功能**:
  - `open(subTopicId, userId, options)` — 主入口：显示 Modal → fetch 卡片 → 渲染
  - `_renderSlim(data)` — 渲染精简版（定义 + 要点列表 + 来源文档）
  - `_expandFull()` — SSE 连接 → 逐字追加渲染 Markdown → 完成后显示
  - `_renderFallback(chunks)` — AI 失败降级：显示原始文本 + 错误提示
  - `_showSourceChunks()` — 展开溯源面板：引用 chunk 原文
  - `_practiceRelated()` — 学练打通：发送 postMessage 到 exam iframe
  - `close()` — 清理 SSE 连接 + 隐藏 Modal
  - 外部点击 overlay 关闭、ESC 键关闭

- **文件**: `static/assets/starpal-style.css` (MODIFY, ~120 行追加)
- **样式**:
  - `.learning-card-modal` — 全屏 overlay 半透明背景
  - `.learning-card-panel` — 居中面板，max-width 700px，圆角阴影
  - `.learning-card-header` / `.learning-card-body` / `.learning-card-footer`
  - `.learning-card-slim` — 精简版排版（定义块、要点列表、来源标签）
  - `.learning-card-full` — 完整版 Markdown 渲染区域
  - `.learning-card-fallback` — 降级灰色文本块
  - `.learning-card-source-chunks` — 溯源展开面板
  - 骨架屏加载动画（生成中占位）
  - 响应式：移动端面板全宽

### T4.2 — 改造知识图谱节点点击
- **文件**: `static/js/dashboard-library-graph.js` (MODIFY, ~40 行)
- **变更**:
  - `onNodeClick(node)` 重写：调用 `DS.Library.LearningCardModal.open(subTopicId, userId, {from: 'graph'})`
  - 移除旧的下钻面板渲染逻辑（已被学习卡片取代）
  - 保留节点数据中的 `sub_topic_id` 映射

### T4.3 — 改造知识清单行点击
- **文件**: `static/js/dashboard-library-knowledge.js` (MODIFY, ~30 行)
- **变更**:
  - 「按知识点」Tab 中每行增加 `data-sub-topic-id` 属性
  - 行点击事件调用 `DS.Library.LearningCardModal.open()`
  - 展开行（旧的下钻显示关联文档）改为直接打开学习卡片

### T4.4 — 学练打通: 做题页 → 学习资料
- **文件**: `static/exam.html` (MODIFY, ~15 行)
- **内容**: 题目区域增加知识点链接行
  ```html
  <div class="exam-knowledge-link">
    📚 知识点：<a href="#" id="examViewLearning">TCP连接管理</a>
  </div>
  ```
- **文件**: `static/js/exam.js` (MODIFY, ~25 行)
- **内容**:
  - 渲染题目时动态设置知识点链接文本和 data 属性
  - 点击链接 → `window.parent.postMessage({type: 'openLearningCardByKp', knowledgePoint: '...'}, '*')`

### T4.5 — 学练打通: Dashboard 接收消息 → 卡片
- **文件**: `static/js/dashboard.js` (MODIFY, ~30 行)
- **变更**: 在现有 `window.addEventListener('message', ...)` 中新增消息处理
  ```javascript
  if (data.type === 'openLearningCardByKp') {
    // 根据 knowledge_point (parent_kp) 查找 sub_topic_id → 打开卡片
    DS.Library.openLearningCardByKp(data.knowledgePoint);
  }
  ```
- **新增函数**: `DS.Library.openLearningCardByKp(knowledgePoint)` — 调用 `/api/knowledge/parent-kps` 获取映射 → 取第一个 sub_topic_id → 打开卡片（父知识点下展示第一个子知识点的卡片）

### T4.6 — 学练打通: 学习卡片 → 选题
- **文件**: `static/js/dashboard-library.js` (在 T4.1 中实现，~20 行)
- **内容**: 学习卡片底部 `[📝 练习相关题目]` 按钮
  ```javascript
  _practiceRelated() {
    const examFrame = document.getElementById('iframe-exam');
    if (examFrame) {
      examFrame.contentWindow.postMessage({
        type: 'loadProblemsByKnowledgePoint',
        knowledgePoint: this._currentParentKp
      }, '*');
    }
    // 切换到做题 section
    document.querySelector('[data-section="exam"]')?.click();
    this.close();
  }
  ```
- **文件**: `static/js/exam.js` (MODIFY, ~20 行)
- **内容**: 接收 `loadProblemsByKnowledgePoint` 消息 → 调用 API 按知识点筛选题目 → 渲染

### T4.7 — 学练打通: 能力画像 → 学习/练题
- **文件**: `static/js/dashboard.js` (MODIFY, ~40 行)
- **内容**: 在能力画像渲染函数中，对熟练度 < 0.6 的知识点，追加操作按钮：
  - `[📖 学习]` → 调用 `DS.Library.openLearningCardByKp(kp)`
  - `[📝 练习]` → 发送 postMessage 到 exam iframe → 切换 section

### T4.8 — 学练打通: 知识图谱节点 → 练题
- **文件**: `static/js/dashboard-library-graph.js` (MODIFY, ~15 行)
- **内容**: 学习卡片打开时（从图谱节点触发），卡片底部自动显示 `[🎯 练习此知识点]` 按钮

### T4.9 — CSS 样式补充
- **文件**: `static/assets/starpal-style.css` (MODIFY, ~80 行追加)
- **内容**:
  - 学练打通按钮样式 (`.kp-action-btn`, `.exam-knowledge-link`)
  - 按钮 hover/active 状态
  - 画像薄弱项高亮样式
  - 知识点链接标签样式

---

## Phase 5: 测试

> **Agent**: tester | **Skill**: `write-tests` | **依赖**: Phase 3 + Phase 4
> **原则**: 新代码覆盖率 ≥ 90%，Mock 所有外部 API

### T5.1 — 测试基础设施
- **文件**: `tests/conftest.py` (MODIFY, ~40 行)
- **新增 fixture**:
  - `mock_deepseek_slim` — Mock DeepSeek 返回固定精简版 JSON
  - `mock_deepseek_full` — Mock DeepSeek 流式返回固定 Markdown
  - `sample_card_data` — 测试用卡片数据
  - `test_sub_topic` — 确保 `wzyProjectDb_test` 中有子知识点数据

### T5.2 — 服务层单元测试
- **文件**: `tests/unit/test_learning_card_service.py` (NEW, ~130 行)

| 测试用例 | 说明 |
|---------|------|
| `test_get_slim_cache_hit` | 缓存命中直接返回，不调用 AI |
| `test_get_slim_cache_miss_generates` | 缓存未命中 → 调用 AI → 写入缓存 |
| `test_get_slim_ai_failure_fallback` | AI 调用失败 → 返回降级数据 |
| `test_get_slim_regenerating_flag` | 标记重新生成 → 即使缓存存在也重新生成 |
| `test_full_stream_cache_hit` | 完整版缓存命中 → 单 chunk 返回 |
| `test_full_stream_generates` | 完整版生成 → SSE 格式输出 |
| `test_invalidate_cards_for_document` | 文档更新 → 关联卡片全部标记失效 |
| `test_mark_for_regeneration` | 单卡片标记逻辑 |
| `test_build_slim_prompt_format` | Prompt 模板包含必要信息 |
| `test_build_full_prompt_format` | Complete Prompt 包含精简版内容 |

### T5.3 — API 集成测试
- **文件**: `tests/integration/test_api_learning_cards.py` (NEW, ~150 行)

| 测试用例 | 说明 |
|---------|------|
| `test_get_card_valid_sub_topic` | 有效子知识点 → 200 + slim_content |
| `test_get_card_invalid_sub_topic` | 无效 ID → 404 |
| `test_get_card_missing_user_id` | 缺少 user_id → 使用默认值 |
| `test_expand_returns_sse` | SSE 流式响应格式正确 |
| `test_regenerate_marks_flag` | 重新生成 → is_regenerating=1 |
| `test_card_user_isolation` | 用户 A 不能访问用户 B 的卡片 |
| `test_parent_kps_list` | `/api/knowledge/parent-kps` 返回 25 个知识点 |
| `test_readable_content_cache` | 文档阅读版本缓存命中/未命中 |

### T5.4 — 前端手动测试清单
- **文件**: `docs/test-checklist-学习呈现.md` (NEW, ~60 行)
- **内容**: 按 11 条验收标准逐条列出操作步骤和预期结果

---

## Phase 6: 代码审查

> **Agent**: reviewer | **Skill**: `code-review` | **依赖**: Phase 5 全部通过

### T6.1 — 6 维度审查

| 维度 | 级别 | 重点检查项 |
|------|:--:|------|
| **安全** | 🔴 阻塞 | API Key 来源、SQL 参数化、AI 内容 XSS、权限校验 |
| **正确性** | 🔴 阻塞 | 卡片生成→缓存→失效全链路、学练跳转逻辑、降级路径 |
| **测试** | 🔴 阻塞 | Mock 正确性、覆盖率 ≥ 90%、边缘场景覆盖 |
| **性能** | 🟡 警告 | 卡片生成不阻塞 API 响应、SSE 连接正确释放、MySQL 索引 |
| **文档** | 🟡 警告 | 新端点文档化、服务层注释、前端 JSDoc |
| **风格** | 🟢 建议 | PEP 8、ES6+、CSS 变量、命名一致性 |

### T6.2 — 审查输出
- 审查报告写入 `docs/code-review-report-学习呈现.md`
- 包含: 结论 (阻塞/条件通过/通过) + 问题清单 + 修复验证

---

## Phase 7: 集成验证与交付

> **Agent**: architect (集成) + tester (冒烟) | **依赖**: Phase 6 通过

### T7.1 — 端到端集成测试
```bash
# 1. 重置环境
python database/init_db.py

# 2. 启动服务
python server/app.py &
sleep 15

# 3. 全量测试
python -m pytest tests/ -v --tb=long

# 4. 验证知识体系统一
mysql -u root wzyProjectDb -e "SELECT DISTINCT knowledge_point FROM problems"
# 预期: 全部在 parent_kp 范围内
```

### T7.2 — 手动冒烟测试 (11 条验收标准)

| AC | 操作 | 预期 |
|----|------|------|
| AC-Z01 | 检查 problems 表 | knowledge_point 值在 parent_kp 范围内 |
| AC-Z02 | 选题按 parent_kp 筛选 | 返回正确题目 |
| AC-Z03 | 查看能力画像 | 显示标准知识点名称 |
| AC-C01 | 知识图谱点击未生成过卡片的节点 | < 15s 显示精简版（定义+要点+来源） |
| AC-C02 | 再次点击同一节点 | 秒开缓存版本 |
| AC-C03 | 点击「展开详细」 | SSE 流式输出完整讲解 |
| AC-C04 | 点击「查看原始资料片段」 | 展开显示 chunks |
| AC-C05 | 断开 DeepSeek API | 降级显示原始文本+提示 |
| AC-C06 | 上传新资料覆盖某知识点 | 卡片标记再生→下次点击更新 |
| AC-C07 | 知识清单 Tab 点击知识点行 | 弹出学习卡片 |
| AC-D01 | 做题页点击「查看学习资料」 | 打开对应卡片 |
| AC-D02 | 学习卡片点击「练习相关题目」 | 切换到做题+筛选知识点 |
| AC-D03 | 画像薄弱项点击「学习」 | 打开卡片 |
| AC-D04 | 图谱节点面板点击「练习」 | 跳转针对性刷题 |

---

## 统计总览

| 指标 | 数值 |
|------|:--:|
| **总任务数** | 23 个 (T0.1 ~ T7.2) |
| **Phase 数** | 8 个 (Phase 0-7) |
| **Agent 参与** | 5 个 (architect, backend, frontend, tester, reviewer) |
| **使用 Skill** | 4 个 (add-database-migration, add-api-endpoint, add-frontend-page, write-tests, code-review) |
| **新增文件** | 5 个 (2 迁移 + 1 服务 + 2 测试) |
| **修改文件** | 12 个 |
| **API 端点** | 6 个新增 |
| **预估总代码行数** | ~1,200 行 (后端 ~550 + 前端 ~400 + 测试 ~250) |
| **预估开发时间** | 6-10 小时 (含测试和审查) |
| **测试用例数** | 18 个 (单元 10 + 集成 8) |
| **验收标准** | 15 条 (AC-Z01~Z03 + AC-C01~C07 + AC-D01~D04) |

---

## 附录 A: 文件清单

### 新增文件
```
database/migrations/004_unify_knowledge_points.sql    # 知识体系统一 + 测试数据替换
database/migrations/005_learning_cards.sql             # 学习卡片表 + 文档阅读缓存列
server/learning_card_service.py                         # 卡片生成+缓存+失效管理服务
tests/unit/test_learning_card_service.py                # 服务层单元测试
tests/integration/test_api_learning_cards.py            # API 集成测试
```

### 修改文件
```
database/init_db.py                          # +5行: 添加 004/005 迁移
server/knowledge_mapper.py                   # +15行: 映射后卡片失效联动
server/library_pipeline.py                   # +5行: 处理后卡片失效联动
server/library_api.py                        # +200行: 6个新端点
AI_operate/rag_service.py                    # +30行: user_id过滤 (如未完成)
static/dashboard.html                        # +55行: 学习卡片Modal骨架 + 画像操作按钮
static/assets/starpal-style.css              # +200行: 学习卡片 + 打通按钮全部样式
static/js/dashboard-library.js               # +180行: LearningCardModal 类
static/js/dashboard-library-graph.js         # +55行: 节点点击→学习卡片
static/js/dashboard-library-knowledge.js     # +30行: 行点击→学习卡片
static/js/dashboard.js                       # +70行: postMessage处理 + 画像按钮
static/exam.html                             # +15行: 知识点链接行
static/js/exam.js                            # +45行: 查看学习资料 + 接收筛选消息
tests/conftest.py                            # +40行: 测试fixtures
```

---

## 附录 B: 任务状态追踪

| ID | 任务 | Agent | 预估行数 | 依赖 | Skill | 状态 |
|----|------|-------|:--:|------|------|:--:|
| T0.1 | 技术规格评审 | architect | 0 | - | — | ⬜ |
| T1.1 | 迁移004: 知识体系统一 | backend | ~100 | T0 | add-database-migration | ⬜ |
| T1.2 | 迁移005: 学习卡片表 | backend | ~30 | T0 | add-database-migration | ⬜ |
| T1.3 | knowledge_documents 扩展 | backend | ~10 | T0 | add-database-migration | ⬜ |
| T1.4 | 更新 init_db.py | backend | ~5 | T1.1-1.3 | — | ⬜ |
| T2.1 | learning_card_service.py | backend | ~220 | T1 | — | ⬜ |
| T2.2 | 修改 knowledge_mapper.py | backend | ~15 | T2.1 | — | ⬜ |
| T2.3 | 修改 library_pipeline.py | backend | ~5 | T2.1 | — | ⬜ |
| T2.4 | 确认 rag_service.py user_id | backend | ~30 | T1 | — | ⬜ |
| T3.1 | 学习卡片 4 端点 | backend | ~130 | T2 | add-api-endpoint | ⬜ |
| T3.2 | parent-kps 端点 | backend | ~25 | T2 | add-api-endpoint | ⬜ |
| T3.3 | 文档阅读端点 | backend | ~40 | T2 | add-api-endpoint | ⬜ |
| T4.1 | 学习卡片 Modal | frontend | ~340 | T3 | add-frontend-page | ⬜ |
| T4.2 | 图谱节点改造 | frontend | ~40 | T3 | — | ⬜ |
| T4.3 | 知识清单改造 | frontend | ~30 | T3 | — | ⬜ |
| T4.4 | 做题页→学习资料 | frontend | ~40 | T3 | — | ⬜ |
| T4.5 | Dashboard 消息处理 | frontend | ~30 | T4.4 | — | ⬜ |
| T4.6 | 卡片→选题跳转 | frontend | ~45 | T4.1 | — | ⬜ |
| T4.7 | 画像→学习/练题 | frontend | ~40 | T4.1 | — | ⬜ |
| T4.8 | 图谱→练题 | frontend | ~15 | T4.2 | — | ⬜ |
| T5.1 | 测试基础设施 | tester | ~40 | T0 | write-tests | ⬜ |
| T5.2 | 服务层单元测试 | tester | ~130 | T2 | write-tests | ⬜ |
| T5.3 | API 集成测试 | tester | ~150 | T3 | write-tests | ⬜ |
| T5.4 | 手动测试清单 | tester | ~60 | T4 | — | ⬜ |
| T6.1 | 代码审查 | reviewer | 0 | T5 | code-review | ⬜ |
| T7.1 | 集成验证 | architect+tester | 0 | T6 | — | ⬜ |
| T7.2 | 冒烟测试 | architect+tester | 0 | T7.1 | — | ⬜ |

---

> **文档版本**: 1.0 | **创建日期**: 2026-08-07 | **作者**: Claude
>
> 🤖 Generated with [Claude Code](https://claude.com/claude-code)