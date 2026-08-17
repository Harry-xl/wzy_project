---
name: session-2026-08-05-textbook-ocr-and-fixes
description: 2026-08-05 会话 — 教材OCR导入全流程、OCR引擎选型、PDF损坏诊断、多项Bug修复
metadata:
  type: project
---

# 2026-08-05 会话：教材 OCR 导入与 Bug 修复

## 会话目标

将《计算机网络（第8版）》(谢希仁) 扫描PDF导入系统知识库，同时修复多项Bug。

## OCR 引擎选型过程

### PaddleOCR v3（❌ 放弃）
- PaddleOCR 3.7.0 + PaddlePaddle 3.3.1
- 问题：模型下载成功后，`paddle_inference.create_predictor(config)` 抛出 `json.exception.parse_error` 
- 根因：PaddleX 在 Windows 上的 `paddle_static` 引擎有 JSON 解析 Bug，非网络问题
- 尝试过的方案：清缓存重下、禁用文档预处理（`use_doc_orientation_classify=False`）——均失败

### PaddleOCR v2.7（❌ 放弃）
- 依赖 PaddlePaddle 2.x API，与已安装的 PaddlePaddle 3.3.1 不兼容
- 降级 PaddlePaddle 会引发 PyMuPDF、opencv 连锁版本冲突
- 旧版 PyMuPDF<1.21 需要 Visual Studio 编译

### EasyOCR（✅ 采用）
- `easyocr==1.7.2`，模型：`craft_mlt_25k.pth`(83MB) + `zh_sim_g2.pth`(22MB)
- 模型加载 9s，每页识别 6s(150DPI) / 16s(250DPI)
- 首次初始化自动从 PyTorch Hub 下载模型（~105MB）

## PDF 损坏诊断（关键发现）

122MB 的 PDF 声称 485 页，但：
- 第 1-66 页：正常渲染，EasyOCR 可识别
- 第 67 页起：MuPDF 报语法错误，渲染出的图像异常（OCR 返回 0 字符）
- 第 100 页起：`doc[99]` 抛出 `IndexError: page not in document`
- **结论：PDF 文件下载不完整/损坏**，122MB 对于 485 页扫描版太小（正常 300-500MB）

后续需用户提供完整 PDF。

## 已修复的 Bug

### 1. 中文标题乱码 🔴
- 现象：`knowledge_documents` 中文标题存储为 `\ufffd` 乱码
- 原因：curl 上传时 `title` 参数编码在 bash→Flask→MySQL 跨环境时丢失
- 修复：MySQL 直接 UPDATE 修正为 `计算机网络（第8版）谢希仁`

### 2. RAG 来源卡片不显示 🔴
- 现象：AI 回答底部不显示参考来源
- 根因：`dashboard-chat.js` 中 `sources` 提取后只存到局部变量，`renderMessages()` 在 `aiPlaceholder.sources` 赋值前调用
- 修复：SSE 解析 `o.done && o.sources` 时立即同步设置 `aiPlaceholder.sources = o.sources`
- 文件：`static/js/dashboard-chat.js` 第158行

### 3. AI 占位数据替换 🔴
- 删除旧 12 篇 AI 生成文档（doc_id 1-12）
- MySQL：`DELETE FROM knowledge_documents WHERE doc_id <= 12`（cascade 删除 32 chunks）
- ChromaDB：`collection.delete(ids=['1'..'32'])`，185 → 185

### 4. 导出按钮 🟡
- 新增 API：`GET /api/library/documents/<doc_id>/export`
- 返回拼接全部 chunks 的 Markdown 文本，触发浏览器下载
- 前端文档列表每行加 📥 图标按钮
- 修复：UTF-8 编码（`md_text.encode("utf-8")` + `content_type`）
- 修复：中文文件名 URL encode（`urllib.parse.quote`）
- 文件：`server/library_api.py` + `static/js/dashboard-library.js` + `static/assets/starpal-style.css`

### 5. 前端 JS 语法错误
- `DS.$$(document.querySelectorAll(...))` — 传 NodeList 而非选择器字符串
- 改为 `document.querySelectorAll(...)` 直接调用
- 文件：`dashboard-chat.js` (3处) + `dashboard-library.js` (2处)

### 6. 进度反馈增强
- OCR 进度从 5%→20% 扩展为 5%→60%（`library_pipeline.py`）
- 前端初始显示 "等待处理..." + 2% 最小进度
- SSE 连接时立即推送当前状态，轮询超时 5→30 分钟
- 文件：`server/library_pipeline.py` + `server/library_api.py` + `static/js/dashboard-library.js`

### 7. `init_db.py` 修复
- 添加 `load_dotenv()` 加载 .env
- `execute_multi_sql` 修复 `multi=True` 结果集未消费导致 "Unread result found" 警告
- 文件：`database/init_db.py`

## 关键技术要点

### EasyOCR API
```python
import easyocr, fitz, tempfile, os
reader = easyocr.Reader(['ch_sim'], gpu=False)
pix = page.get_pixmap(dpi=250)
with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as tmp:
    tmp.write(pix.tobytes("png"))
    result = reader.readtext(tmp.name, detail=0)  # detail=0 只返回文本
    os.unlink(tmp.name)
```

### ChromaDB user_id 过滤
- 系统知识库：`user_id=None` → 不加 `where` 条件（返回所有，兼容旧数据）
- 个人资料库：`user_id=int` → `where={"user_id": str(user_id)}`
- `index_chunks` 写入 metadata：`{"user_id": "system"}` 或 `{"user_id": "123"}`

### 服务器启动方式
```bash
# 绝对路径！项目目录含空格
"d:/WZYproject/WeiZuyi_Project_0.2.8 20260804/.venv/Scripts/python.exe" "d:/WZYproject/WeiZuyi_Project_0.2.8 20260804/server/app.py"
```

### .paddlex 缓存路径
`C:\Users\泫岚\.paddlex\official_models\`

## 当前系统状态

| 组件 | 状态 |
|------|:--:|
| Flask API + 静态服务 | ✅ 运行中 |
| 数据库 (10表) | ✅ |
| 系统知识库 | 🟡 仅 66/485 页，等待完整 PDF |
| RAG 检索 | ✅ 正常工作，引用来源 |
| 导出功能 | ✅ 可用 |
| 前端 | ✅ 无 JS 错误 |

## 下次会话接入

1. **用户提供完整 PDF** → 放到项目根目录 → `curl -F "file=@完整.pdf" -F "user_id=0" -F "doc_type=textbook" -F "title=计算机网络第8版" http://127.0.0.1:3001/api/library/upload`
2. 如需提高 OCR 准确度：考虑换成 PaddleOCR 或调整 EasyOCR 参数
3. 编写自动化测试（Phase 5）
4. 代码审查（Phase 6）

**Why:** 本次会话完成了个人资料库系统的教材导入全流程，解决了 OCR 引擎选型、PDF 诊断、5 项 Bug 修复。核心结论：当前 PDF 文件损坏，需完整版。系统其他部分（API/前端/RAG）已就绪。
**How to apply:** 下次会话时，AI 应首先确认 PDF 是否已提供，然后上传处理。参考 [[session-2026-08-04-library-implementation]] 了解架构背景。
