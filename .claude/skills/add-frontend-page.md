# Skill: 添加前端页面 (add-frontend-page)

> 标准化的前端页面开发流程

## 工作流程

### 第一步：确定页面类型
- **独立页面**：完整的 HTML 文件（如 `login.html`, `admin.html`）
- **Dashboard 子模块**：通过 iframe 或内联渲染集成到仪表盘

### 第二步：创建文件
```
frontend/
├── pages/xxx.html           # HTML 入口
├── js/pages/xxx.js           # 页面专属 JS
└── css/                      # 样式（在现有 CSS 文件中追加）
```

### 第三步：HTML 结构
```html
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>页面标题 - 星伴</title>
    <link rel="stylesheet" href="../css/starpal-style.css">
    <link href="https://cdn.jsdelivr.net/npm/remixicon@3.5.0/fonts/remixicon.css" rel="stylesheet">
</head>
<body>
    <!-- 页面内容 -->
    <script src="../js/core/utils.js"></script>
    <script src="../js/core/storage.js"></script>
    <script src="../js/core/api.js"></script>
    <script src="../js/pages/xxx.js"></script>
</body>
</html>
```

### 第四步：JS 模块
- 遵循 `.claude/rules/javascript-coding.md`
- 使用 ES6 class 封装
- 全局命名空间使用 `window.__DS.xxx`

### 第五步：集成（如需要）
- Dashboard 子模块：在 `dashboard.js` 中添加切换逻辑和 postMessage 通信
- 导航链接：更新 Dashboard 的导航卡片

### 第六步：验证
- 浏览器中打开页面
- 检查不同分辨率下的显示
- 测试所有交互流程
