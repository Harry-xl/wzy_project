# Git 版本控制规范

## 仓库状态
- 仓库在本地（未关联远程）
- 所有代码在 `main` 分支

## 分支策略
| 分支类型 | 命名格式 | 用途 |
|---------|---------|------|
| 功能分支 | `feature/<简短描述>` | 新功能开发 |
| 修复分支 | `bugfix/<问题描述>` | Bug 修复 |
| 重构分支 | `refactor/<重构目标>` | 代码重构 |
| 紧急修复 | `hotfix/<问题描述>` | 线上紧急修复 |

分支命名使用英文小写 + 连字符：`feature/add-jwt-auth`, `bugfix/fix-login-redirect`

## 提交信息格式
```
<类型>: <简短描述（中文）>

<详细说明（中文或英文，可选）>

Co-Authored-By: Claude <noreply@anthropic.com>
```

类型标签：
- `feat` — 新功能
- `fix` — Bug 修复
- `refactor` — 代码重构
- `docs` — 文档更新
- `test` — 测试相关
- `chore` — 杂项（构建、依赖、配置）

示例：
```
feat: 添加 JWT 令牌认证

- 登录接口返回 access_token + refresh_token
- 添加 @login_required 装饰器保护敏感接口
- 前端自动在请求头携带 Authorization

Co-Authored-By: Claude <noreply@anthropic.com>
```

## 提交粒度
- 一个逻辑变更 = 一个提交
- 不要混合无关变更（如功能开发 + 格式修正放在两个提交）
- 每个提交应可通过测试
- WIP（进行中）提交在推送前 squash

## 日常操作
```bash
# 开始新功能
git checkout -b feature/xxx

# 提交前检查
python -m pytest tests/ -v

# 提交
git add <相关文件>
git commit -m "feat: xxx"

# 完成功能后合并回 main
git checkout main
git merge feature/xxx
git branch -d feature/xxx
```

## .gitignore 核心规则
- `.env` — 含密钥，绝不提交
- `.venv/` — Python 虚拟环境
- `__pycache__/`, `*.pyc` — Python 编译产物
- `.idea/` — JetBrains IDE 配置（含个人路径）
- `extracted_questions_cache.json` — 缓存文件（287KB）
- `import_checkpoint.json` — 导入断点（含机器状态）
- `*.log` — 日志文件

## 禁止事项
- ❌ 禁止提交 `.env` 或含密钥的任何文件
- ❌ 禁止强制推送（`git push --force`）
- ❌ 禁止提交大文件（> 5MB，使用 Git LFS 或外部存储）
- ❌ 禁止在提交信息中写密码或 API Key
