# Skill: 添加新功能 (add-feature)

> 端到端的功能添加工作流。从需求理解到代码交付的完整链路。

## 触发条件
- 用户说「添加一个功能」「新增」「做一个」等
- 用户描述了具体的功能需求

## 工作流程

### 第一步：需求确认
1. 加载 `.claude/rules/requirement-engineering.md`
2. 按 4 维度框架提问澄清（目标/范围/约束/优先级）
3. 确认需求理解正确后进入设计阶段

### 第二步：影响分析
1. 识别受影响的模块：
   - 需要新的 API 端点？→ `src/server/routes/`
   - 需要新的数据库表/字段？→ `database/migrations/`
   - 需要新的前端页面/组件？→ `frontend/pages/` + `frontend/js/pages/`
   - 需要修改业务逻辑？→ `src/server/services/`
2. 评估技术风险和依赖

### 第三步：按阶段开发
遵循需求工程流程：PRD → 技术设计 → 任务分解 → 逐任务实现

### 第四步：质量验证
执行完整质量门禁清单（见 `.claude/templates/code-review-checklist.md`）

## 开发顺序约定
```
数据库迁移 → DAO 层 → 服务层 → 路由层 → 前端页面 → 前端样式
```

## 注意事项
- 每步跑测试：`python -m pytest tests/ -v`
- 遵循所有 `.claude/rules/` 中的规范
- 完成后更新 `docs/api-reference.md` 和 `changelog.md`
