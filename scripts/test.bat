@echo off
REM =========================================
REM 星伴 (StarPal) — 测试运行脚本
REM =========================================

echo =========================================
echo   星伴 - 运行测试套件
echo =========================================
echo.

REM 激活虚拟环境
call ..\.venv\Scripts\activate.bat

REM 安装测试依赖（如需要）
pip install -r ..\requirements-dev.txt >nul 2>&1

echo [1/2] 运行测试...
python -m pytest ..\tests\ -v

echo.
echo [2/2] 生成覆盖率报告...
python -m pytest ..\tests\ --cov=..\ --cov-report=term --cov-report=html

echo.
echo =========================================
echo   测试完成！覆盖率报告: htmlcov\index.html
echo =========================================
pause
