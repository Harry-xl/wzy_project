# 个人资料库 OCR 问题排查报告

> 日期: 2026-08-04 | 目标文件: 《计算机网络（第8版）》(谢希仁) 扫描PDF, 122MB, 485页

---

## 一、问题总览

| # | 类别 | 问题 | 严重度 | 状态 |
|---|------|------|:---:|:---:|
| 1 | 依赖 | PaddleOCR 2.7.0.3 + PaddlePaddle 3.3.1 **版本不兼容** | 🔴 阻塞 | ❌ |
| 2 | 依赖 | PaddleOCR v3 模型下载后 JSON 解析崩溃 | 🔴 阻塞 | ❌ |
| 3 | 依赖 | 缺失 4 个包: imgaug, visualdl, premailer, pdf2docx | 🟡 次要 | ❌ |
| 4 | 依赖 | opencv 版本冲突 (需要 4.6, 当前 4.10) | 🟡 次要 | ❌ |
| 5 | 依赖 | PyMuPDF 版本冲突 (需要 <1.21, 当前 1.28) | 🟡 次要 | ❌ |
| 6 | 前端 | `DS.$$(document.querySelectorAll(...))` 传参错误 | 🟡 次要 | ✅ |
| 7 | 前端 | 系统上传进度显示无反馈 | 🟡 次要 | ✅ |
| 8 | 后端 | 服务器重启后未加载更新代码 | 🟡 次要 | ✅ |
| 9 | 后端 | SSE 轮询超时太短 (5分钟 → 30分钟) | 🟢 优化 | ✅ |
| 10 | PDF | 确认为纯扫描版 (0 字符文本层，485页) | — 事实 | — |

---

## 二、核心问题深度分析

### 问题1: PaddleOCR 2.7.0.3 ↔ PaddlePaddle 3.3.1 版本不兼容

**现状**:
```
paddleocr     2.7.0.3  ← 2023年发布，依赖 PaddlePaddle 2.x API
paddlepaddle  3.3.1    ← 2025年最新版，API 已完全改变
```

**表现**: PaddleOCR 2.7 内部引用 `ppocr.*` 模块使用了旧版 PaddlePaddle 的 `fluid` API，而 PaddlePaddle 3.x 已移除此 API。即使用 `--no-deps` 强制安装成功，运行时也会因 API 不匹配而崩溃。

**正确组合**:
```
paddleocr 2.7.0.3 需要 → paddlepaddle >=2.4.0, <3.0
paddleocr 3.x      需要 → paddlepaddle >=3.0.0
```

### 问题2: PaddleOCR v3 模型下载成功但初始化崩溃

**现状**: `PaddleOCR(lang='ch')` 能够成功下载 `PP-LCNet_x1_0_doc_ori` 模型（6个文件, 6.87MB），但初始化时 `paddle_inference.create_predictor(config)` 抛出 `json.exception.parse_error`。

**根因**: PaddleOCR v3 依赖 PaddleX pipeline，但 PaddleX 在创建检测模型（`PP-OCRv5_server_det`）和识别模型（`PP-OCRv5_server_rec`）时，由于网络原因无法下载这些模型，导致配置文件为空，引发 JSON 解析错误。`PP-LCNet_x1_0_doc_ori` 只是文档方向分类模型，真正的主体模型（检测+识别）需要额外下载 ~500MB。

---

## 三、解决方案对比

| 方案 | OCR引擎 | 优势 | 劣势 | 安装量 | 推荐 |
|------|---------|------|------|:---:|:---:|
| **A** | PaddleOCR 3.x + 离线模型 | 中文精度最高 | 需手动下载模型包 (500MB+)、模型路径配置复杂 | ~1.5GB | ⭐⭐ |
| **B** | PaddleOCR 2.7 + PaddlePaddle 2.6 | 模型内置 | PyMuPDF 降级需编译 VS | ~2GB | ⭐ |
| **C** | **EasyOCR** | 一行安装，自动下载模型，离线工作 | 中文精度略低于 PaddleOCR | ~300MB | ⭐⭐⭐ |
| **D** | Tesseract + pytesseract | 最轻量 | 中文识别率最低，需安装系统包 | ~50MB | ⭐ |

### 推荐: 方案 C — EasyOCR

**理由**:
1. `pip install easyocr` 一行安装，无依赖冲突
2. 首次运行自动下载中文模型 (~200MB, 从 PyTorch Hub/GitHub)
3. 模型下载后完全离线可用
4. PyTorch 生态，与现有项目无冲突
5. API 简单: `reader.readtext(img_array)`

**对代码的影响**: 只需修改 `server/file_handler.py` 中的 `_extract_via_ocr()` 函数，从 PaddleOCR 切换到 EasyOCR。改动约 20 行。

**安装命令**:
```powershell
cd "d:\WZYproject\WeiZuyi_Project_0.2.8 20260804"
.\.venv\Scripts\python.exe -m pip install easyocr
```

**首次运行测试**:
```powershell
.\.venv\Scripts\python.exe -c "import easyocr; r = easyocr.Reader(['ch_sim']); print('EasyOCR OK')"
```

---

## 四、非 OCR 问题已修复清单

| 问题 | 文件 | 修复内容 |
|------|------|---------|
| `$$(document.querySelectorAll)` | `dashboard-chat.js`, `dashboard-library.js` | 改为 `document.querySelectorAll` |
| 系统上传进度无反馈 | `dashboard-library.js` (SysLibrary) | 添加 console.log、初始状态显示、2% 最小进度 |
| SSE 超时太短 | `server/library_api.py` | 5→30分钟，初始立即推送状态 |
| OCR 进度不更新 | `server/file_handler.py`, `library_pipeline.py` | 每5页回调写入 DB |
| server 代码未生效 | — | 需手动重启 Flask |
| `init_db.py` 不加载 .env | `database/init_db.py` | 添加 dotenv 加载 + multi=True 修复 |

---

## 五、建议执行顺序

1. **先解决 OCR**: 用 EasyOCR 替换 PaddleOCR（方案 C）→ 上传教材 → 验证全流程
2. **然后完善**: 编写自动化测试 → 代码审查 → 文档更新
3. **后续优化**: 如果 EasyOCR 识别率不够，再考虑 PaddleOCR 离线模型方案

---

> 生成时间: 2026-08-04 | 作者: Claude
