@echo off
REM =========================================
REM 星伴 (StarPal) — 首次环境搭建脚本
REM =========================================

echo =========================================
echo   星伴 - 首次环境搭建
echo =========================================
echo.

REM 检查 Python
python --version >nul 2>&1
if errorlevel 1 (
    echo [错误] 未找到 Python，请先安装 Python 3.11+
    pause
    exit /b 1
)
echo [OK] Python 已找到

REM 创建虚拟环境
if not exist "..\.venv\" (
    echo [1/5] 创建 Python 虚拟环境...
    python -m venv ..\.venv
    echo [OK] 虚拟环境已创建
) else (
    echo [1/5] 虚拟环境已存在，跳过
)

REM 激活虚拟环境
call ..\.venv\Scripts\activate.bat

REM 安装依赖
echo [2/5] 安装 Python 依赖...
pip install -r ..\requirements.txt
echo [OK] 依赖安装完成

REM 初始化数据库
echo [3/5] 初始化数据库...
echo   请确保 MySQL 8.x 已启动，并修改了 ..\.env 中的数据库密码
python ..\database\init_db.py
echo [OK] 数据库初始化完成

REM 安装测试依赖
echo [4/5] 安装测试依赖...
pip install -r ..\requirements-dev.txt
echo [OK] 测试依赖安装完成

REM 运行测试
echo [5/5] 运行测试验证环境...
python -m pytest ..\tests\ -v

echo.
echo =========================================
echo   环境搭建完成！
echo   运行 scripts\start.bat 启动项目
echo =========================================
pause
