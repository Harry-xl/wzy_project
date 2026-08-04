@echo off
setlocal
REM 切换到当前脚本所在目录
cd /d %~dp0

echo [+] 激活虚拟环境...
call .venv\Scripts\activate

echo [+] 升级 pip...
pip install --upgrade pip

echo [+] 安装依赖（强制按 requirements.txt 重装）...
pip install -r requirements.txt --upgrade --force-reinstall

echo [+] 当前 Flask/Werkzeug 版本:
python -c "import flask, werkzeug; print('Flask', flask.__version__, 'Werkzeug', werkzeug.__version__)"

echo [+] 初始化数据库（建库/建表/数据/用户实力字段）...
python database\init_db.py

echo [+] 启动后端（Flask，端口 3000）...
start "Flask Server" cmd /k "cd /d %~dp0 && call .venv\Scripts\activate && python server\app.py"

echo [+] 启动前端静态服务器（端口 8888）...
start "Static Server" cmd /k "cd /d %~dp0 && call .venv\Scripts\activate && python -m http.server 8888 -d static"

echo [*] 所有服务已启动，浏览器打开：http://127.0.0.1:8888/login.html
start "" "http://127.0.0.1:8888/login.html"
pause