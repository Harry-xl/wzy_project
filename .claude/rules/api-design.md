# REST API 设计规范

## URL 设计
- 资源名使用名词复数：`/api/problems`（非 `/api/getProblems`）
- 动作用 HTTP 方法表达：GET（查）/ POST（增）/ PUT（改）/ DELETE（删）
- 特殊操作用动词后缀：`/api/problems/filter`、`/api/explain/stream`
- 资源 ID 作为路径参数：`/api/user_profile/<user_id>`
- 全部小写，单词用下划线分隔

## 响应格式

### 成功响应
```json
{
    "success": true,
    "data": { ... },           // 或直接展开
    "message": "操作成功"       // 可选
}
```

### 列表响应（含分页信息）
```json
{
    "success": true,
    "items": [ ... ],
    "total": 868,
    "page": 1,
    "page_size": 50,
    "total_pages": 18
}
```

### 错误响应
```json
{
    "success": false,
    "message": "用户可读的错误描述",
    "error": "TECHNICAL_CODE"   // 可选，仅内部使用
}
```

## HTTP 状态码
| 状态码 | 场景 |
|--------|------|
| 200 | 请求成功 |
| 201 | 资源创建成功 |
| 204 | 操作成功，无返回内容（如 DELETE） |
| 400 | 请求参数错误 |
| 401 | 未认证 |
| 404 | 资源不存在 |
| 409 | 资源冲突（重复注册） |
| 500 | 服务器内部错误 |

## 参数规范

### Query 参数（GET 请求）
- 分页：`?page=1&page_size=50`
- 筛选：`?difficulty=中等&knowledge_point=TCP协议`
- 排序：`?sort_by=time&order=desc`
- 搜索：`?keyword=握手`

### Body 参数（POST/PUT 请求）
- Content-Type: `application/json`
- 字段名：snake_case 与数据库字段一致
- 必填字段在路由层验证，返回 400

### 参数验证规则
```python
# 路由入口处必须验证
if not request.json or 'email' not in request.json:
    return jsonify({"success": False, "message": "缺少必填参数"}), 400

if len(name) < 1 or len(name) > 255:
    return jsonify({"success": False, "message": "昵称长度为1-255字符"}), 400
```

## 分页标准
- 参数：`page`（默认 1）、`page_size`（默认 50，最大 200）
- 返回：`total`（总数）、`total_pages`（总页数）、当前页数据
- 超出范围：返回空数组而非 404

## SSE 流式接口
- Content-Type: `text/event-stream`
- Cache-Control: `no-cache`
- Connection: `keep-alive`
- 每条消息格式：`data: <内容>\n\n`
- 结束信号：`data: [DONE]\n\n`
- 前端通过 `fetch` + `ReadableStream` 读取
- 支持 `AbortController` 中止

## CORS
- 开发环境：全局 `Access-Control-Allow-Origin: *`
- 生产环境：限制为具体域名
- 预检请求（OPTIONS）返回 204

## API 版本管理
- 当前无版本号前缀（`/api/...`）
- 如需 breaking change：`/api/v2/...`
- 新版上线后旧版保留至少 1 个月过渡期

## 文档同步
- 任何 API 变更必须同步更新 `docs/api-reference.md`
- 请求/响应示例必须为真实 JSON（可复制的）
