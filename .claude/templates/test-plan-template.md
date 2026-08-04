# 测试计划: [功能名称]

> 关联: PRD #[编号] | 技术规格 #[编号]

---

## 1. 测试范围

### 1.1 测试目标
（本次测试要验证什么）

### 1.2 测试范围
- [ ] 单元测试
- [ ] 集成测试
- [ ] 手动测试（UI 验证）

### 1.3 不测试的范围
（哪些不需要测试，为什么）

---

## 2. 测试环境

| 项目 | 配置 |
|------|------|
| Python | 3.11 |
| MySQL | 8.x (测试库: wzyProjectDb_test) |
| 浏览器 | Chrome 90+ |
| Mock 服务 | DeepSeek API |

---

## 3. 测试用例

### 3.1 单元测试用例

| ID | 测试项 | 输入 | 预期输出 | 优先级 |
|----|--------|------|---------|--------|
| UT-01 | xxx | xxx | xxx | P0 |
| UT-02 | xxx | xxx | xxx | P1 |

### 3.2 集成测试用例

| ID | 测试项 | 请求 | 预期响应 | 优先级 |
|----|--------|------|---------|--------|
| IT-01 | xxx | GET /api/xxx | 200 + data | P0 |
| IT-02 | xxx | POST /api/xxx (缺参数) | 400 | P0 |

### 3.3 手动测试用例

| ID | 测试项 | 操作步骤 | 预期结果 | 优先级 |
|----|--------|---------|---------|--------|
| MT-01 | xxx | 1. ... 2. ... | xxx | P1 |

---

## 4. 测试数据

- 测试用户: user@test.com / 123456
- 测试题目: 见 `tests/fixtures/sample_problems.json`

---

## 5. 测试执行

```bash
# 运行所有测试
python -m pytest tests/ -v

# 运行特定模块
python -m pytest tests/unit/test_xxx.py -v
python -m pytest tests/integration/test_api_xxx.py -v

# 带覆盖率
python -m pytest tests/ --cov=. --cov-report=term
```

---

## 6. 缺陷记录

| ID | 描述 | 严重度 | 状态 | 修复人 |
|----|------|--------|------|--------|
| BUG-01 | xxx | 高/中/低 | 待修复/已修复 | |
