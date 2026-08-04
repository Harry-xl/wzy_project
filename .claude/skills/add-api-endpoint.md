# Skill: 添加 API 端点 (add-api-endpoint)

> 标准化的 API 端点开发流程

## 工作流程

### 第一步：设计
1. 确定 HTTP 方法和 URL 路径
2. 设计请求参数和响应格式
3. 遵循 `.claude/rules/api-design.md`

### 第二步：实现
按以下顺序开发（逐层向下）：

```
路由层 (routes/)  →  参数验证 + 调用服务层
服务层 (services/) →  业务逻辑
模型层 (models/)   →  数据库访问（如需要）
```

每层完成后写测试。

### 第三步：注册路由
在 `src/server/routes/__init__.py` 中注册新 Blueprint。

### 第四步：文档
更新 `docs/api-reference.md`，包含：
- 请求方式、URL、参数说明
- 请求/响应示例（真实 JSON）
- 错误码说明

### 第五步：验证
```bash
python -m pytest tests/integration/test_api_xxx.py -v
python -m pytest tests/ -v  # 全量回归
```
