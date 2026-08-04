@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion

:: ============================================================
::  PDF OCR → RAG 知识库 — 全流程一键脚本
::
::  输入: 扫描版 PDF 教材
::  输出: ChromaDB + MySQL RAG 知识库（可直接用于 AI 对话）
::
::  流程:
::    Step 1: OCR 识别 → Markdown 文件
::    Step 2: Markdown 分块 → 向量嵌入
::    Step 3: 入库 MySQL + ChromaDB
:: ============================================================

title StarPal — PDF → RAG 全流程

echo.
echo  ============================================
echo   StarPal 知识库 — 全流程导入工具
echo  ============================================
echo.
echo  本脚本将完成:
echo    扫描PDF → OCR识别 → 文本分块 → 向量嵌入 → RAG入库
echo.
echo  预计总耗时: 15-40 分钟（取决于PDF大小和DPI）
echo.

:: ---- 检查环境 ----
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo  [错误] 未找到 Python！
    pause
    exit /b 1
)

:: ---- 获取 PDF 文件 ----
if not "%~1"=="" (
    set "PDF_FILE=%~1"
    goto :SKIP_FILE_INPUT
)

echo  ----------------------------------------
echo   请输入 PDF 文件路径:
echo   也可以直接把 PDF 文件拖拽到这个脚本上！
echo  ----------------------------------------
set /p PDF_FILE="  PDF路径: "
set PDF_FILE=%PDF_FILE:"=%

if "%PDF_FILE%"=="" (
    echo  [错误] 未输入文件路径
    pause
    exit /b 1
)

:SKIP_FILE_INPUT
if not exist "%PDF_FILE%" (
    echo  [错误] 文件不存在: %PDF_FILE%
    pause
    exit /b 1
)

:: ---- 配置参数 ----
echo.
echo  ----------------------------------------
echo   选择处理质量:
echo     [1] 标准质量 — 200 DPI (推荐, ~15分钟/400页)
echo     [2] 高质量   — 300 DPI (较慢, ~25分钟/400页)
echo     [3] 快速     — 150 DPI (最快, ~8分钟/400页)
echo  ----------------------------------------
set /p QUALITY_CHOICE="  请输入选项 [1-3，默认 1]: "
if "%QUALITY_CHOICE%"=="" set QUALITY_CHOICE=1

if "%QUALITY_CHOICE%"=="1" (
    set DPI=200
    set BATCH=5
)
if "%QUALITY_CHOICE%"=="2" (
    set DPI=300
    set BATCH=3
)
if "%QUALITY_CHOICE%"=="3" (
    set DPI=150
    set BATCH=8
)

:: ---- 文档信息 ----
echo.
echo  ----------------------------------------
echo   文档信息（用于知识库检索）:
echo  ----------------------------------------

:: 从 PDF 文件名推断标题
for %%F in ("%PDF_FILE%") do set DEFAULT_TITLE=%%~nF
set /p DOC_TITLE="  文档标题 [默认: %DEFAULT_TITLE%]: "
if "%DOC_TITLE%"=="" set DOC_TITLE=%DEFAULT_TITLE%

set /p DOC_SOURCE="  来源描述 [如: 谢希仁《计算机网络》第8版]: "

set DOC_TYPE=textbook
echo.
echo   文档类型:
echo     [1] textbook      — 教材
echo     [2] rfc           — RFC 标准
echo     [3] paper         — 论文
echo     [4] lab           — 实验指导
echo     [5] other         — 其他
set /p TYPE_CHOICE="  请选择 [1-5，默认 1]: "
if "%TYPE_CHOICE%"=="" set TYPE_CHOICE=1
if "%TYPE_CHOICE%"=="1" set DOC_TYPE=textbook
if "%TYPE_CHOICE%"=="2" set DOC_TYPE=rfc
if "%TYPE_CHOICE%"=="3" set DOC_TYPE=paper
if "%TYPE_CHOICE%"=="4" set DOC_TYPE=lab
if "%TYPE_CHOICE%"=="5" set DOC_TYPE=other

:: ---- 输出路径 ----
for %%F in ("%PDF_FILE%") do set PDF_DIR=%%~dpF
set OUTPUT_DIR=%PDF_DIR%output

