# JavaScript 编码规范

## 语言标准
- ES6+ 语法，不使用过时特性
- 禁用 `var`，使用 `const`（不变值）和 `let`（可变值）
- 每个 JS 文件顶部添加 `'use strict';`
- 使用模板字面量 `` `hello ${name}` `` 替代字符串拼接

## 命名约定
- 类名：PascalCase（如 `ExamModule`, `ChatSession`）
- 函数/方法：camelCase（如 `loadProblems`, `submitAnswer`）
- 变量：camelCase（如 `currentProblem`, `selectedAnswers`）
- 常量：UPPER_SNAKE_CASE（如 `MAX_PROBLEMS`, `CACHE_TTL`）
- DOM ID/class：kebab-case 用于 HTML，camelCase 用于 JS 引用
- 全局命名空间：`window.__DS` 用于仪表盘共享状态

## 模块组织
- 核心工具 → `js/core/`（api.js, storage.js, utils.js）
- 页面逻辑 → `js/pages/`（auth.js, exam.js, dashboard.js ...）
- 加载顺序：utils.js → storage.js → api.js → renderer.js → 页面脚本

## 类设计
```javascript
'use strict';

class ExamPage {
    // 私有属性用 _ 前缀约定
    _problems = [];
    _currentIndex = 0;

    constructor(options = {}) {
        this.userId = options.userId || 0;
        this.count = Math.min(options.count || 5, 50);
    }

    async loadProblems() {
        try {
            const response = await ApiClient.getProblems({
                user_id: this.userId,
                count: this.count
            });
            this._problems = response.problems;
            this.render();
        } catch (error) {
            console.error('加载题目失败:', error);
            Utils.showToast('加载失败，请重试', 'error');
        }
    }

    render() { /* ... */ }
}
```

## DOM 操作
- 缓存 DOM 查询结果
- 事件处理：优先使用事件委托
- 批量 DOM 更新：使用 DocumentFragment 或先 off-screen 再挂载

```javascript
// ✅ 缓存选择器
const $ = (sel) => document.querySelector(sel);
const $$ = (sel) => document.querySelectorAll(sel);

// ✅ 事件委托
container.addEventListener('click', (e) => {
    const btn = e.target.closest('.answer-btn');
    if (btn) this.handleAnswer(btn.dataset.value);
});
```

## 错误处理
- 所有 API 调用包裹 try/catch
- 用户可见的错误通过 `Utils.showToast()` 显示
- 技术错误通过 `console.error` 记录
- SSE 流式连接失败时提供重试按钮

```javascript
// ✅ 正确
async submit() {
    try {
        const result = await ApiClient.submitAnswer(data);
        if (result.success) {
            this.showResult(result.is_correct);
        }
    } catch (err) {
        console.error('提交失败:', err);
        Utils.showToast('提交失败，请重试', 'error');
    }
}
```

## iframe 通信
- Dashboard 通过 `postMessage` 向 iframe 发送指令
- 消息类型：`loadProblemsByFilter`, `setProblems`, `loadChat`
- iframe 内页面通过 `window.addEventListener('message', ...)` 接收
- 始终验证 `event.origin`

## 缓存策略
| 数据 | TTL | 存储 |
|------|-----|------|
| 能力画像 | 16 分钟 | 内存 + localStorage |
| 知识点列表 | 30 分钟 | 内存 |
| 用户信息 | 永久 | localStorage |
| 聊天记录 | 永久 | localStorage（按用户+对话ID分组） |

## 禁止事项
- ❌ 禁止使用 `innerHTML`（使用 `textContent` 或 DOM API，renderer.js 中的 Markdown 渲染除外）
- ❌ 禁止同步 XHR 请求
- ❌ 禁止在循环中进行 DOM 操作（先构建再一次性插入）
- ❌ 禁止全局变量污染（使用类封装或 IIFE）
