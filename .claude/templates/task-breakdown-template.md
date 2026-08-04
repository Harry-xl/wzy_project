# 任务分解: [功能名称]

> 关联: PRD #[编号] | 技术规格 #[编号]

---

## 任务列表

原则：每个任务 < 200 行新代码、独立可测、有明确完成标准。

---

### Phase 1: 数据库

| ID | 任务 | 文件 | 预估行数 | 依赖 | 状态 |
|----|------|------|---------|------|------|
| DB-01 | 创建迁移文件 | `database/migrations/NNN_xxx.sql` | ~20 | - | ⬜ |
| DB-02 | 更新 init_db.py | `database/scripts/init_db.py` | ~5 | DB-01 | ⬜ |

### Phase 2: 数据访问层 (DAO)

| ID | 任务 | 文件 | 预估行数 | 依赖 | 状态 |
|----|------|------|---------|------|------|
| DAO-01 | 实现 xxx_dao | `src/server/models/xxx_dao.py` | ~80 | DB-01 | ⬜ |
| DAO-02 | xxx_dao 单元测试 | `tests/unit/test_xxx_dao.py` | ~60 | DAO-01 | ⬜ |

### Phase 3: 业务逻辑层 (Service)

| ID | 任务 | 文件 | 预估行数 | 依赖 | 状态 |
|----|------|------|---------|------|------|
| SVC-01 | 实现 xxx_service | `src/server/services/xxx_service.py` | ~100 | DAO-01 | ⬜ |
| SVC-02 | xxx_service 单元测试 | `tests/unit/test_xxx_service.py` | ~80 | SVC-01 | ⬜ |

### Phase 4: API 路由层

| ID | 任务 | 文件 | 预估行数 | 依赖 | 状态 |
|----|------|------|---------|------|------|
| API-01 | 实现 /api/xxx 端点 | `src/server/routes/xxx.py` | ~60 | SVC-01 | ⬜ |
| API-02 | 注册 Blueprint | `src/server/routes/__init__.py` | ~3 | API-01 | ⬜ |
| API-03 | 集成测试 | `tests/integration/test_api_xxx.py` | ~100 | API-01 | ⬜ |

### Phase 5: 前端

| ID | 任务 | 文件 | 预估行数 | 依赖 | 状态 |
|----|------|------|---------|------|------|
| FE-01 | 创建 HTML 页面 | `frontend/pages/xxx.html` | ~40 | - | ⬜ |
| FE-02 | 实现 JS 模块 | `frontend/js/pages/xxx.js` | ~150 | API-01 | ⬜ |
| FE-03 | 添加 CSS 样式 | `frontend/css/star pal-style.css` | ~60 | FE-01 | ⬜ |

### Phase 6: 文档与收尾

| ID | 任务 | 文件 | 预估行数 | 依赖 | 状态 |
|----|------|------|---------|------|------|
| DOC-01 | 更新 API 文档 | `docs/api-reference.md` | ~30 | API-01 | ⬜ |
| DOC-02 | 更新 changelog | `docs/changelog.md` | ~10 | ALL | ⬜ |
| QA-01 | 代码审查 | - | - | ALL | ⬜ |
| QA-02 | 手动冒烟测试 | - | - | ALL | ⬜ |

---

## 统计

- 总任务数: __
- 预估总代码行数: __
- 预估开发时间: __ 小时

---

## 状态图例
- ⬜ 待开始
- 🔄 进行中
- ✅ 已完成
- ❌ 已取消
- ⚠️ 受阻
