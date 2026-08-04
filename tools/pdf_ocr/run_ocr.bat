@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion

:: ============================================================
::  PDF OCR 工具 — 交互式 OCR 处理脚本
::  支持拖拽 PDF 文件到脚本窗口，引导式操作
:: ============================================================

title PDF OCR 工具 - OCR 处理

:: ---- 快速模式：拖拽文件到脚本上 ----
if not "%~1"=="" (
    set "PDF_FILE=%~1"
    goto :QUICK_START
)

echo.
echo  ============================================
echo   PDF OCR 工具 — 交互式 OCR 处理
echo  ============================================
echo.
echo  提示：你也可以直接把 PDF 文件拖拽到这个脚本上！
echo.

:: ---- 选择 PDF 文件 ----
:SELECT_FILE
echo  ----------------------------------------
echo   请输入 PDF 文件路径:
echo  ----------------------------------------
set /p PDF_FILE="  PDF路径: "

:: 去掉路径两端的引号
set PDF_FILE=%PDF_FILE:"=%

if "%PDF_FILE%"=="" (
    echo  [错误] 未输入文件路径
    goto :SELECT_FILE
)

if not exist "%PDF_FILE%" (
    echo  [错误] 文件不存在: %PDF_FILE%
    goto :SELECT_FILE
)

:QUICK_START
echo.
echo  输入文件: %PDF_FILE%

:: ---- 检测已有进度 ----
set RESUME_FLAG=
set "OUTPUT_DIR=%~dp1output"
if "%OUTPUT_DIR%"=="output" set "OUTPUT_DIR=output"

if exist "%OUTPUT_DIR%\.ocr_checkpoint.json" (
    echo.
    echo  ============================================
    echo   检测到上次处理进度！
    echo  ============================================
    echo.
    echo  是否从断点继续？
    echo    [1] 从断点继续 (--resume)
    echo    [2] 重新开始 (--no-resume)
    echo  ----------------------------------------
    set /p RESUME_CHOICE="  请输入选项 [1-2，默认 1]: "
    if "!RESUME_CHOICE!"=="" set RESUME_CHOICE=1
    if "!RESUME_CHOICE!"=="1" set RESUME_FLAG=--resume
    if "!RESUME_CHOICE!"=="2" set RESUME_FLAG=--no-resume
)

:: ---- 选择处理模式 ----
echo.
echo  ============================================
echo   选择处理模式:
echo  ============================================
echo.
echo   [1] 快速测试 — 处理前5页，验证识别效果
echo   [2] 全量处理 — 处理整个PDF (默认200 DPI)
echo   [3] 高精度 — 全量处理，300 DPI (较慢但更准)
echo   [4] 自定义 — 手动指定所有参数
echo  ----------------------------------------
set /p MODE_CHOICE="  请输入选项 [1-4，默认 2]: "
if "%MODE_CHOICE%"=="" set MODE_CHOICE=2

set EXTRA_FLAGS=

if "%MODE_CHOICE%"=="1" (
    echo.
    echo  模式: 快速测试 (前5页)
    set MODE_FLAGS=--start-page 1 --end-page 5 -v
    goto :CHOOSE_FORMAT
)

if "%MODE_CHOICE%"=="2" (
    echo.
    echo  模式: 全量处理 (200 DPI)
    set MODE_FLAGS=--dpi 200 -v
    goto :CHOOSE_FORMAT
)

if "%MODE_CHOICE%"=="3" (
    echo.
    echo  模式: 高精度 (300 DPI, 较慢)
    set MODE_FLAGS=--dpi 300 --batch-size 3 -v
    goto :CHOOSE_FORMAT
)

if "%MODE_CHOICE%"=="4" (
    echo.
    echo  ============================================
    echo   自定义参数:
    echo  ============================================

    :: DPI
    set /p CUSTOM_DPI="  DPI [默认 200]: "
    if "!CUSTOM_DPI!"=="" set CUSTOM_DPI=200

    :: 起始页
    set /p CUSTOM_START="  起始页 [默认 1]: "
    if "!CUSTOM_START!"=="" set CUSTOM_START=1

    :: 结束页
    set /p CUSTOM_END="  结束页 [-1=全部]: "
    if "!CUSTOM_END!"=="" set CUSTOM_END=-1

    :: 批大小
    set /p CUSTOM_BATCH="  批大小 [默认 5]: "
    if "!CUSTOM_BATCH!"=="" set CUSTOM_BATCH=5

    :: 分卷
    set /p CUSTOM_SPLIT="  DOCX分卷页数 [0=不拆分]: "
    if "!CUSTOM_SPLIT!"=="" set CUSTOM_SPLIT=0

    set MODE_FLAGS=--dpi !CUSTOM_DPI! --start-page !CUSTOM_START! --end-page !CUSTOM_END! --batch-size !CUSTOM_BATCH! --split !CUSTOM_SPLIT! -v
)

:: ---- 选择输出格式 ----
:CHOOSE_FORMAT
echo.
echo  ----------------------------------------
echo   选择输出格式:
echo     [1] MD + DOCX 都要 (推荐)
echo     [2] 只要 Markdown (给AI/RAG用)
echo     [3] 只要 Word (人工校对)
echo  ----------------------------------------
set /p FORMAT_CHOICE="  请输入选项 [1-3，默认 1]: "
if "%FORMAT_CHOICE%"=="" set FORMAT_CHOICE=1

if "%FORMAT_CHOICE%"=="1" set FORMAT_FLAG=-f both
if "%FORMAT_CHOICE%"=="2" set FORMAT_FLAG=-f md
if "%FORMAT_CHOICE%"=="3" set FORMAT_FLAG=-f docx

:: ---- 输出目录 ----
set /p CUSTOM_OUTDIR="  输出目录 [默认: PDF同级output文件夹]: "
if not "%CUSTOM_OUTDIR%"=="" set EXTRA_FLAGS=%EXTRA_FLAGS% -o "%CUSTOM_OUTDIR%"

:: ---- 执行 OCR ----
echo.
echo  ============================================
echo   开始 OCR 处理...
echo  ============================================
echo.
echo  命令: python ocr_tool.py "%PDF_FILE%" %MODE_FLAGS% %FORMAT_FLAG% %RESUME_FLAG% %EXTRA_FLAGS%
echo.

python ocr_tool.py "%PDF_FILE%" %MODE_FLAGS% %FORMAT_FLAG% %RESUME_FLAG% %EXTRA_FLAGS%

:: ---- 处理结果 ----
if %errorlevel% neq 0 (
    echo.
    echo  ============================================
    echo   处理中断或出错
    echo  ============================================
    echo.
    echo  不用担心！已处理的页面不会丢失。
    echo  重新运行此脚本，选择"[1] 从断点继续"即可。
    echo.
    pause
    exit /b 1
)

echo.
echo  ============================================
echo   OCR 处理完成！
echo  ============================================
echo.
echo  输出文件在 output 目录中。
echo.
echo  下一步:
echo    1. 打开 output/*.md   查看 Markdown 结果
echo    2. 打开 output/*.docx 查看 Word 结果
echo    3. 运行 run_full_pipeline.bat 一键导入 RAG
echo.

pause
