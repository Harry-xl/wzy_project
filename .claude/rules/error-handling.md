# 错误处理规范

## 总体原则
1. **用户看到的错误要友好**：不暴露技术细节，告诉用户发生了什么 + 可以怎么做
2. **开发者看到的错误要详细**：完整的堆栈、上下文、输入数据，方便定位
3. **错误不应阻断核心流程**：非关键步骤失败降级处理，不影响主流程

---

## 后端错误处理

### API 路由层
```python
# 标准模式
@app.route('/api/xxx', methods=['POST'])
def handle_xxx():
    try:
        data = request.json
        # 1. 参数验证
        if not data or 'required_field' not in data:
            return jsonify({
                "success": False,
                "message": "缺少必填字段：required_field"
            }), 400

        # 2. 业务逻辑
        result = some_service.do_something(data)

        # 3. 成功返回
        return jsonify({"success": True, "data": result})

    except ValueError as e:
        # 可预期的业务错误
        return jsonify({"success": False, "message": str(e)}), 400

    except Exception as e:
        # 未预期的系统错误
        logger.error(f"处理 xxx 失败: {e}", exc_info=True)
        return jsonify({
            "success": False,
            "message": "服务暂时不可用，请稍后重试"
        }), 500
```

### 服务层
```python
# 抛出具体异常，由路由层处理
def update_ability_profile(user_id: int, problem_id: int, is_correct: bool) -> None:
    try:
        # ... 业务逻辑
    except mysql.connector.Error as e:
        logger.error(f"更新能力画像失败: user_id={user_id}, error={e}")
        # 非关键步骤，失败不阻塞主流程（答案已保存）
        # 仅记录日志，不向上抛出
```

### 数据库操作
- 连接池耗尽 → 等待或返回 503
- 查询超时 → 重试 1 次，失败返回 500
- 死锁 → 重试 1 次（InnoDB 自动检测并回滚）

### LLM API 调用
```python
import time

def call_deepseek(prompt: str, max_retries: int = 3) -> str:
    for attempt in range(max_retries):
        try:
            response = requests.post(
                API_URL, headers=headers, json=payload,
                timeout=30
            )
            response.raise_for_status()
            return response.json()["choices"][0]["message"]["content"]
        except requests.Timeout:
            if attempt < max_retries - 1:
                time.sleep(2 ** attempt)  # 指数退避
                continue
            raise Exception("AI 服务响应超时，请稍后重试")
        except requests.HTTPError as e:
            if e.response.status_code == 429:  # Rate limit
                retry_after = int(e.response.headers.get("Retry-After", 5))
                time.sleep(retry_after)
                continue
            raise
```

---

## 前端错误处理

### API 调用
```javascript
async submitAnswer(data) {
    try {
        const result = await ApiClient.submitAnswer(data);
        if (result.success) {
            this.showResult(result.is_correct);
        } else {
            Utils.showToast(result.message || '操作失败', 'error');
        }
    } catch (err) {
        console.error('提交答案失败:', err);
        Utils.showToast('网络错误，请检查连接后重试', 'error');
    }
}
```

### SSE 流式连接
```javascript
async fetchStream(url, data, onChunk, onDone) {
    const controller = new AbortController();
    try {
        const response = await fetch(url, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(data),
            signal: controller.signal
        });

        const reader = response.body.getReader();
        const decoder = new TextDecoder();

        while (true) {
            const { done, value } = await reader.read();
            if (done) { onDone?.(); break; }
            onChunk(decoder.decode(value, { stream: true }));
        }
    } catch (err) {
        if (err.name === 'AbortError') return; // 用户主动中止
        console.error('流式读取失败:', err);
        Utils.showToast('AI 响应中断，请重试', 'error');
    }
    return controller; // 返回以便外部调用 controller.abort()
}
```

### 全局错误捕获
```javascript
// 未捕获的 Promise 错误
window.addEventListener('unhandledrejection', event => {
    console.error('未处理的 Promise 错误:', event.reason);
    // 不显示给用户，但记录以便调试
});
```

---

## 错误日志级别
| 级别 | 场景 |
|------|------|
| DEBUG | 开发调试信息、SQL 语句、请求参数 |
| INFO | 正常业务流程（登录、答题提交、画像更新） |
| WARNING | 可恢复的异常（LLM 调用重试、连接池接近耗尽） |
| ERROR | 需要关注的错误（API 调用失败、数据库查询异常） |
| CRITICAL | 系统级故障（数据库连接断开、磁盘满） |

---

## 降级策略
当非核心功能失败时，采用降级而非整体失败：

| 场景 | 降级策略 |
|------|---------|
| 画像更新失败 | 答案已保存，画像下次答题时补偿更新 |
| AI 分析超时 | 返回「暂无法生成分析报告」，基础画像数据仍可展示 |
| AI 讲解失败 | 显示正确答案和知识点，不显示 AI 讲解 |
| 会话聚合失败 | 下次提交时补偿聚合 |
| 清理任务异常 | 跳过本次清理，下个周期重试 |
