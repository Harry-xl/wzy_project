# 测试规范

## 测试框架
- 测试运行器：pytest
- Flask 测试：pytest-flask
- 覆盖率：pytest-cov
- Mock 外部 API：responses 库（DeepSeek API 调用）

## 目录结构
```
tests/
├── conftest.py              # 全局 fixtures
├── unit/                    # 单元测试（无 DB/网络）
│   ├── test_exam_service.py
│   ├── test_profile_service.py
│   └── test_llm_client.py
├── integration/             # 集成测试（真实 DB，Mock LLM）
│   ├── test_api_auth.py
│   ├── test_api_problems.py
│   └── test_api_answers.py
└── fixtures/                # 测试数据
    ├── sample_users.json
    └── sample_problems.json
```

## 命名约定
- 文件：`test_<模块名>.py`
- 函数：`test_<被测行为>_<预期结果>()`
- 类：`Test<被测类名>`（如 `TestExamStrategy`）

```python
# tests/unit/test_exam_service.py
def test_random_mode_returns_exact_count():
    """游客随机模式下，返回题目数量等于请求数量"""
    problems = get_random_problems(count=5)
    assert len(problems) == 5

def test_personalized_mode_uses_weak_knowledge_points():
    """个性化模式：优先推荐熟练度 < 0.6 的知识点"""
    ...

def test_submit_answer_returns_400_without_user_id():
    """提交答案缺少 user_id 时返回 400"""
    ...
```

## Fixtures 设计
```python
# tests/conftest.py
import pytest
from src.server import create_app

@pytest.fixture
def app():
    """创建测试 Flask 应用"""
    app = create_app(config='testing')
    app.config['TESTING'] = True
    return app

@pytest.fixture
def client(app):
    """Flask 测试客户端"""
    return app.test_client()

@pytest.fixture
def db():
    """测试数据库连接（使用独立测试库 wzyProjectDb_test）"""
    # setup: 创建测试数据库/表
    # yield connection
    # teardown: 清理测试数据
```

## Mock 策略
- **必须 Mock 的外部服务**：DeepSeek API（所有 LLM 调用）
- **可选的 Mock**：数据库（单元测试中）
- 使用 `responses` 库或 `unittest.mock` Mock HTTP 请求
- Mock 的响应必须贴近真实 API 返回格式

## 覆盖率目标
| 类别 | 目标 |
|------|------|
| 整体覆盖率 | ≥ 80% |
| 新代码覆盖率 | ≥ 90% |
| 关键业务逻辑 | 100%（选题策略、画像更新、密码哈希） |

运行覆盖率：
```bash
python -m pytest tests/ --cov=. --cov-report=html --cov-report=term
```

## 测试数据
- 使用 fixtures 目录中的 JSON 文件
- 测试数据库与生产数据库完全隔离（使用 `wzyProjectDb_test`）
- 每个测试模块运行前后自动创建/清理测试数据
- 不使用生产数据做测试

## 测试编写时机
| 场景 | 测试要求 |
|------|---------|
| 新功能 | 必须包含测试才能合并 |
| Bug 修复 | 必须先写复现测试，再修复 |
| 重构 | 重构前后测试结果必须一致 |
| 性能优化 | 可选，但建议增加性能基准测试 |

## 断言风格
- 使用 pytest 原生 `assert`（非 unittest.TestCase）
- 检查精确值：`assert result['success'] is True`
- 检查数据类型：`assert isinstance(problems, list)`
- 检查范围：`assert 1 <= len(problems) <= 50`
- 浮动值用近似比较：`assert abs(level - 0.55) < 0.01`
