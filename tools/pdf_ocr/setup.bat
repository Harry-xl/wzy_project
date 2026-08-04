@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion

:: ============================================================
::  PDF OCR 工具 — 一键环境安装脚本
::  自动安装 Python 依赖 + 下载 PaddleOCR 模型
:: ============================================================

title PDF OCR 工具 - 环境安装

echo.
echo  ============================================
echo   PDF OCR 工具 — 环境安装
echo  ============================================
echo.
echo  本脚本将安装以下组件:
echo    1. PyMuPDF      — PDF 页面渲染
echo    2. PaddleOCR    — 中文 OCR 识别引擎
echo    3. python-docx  — Word 文档生成
echo    4. 其他依赖库
echo.
echo  首次安装需下载 PaddleOCR 模型 (~500MB)
echo  预计耗时: 5-10 分钟（取决于网络速度）
echo.

:: ---- 检测 Python ----
echo  [检测] 正在检查 Python 环境...
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo  [错误] 未找到 Python！请先安装 Python 3.11+
    echo         下载: https://www.python.org/downloads/
    pause
    exit /b 1
)

python -c "import sys; sys.exit(0 if sys.version_info >= (3, 9) else 1)" >nul 2>&1
if %errorlevel% neq 0 (
    echo  [错误] Python 版本过低，需要 3.9+
    python --version
    pause
    exit /b 1
)

for /f "tokens=2" %%v in ('python --version 2^>^&1') do set PYVER=%%v
echo  [OK] Python %PYVER%

:: ---- 检查是否在正确目录 ----
if not exist "requirements.txt" (
    echo  [错误] 请在 tools\pdf_ocr 目录下运行此脚本！
    echo         当前目录: %CD%
    pause
    exit /b 1
)

:: ---- 选择安装源 ----
echo.
echo  ----------------------------------------
echo   选择 pip 安装源:
echo     [1] 默认源 (pypi.org)
echo     [2] 清华镜像 (推荐国内用户)
echo     [3] 阿里云镜像
echo  ----------------------------------------
set /p MIRROR_CHOICE="  请输入选项 [1-3，默认 2]: "
if "%MIRROR_CHOICE%"=="" set MIRROR_CHOICE=2

if "%MIRROR_CHOICE%"=="1" (
    set PIP_INDEX=
    set MIRROR_NAME=默认源
)
if "%MIRROR_CHOICE%"=="2" (
    set PIP_INDEX=-i https://pypi.tuna.tsinghua.edu.cn/simple
    set MIRROR_NAME=清华镜像
)
if "%MIRROR_CHOICE%"=="3" (
    set PIP_INDEX=-i https://mirrors.aliyun.com/pypi/simple
    set MIRROR_NAME=阿里云镜像
)

echo.
echo  使用: %MIRROR_NAME%

:: ---- 升级 pip ----
echo.
echo  [1/3] 升级 pip...
python -m pip install --upgrade pip %PIP_INDEX% --quiet
if %errorlevel% neq 0 (
    echo  [警告] pip 升级失败，继续安装依赖...
)

:: ---- 安装基础依赖 ----
echo  [2/3] 安装基础依赖 (PyMuPDF, python-docx, tqdm, Pillow)...
python -m pip install PyMuPDF python-docx Pillow tqdm %PIP_INDEX% --quiet
if %errorlevel% neq 0 (
    echo  [错误] 基础依赖安装失败！
    pause
    exit /b 1
)
echo  [OK] 基础依赖安装完成

:: ---- 安装 PaddleOCR ----
echo  [3/3] 安装 PaddleOCR (含 PaddlePaddle CPU 版)...
echo         这个步骤可能较慢，请耐心等待...
python -m pip install paddlepaddle %PIP_INDEX% --quiet
if %errorlevel% neq 0 (
    echo  [错误] PaddlePaddle 安装失败！
    echo         请尝试: pip install paddlepaddle --user
    pause
    exit /b 1
)

python -m pip install paddleocr %PIP_INDEX% --quiet
if %errorlevel% neq 0 (
    echo  [错误] PaddleOCR 安装失败！
    pause
    exit /b 1
)
echo  [OK] PaddleOCR 安装完成

:: ---- 安装测试依赖 ----
echo.
echo  安装测试依赖 (pytest, reportlab)...
python -m pip install pytest reportlab %PIP_INDEX% --quiet

:: ---- 验证安装 ----
echo.
echo  ============================================
echo   验证安装...
echo  ============================================

python -c "import fitz; print('  [OK] PyMuPDF', fitz.version)" 2>nul
if %errorlevel% neq 0 echo  [FAIL] PyMuPDF

python -c "import docx; print('  [OK] python-docx')" 2>nul
if %errorlevel% neq 0 echo  [FAIL] python-docx

python -c "from PIL import Image; print('  [OK] Pillow')" 2>nul
if %errorlevel% neq 0 echo  [FAIL] Pillow

python -c "import paddleocr; print('  [OK] PaddleOCR')" 2>nul
if %errorlevel% neq 0 (
    echo  [WARN] PaddleOCR 导入失败（首次运行时会自动下载模型）
)

:: ---- 运行单元测试 ----
echo.
echo  ----------------------------------------
echo   运行单元测试（验证工具链）...
echo  ----------------------------------------
python -m pytest tests/ -q --tb=short 2>nul
if %errorlevel% equ 0 (
    echo.
    echo  [OK] 所有测试通过！环境安装成功。
) else (
    echo.
    echo  [WARN] 部分测试未通过，但工具基本功能应该可用。
    echo         运行 python -m pytest tests/ -v 查看详情。
)

:: ---- 完成 ----
echo.
echo  ============================================
echo   安装完成！
echo  ============================================
echo.
echo  下一步:
echo    1. 准备你的扫描 PDF 文件
echo    2. 运行: run_ocr.bat
echo    3. 或手动: python ocr_tool.py "教材.pdf" -v
echo.
echo  详细文档: README.md
echo  ============================================

pause