echo.
echo  ============================================
echo   配置确认:
echo  ============================================
echo    PDF文件:   %PDF_FILE%
echo    输出目录:  %OUTPUT_DIR%
echo    识别质量:  %DPI% DPI
echo    文档标题:  %DOC_TITLE%
echo    文档类型:  %DOC_TYPE%
echo    来源:      %DOC_SOURCE%
echo  ============================================

if "%DOC_SOURCE%"=="" (
    echo.
    echo  [提示] 建议填写来源描述，方便在知识库中追溯。
)

echo.
set /p CONFIRM="  确认执行？[Y/n]: "
if /i "%CONFIRM%"=="n" (
    echo  已取消。
    pause
    exit /b 0
)

:: ================================================================
::  Step 1: OCR 识别
:: ================================================================
echo.
echo  ============================================
echo   Step 1/3: OCR 识别
echo  ============================================
echo.

set OCR_CMD=python ocr_tool.py "%PDF_FILE%" --dpi %DPI% --batch-size %BATCH% -f md -v -o "%OUTPUT_DIR%"

:: 检查是否有上次进度
if exist "%OUTPUT_DIR%\.ocr_checkpoint.json" (
    echo  检测到上次进度，将从断点继续...
    set OCR_CMD=!OCR_CMD! --resume
)

echo  执行: !OCR_CMD!
echo.
!OCR_CMD!

if %errorlevel% neq 0 (
    echo.
    echo  [错误] OCR 识别中断！
    echo  进度已保存，重新运行此脚本可继续。
    pause
    exit /b 1
)

:: ---- 找到生成的 MD 文件 ----
set MD_FILE=
for %%F in ("%OUTPUT_DIR%\*.md") do set MD_FILE=%%F

if "%MD_FILE%"=="" (
    echo  [错误] 未找到生成的 Markdown 文件！
    echo  请检查: %OUTPUT_DIR%
    pause
    exit /b 1
)

echo.
echo  [OK] OCR 完成，输出文件: %MD_FILE%

:: ================================================================
::  Step 2: 预览分块
:: ================================================================
echo.
echo  ============================================
echo   Step 2/3: 预览文本分块
echo  ============================================
echo.

set INGEST_CMD=python ingest_to_rag.py "%MD_FILE%" --title "%DOC_TITLE%" --doc-type %DOC_TYPE% --source "%DOC_SOURCE%" --dry-run

echo  执行: !INGEST_CMD!
echo.
!INGEST_CMD!

echo.
echo  ----------------------------------------
set /p DO_INGEST="  分块预览如上。确认入库？[Y/n]: "
if /i "%DO_INGEST%"=="n" (
    echo.
    echo  已跳过入库。Markdown 文件已生成在:
    echo    %MD_FILE%
    echo.
    echo  后续可手动入库:
    echo    python ingest_to_rag.py "%MD_FILE%" --title "%DOC_TITLE%" --doc-type %DOC_TYPE% --source "%DOC_SOURCE%"
    pause
    exit /b 0
)

:: ================================================================
::  Step 3: RAG 入库
:: ================================================================
echo.
echo  ============================================
echo   Step 3/3: 向量嵌入 + RAG 入库
echo  ============================================
echo.

set INGEST_CMD=python ingest_to_rag.py "%MD_FILE%" --title "%DOC_TITLE%" --doc-type %DOC_TYPE% --source "%DOC_SOURCE%"

echo  执行: !INGEST_CMD!
echo.
!INGEST_CMD!

if %errorlevel% neq 0 (
    echo.
    echo  [警告] RAG 入库可能未完全成功。
    echo  请检查数据库和 EmbeddingService 配置。
    pause
    exit /b 1
)

:: ================================================================
::  Done
:: ================================================================
echo.
echo  ============================================
echo   全流程完成！
echo  ============================================
echo.
echo   已完成的步骤:
echo     [OK] PDF OCR 识别 → %MD_FILE%
echo     [OK] 文本智能分块
echo     [OK] 向量嵌入 + RAG 入库
echo.
echo   验证方式:
echo     1. API 测试:
echo        curl "http://127.0.0.1:3001/api/knowledge/search?q=TCP三次握手^&top_k=3"
echo.
echo     2. 浏览器测试:
echo        打开 http://127.0.0.1:8888/dashboard.html
echo        在 AI 对话中问一个教材相关的问题
echo        看到 "📚 来源引用" 说明 RAG 成功！
echo.
echo  ============================================

pause
