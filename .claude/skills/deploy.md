# Skill: 部署 (deploy)

> 部署 StarPal 到目标环境

## 当前状态
StarPal 目前是本地开发环境（Windows），无容器化或远程部署。

## 部署方式

### 本地开发（当前）
```bash
# Windows 一键启动
scripts\start.bat

# 或手动启动
.venv\Scripts\activate
pip install -r requirements.txt
python database/scripts/init_db.py
start "Flask API" python src/server/app.py
start "Static" python -m http.server 8888 --directory frontend
```

### Docker 部署（计划中）
TODO: `Dockerfile` + `docker-compose.yml`

### 生产部署检查清单
- [ ] `.env` 中配置生产环境密钥和数据库凭据
- [ ] MySQL 数据库已创建并迁移完成
- [ ] DeepSeek API Key 有效且配额充足
- [ ] Flask debug 模式关闭 (`FLASK_DEBUG=false`)
- [ ] 前端静态文件由 Nginx 代理（非 `http.server`）
- [ ] CORS 限制为生产域名
- [ ] 已运行全量测试套件
- [ ] 已备份数据库

## 健康检查
部署后验证：
```bash
# API 健康检查
curl http://127.0.0.1:3001/api/health

# 前端可访问
curl -I http://127.0.0.1:8888/login.html
```
