# CSS 与 UI 设计规范

## 方法论
- 采用 BEM-lite 命名：`block__element--modifier`
- 所有颜色和尺寸统一使用 CSS 自定义属性（CSS Variables）
- 间距采用 4px 基元体系
- 中文界面字体栈优先

## 色板系统
```css
:root {
    /* 品牌色 */
    --color-primary: #4F46E5;
    --color-primary-light: #818CF8;
    --color-primary-dark: #3730A3;

    /* 功能色 */
    --color-success: #10B981;
    --color-warning: #F59E0B;
    --color-error: #EF4444;
    --color-info: #3B82F6;

    /* 中性色 */
    --color-bg: #F8FAFC;
    --color-bg-card: #FFFFFF;
    --color-text: #1E293B;
    --color-text-secondary: #64748B;
    --color-border: #E2E8F0;

    /* 难度等级色 */
    --difficulty-easy: #22C55E;
    --difficulty-medium: #F59E0B;
    --difficulty-hard: #EF4444;

    /* 实力等级色 */
    --strength-beginner: #EF4444;
    --strength-intermediate: #F59E0B;
    --strength-advanced: #22C55E;
    --strength-expert: #10B981;
}
```

## 间距体系（4px base）
| Token | 值 | 用途 |
|-------|-----|------|
| `--space-xs` | 4px | 紧密间距 |
| `--space-sm` | 8px | 相关元素间距 |
| `--space-md` | 16px | 标准卡片内边距 |
| `--space-lg` | 24px | 区块间距 |
| `--space-xl` | 32px | 大区块分隔 |
| `--space-2xl` | 48px | 页面级分隔 |
| `--space-3xl` | 64px | 页面上下留白 |

## 圆角
- `--radius-sm: 4px` — 小按钮/标签
- `--radius-md: 8px` — 标准卡片
- `--radius-lg: 12px` — 大卡片/模态框
- `--radius-full: 9999px` — 圆形元素/药丸按钮

## 阴影
- `--shadow-sm` — 卡片悬停微抬
- `--shadow-md` — 下拉菜单/弹出层
- `--shadow-lg` — 模态框

## 字体
```css
--font-sans: "Microsoft YaHei", "PingFang SC", -apple-system, BlinkMacSystemFont, sans-serif;
--font-mono: "Cascadia Code", "Fira Code", "JetBrains Mono", Consolas, monospace;
```

## 响应式
- 暂以桌面端为主（>= 1024px）
- 使用相对单位（rem/%, em）替代固定 px
- 新增组件考虑移动端折叠方案
- 使用 `max-width` + `margin: auto` 实现内容居中

## 动画
- 过渡动画使用 CSS transition，避免 JS 动画
- 默认 duration: 200ms, easing: ease-in-out
- 对 `prefers-reduced-motion` 做适配
- 关键帧动画仅用于加载指示器、骨架屏等

## 命名公约
- class 名：kebab-case
- 页面级组件以页面名开头：`.login-card`, `.exam-question`
- 状态类：`.is-active`, `.is-disabled`, `.is-loading`, `.has-error`
- 工具类：`.hidden`, `.text-center`, `.mt-md`

## 注意事项
- 不在 `<style>` 标签中写行内样式
- 避免 `!important`（除非覆盖第三方库）
- 新增颜色必须加入 `:root` 变量
- 禁止使用 `float` 布局（使用 Flexbox/Grid）
