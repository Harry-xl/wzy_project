# PDF OCR 工具 — 使用与集成指南

## 概述

将**扫描版中文 PDF 教材**（400+ 页）转换为 **Markdown**（AI 可读）+ **Word**（人工校对），并支持将产出结果灌入 StarPal RAG 知识库。

```
┌─────────────────┐      ┌────────────────┐      ┌──────────────┐
│ 扫描版 PDF 教材  │ ──►  │ PDF OCR 工具    │ ──►  │ Markdown 文件 │
│ (400+ 页，中文)  │      │ (PaddleOCR)    │      │ + DOCX 文件   │
└─────────────────┘      └────────────────┘      └──────┬───────┘
                                                        │
                                          ┌─────────────┘
                                          ▼
                                   ┌──────────────┐
                                   │ 文本分块      │
                                   │ chunk_document│
                                   └──────┬───────┘
                                          │
                                          ▼
                                   ┌──────────────┐
                                   │ 向量化 + 入库 │
                                   │ index_chunks  │
                                   └──────┬───────┘
                                          │
                                          ▼
                                   ┌──────────────┐
                                   │ ChromaDB     │
                                   │ + MySQL       │
                                   │ 知识库        │
                                   └──────────────┘
```

---

## ⚡ 一键脚本速查

| 脚本 | 用途 | 运行方式 |
|------|------|---------|
| `setup.bat` | 一键安装所有依赖 | 双击运行 |
| `run_ocr.bat` | 交互式 OCR 处理（支持拖拽 PDF） | 双击或拖拽 PDF 到脚本上 |
| `run_full_pipeline.bat` | 全流程：OCR → RAG 入库 | 双击或拖拽 PDF 到脚本上 |

> **新手推荐**：先双击 `setup.bat` 安装环境 → 把 PDF 拖到 `run_ocr.bat` 上测试 5 页 → 满意后拖到 `run_full_pipeline.bat` 一键入库。

---

## 目录

1. [环境准备](#1-环境准备)
2. [快速上手（5 分钟）](#2-快速上手5-分钟)
3. [全量处理 400+ 页 PDF](#3-全量处理-400-页-pdf)
4. [命令行参考](#4-命令行参考)
5. [输出文件说明](#5-输出文件说明)
6. [集成 RAG 知识库](#6-集成-rag-知识库)
7. [常见问题](#7-常见问题)

---

## 1. 环境准备

### 系统要求
- Windows 操作系统
- Python 3.11+
- 磁盘空间：**约 3GB**（PaddleOCR 模型 ~500MB + 依赖 ~1GB + 输出文件预留）

### 安装依赖

**方式一：一键脚本**

双击 `setup.bat` → 选择镜像源 → 等待完成。脚本会自动安装所有依赖并运行测试验证。

**方式二：手动安装**

```bash
cd tools/pdf_ocr
pip install -r requirements.txt
```

> **注意**：`paddlepaddle` 在 Windows 上仅支持 CPU 版本。400 页 200 DPI 预计耗时 12-20 分钟。

---

## 2. 快速上手（5 分钟）

### 方式一：用脚本（推荐）

直接把 PDF 文件**拖拽到 `run_ocr.bat`** 上 → 选择 `[1] 快速测试` → 自动处理前 5 页并打开结果。

### 方式二：用命令行

先用前 5 页验证工具是否正常工作：

```bash
cd tools/pdf_ocr

# 只处理前 5 页，输出 MD + DOCX，显示详细日志
python ocr_tool.py "D:/教材/计算机网络.pdf" --start-page 1 --end-page 5 -v
```

**预期输出**：
```
正在校验 PDF: D:/教材/计算机网络.pdf
DPI: 200 | 语言: ch | 批大小: 5 | 输出: both
PDF 有效: 432 页
处理范围: 第 1-5 页（共 5 页）
正在加载 PaddleOCR 模型（首次运行需下载 ~500MB，请耐心等待）...
PaddleOCR 模型加载完成
待处理: 5 页
100%|████████████████| 5/5 页 [00:12<00:00,  2.41s/页]

✅ 处理完成！总耗时: 0.2 分钟
==================================================
处理摘要:
  总页数: 432
  已完成: 5 页
  失败:   0 页
  进度:   1.2%
==================================================
输出文件:
  📄 D:/教材/output/计算机网络.md (12.5 KB)
  📄 D:/教材/output/计算机网络.docx (45.3 KB)
```

检查生成的 Markdown 是否包含正确的课文内容。

---

## 3. 全量处理 400+ 页 PDF

### 3.1 直接全量处理（推荐先看 3.2）

```bash
# 默认配置：200 DPI，batch-size=5，输出 MD + DOCX
python ocr_tool.py "D:/教材/计算机网络.pdf" -v
```

### 3.2 分批处理（更安全）

对于 400+ 页大文档，建议分章节处理。这样某个章节出问题不会影响其他章节：

```bash
# 第一章（假设第 1-50 页）
python ocr_tool.py "D:/教材/计算机网络.pdf" --start-page 1 --end-page 50 -v -o ./output/ch01

# 第二章（第 51-100 页）
python ocr_tool.py "D:/教材/计算机网络.pdf" --start-page 51 --end-page 100 -v -o ./output/ch02

# ... 以此类推
```

### 3.3 断点续传（中断后继续）

```bash
# 处理到一半按了 Ctrl+C？没关系，重新运行即可从断点继续：
python ocr_tool.py "D:/教材/计算机网络.pdf" --resume -v
```

工具会自动检测之前的进度文件 `.ocr_checkpoint.json`，跳过已完成的页面。

**工作原理**：
- 每处理完一页，立即保存进度到 `output/.ocr_checkpoint.json`
- Markdown 文件每页追加写入 + 磁盘同步（即使进程被杀，已处理页面不丢失）
- 重新运行时加载进度文件 → 自动跳过已完成页面 → 继续未处理的页面

### 3.4 高精度模式

如果对识别质量要求高（比如直接用于 RAG 入库），可以提高 DPI：

```bash
# 300 DPI 高精度（耗时约 20-30 分钟）
python ocr_tool.py "D:/教材/计算机网络.pdf" --dpi 300 --batch-size 3 -v
```

### 3.5 DOCX 分卷输出

400+ 页全塞进一个 DOCX 文件会很臃肿，建议拆分：

```bash
# 每 100 页生成一个 DOCX 文件
python ocr_tool.py "D:/教材/计算机网络.pdf" --split 100 -v

# 输出：
#   计算机网络.md           (单文件，推荐 AI 读取用)
#   计算机网络_p001-100.docx
#   计算机网络_p101-200.docx
#   计算机网络_p201-300.docx
#   计算机网络_p301-400.docx
#   计算机网络_p401-432.docx
```

---

## 4. 命令行参考

```
用法: python ocr_tool.py <输入PDF路径> [选项]
```

### 全部选项

| 选项 | 默认值 | 说明 |
|------|--------|------|
| `-o, --output-dir` | PDF 同级的 `output/` | 输出目录 |
| `-f, --format` | `both` | 输出格式：`md` / `docx` / `both` |
| `--dpi` | `200` | 渲染分辨率（72-600）。400 页推荐 200 |
| `--lang` | `ch` | 识别语言：`ch` / `en` / `ch_en` |
| `--batch-size` | `5` | Mini-batch 大小（1-20）。越大越快但占内存 |
| `--start-page` | `1` | 起始页码 |
| `--end-page` | `-1`（最后一页） | 结束页码 |
| `--split` | `0`（不拆分） | 每 N 页拆分为独立 DOCX。建议大文档用 `100` |
| `--resume` | 自动询问 | 从上次中断处继续 |
| `--no-resume` | — | 忽略已有进度，强制重新开始 |
| `--no-progress` | — | 关闭进度条（脚本/后台运行时有用） |
| `-v, --verbose` | — | 详细日志输出（DEBUG 级别） |

### 常用场景

```bash
# 场景 1：只要 Markdown（给 AI/RAG 用）
python ocr_tool.py 教材.pdf -f md --dpi 300 -v

# 场景 2：只要 Word（人工校对/打印）
python ocr_tool.py 教材.pdf -f docx --split 100

# 场景 3：测试不同 DPI 的识别质量
python ocr_tool.py 教材.pdf --start-page 10 --end-page 10 --dpi 150
python ocr_tool.py 教材.pdf --start-page 10 --end-page 10 --dpi 300 -o ./output/test300

# 场景 4：批量处理多个 PDF
for f in 教材/*.pdf; do
    python ocr_tool.py "$f" -v
done
```

---

## 5. 输出文件说明

### Markdown 文件（`.md`）

```
# 计算机网络 — OCR 识别结果

> 生成时间: 2026-08-03 14:30:00

---

### 第 1 页

计算机网络是指将多台计算机通过通信线路互联互通，
实现资源共享和信息传递的系统。

TCP/IP 协议是互联网的核心协议，
其中 TCP 提供可靠的、面向连接的数据传输服务。

---

### 第 2 页

...
```

**特点**：
- 每页以 `---` 分隔 + `### 第 N 页` 标记，方便定位原文
- 段落已自动重排（按 OCR 坐标回归原文阅读顺序）
- UTF-8-BOM 编码，Windows 记事本直接打开不乱码
- 流式写入，中断不丢失已处理页面

### DOCX 文件（`.docx`）

- 每页有分页符 + 页码标题
- 微软雅黑 10.5pt，1.5 倍行距，适合校对
- 分卷模式下每 100 页一个文件

### 进度文件（`.ocr_checkpoint.json`）

```json
{
  "version": 1,
  "pdf_path": "D:/教材/计算机网络.pdf",
  "pdf_hash": "a1b2c3d4e5f6...",
  "total_pages": 432,
  "processed_pages": [1, 2, 3, 4, 5, ...],
  "failed_pages": {"15": "OCR 识别失败: ..."},
  "last_page": 42,
  "updated_at": "2026-08-03T14:30:00"
}
```

自动生成、自动读取。不需要手动编辑。

---

## 6. 集成 RAG 知识库

OCR 产出的 Markdown 文件 → RAG 知识库的完整流程。

### 6.1 新建集成脚本

在项目根目录创建 `tools/pdf_ocr/ingest_to_rag.py`：

```python
"""
将 OCR 产出的 Markdown 文件导入 StarPal RAG 知识库。

用法:
    python tools/pdf_ocr/ingest_to_rag.py tools/pdf_ocr/output/计算机网络.md

流程:
    Markdown 文件 → 按页码分割 → EmbeddingService 分块 → RAGService 入库
"""

import argparse
import re
import sys
from pathlib import Path

# 添加项目根目录
BASE_DIR = Path(__file__).parent.parent.parent
sys.path.insert(0, str(BASE_DIR))

from database.db_connector import get_connection
from AI_operate.embedding_service import EmbeddingService
from AI_operate.rag_service import RAGService


def parse_markdown_pages(md_path: str) -> list[dict]:
    """解析 OCR 产出的 Markdown 文件，按页码分割。

    OCR 产出的 Markdown 格式：
        ### 第 N 页
        <正文内容>
        ---

    Returns:
        [{'page_num': 1, 'content': '...'}, ...]
    """
    with open(md_path, 'r', encoding='utf-8-sig') as f:
        text = f.read()

    # 按 "### 第 N 页" 分割
    pages = []
    # 匹配页码标记
    pattern = r'### 第 (\d+) 页\s*\n(.*?)(?=---\s*\n### 第 \d+ 页|---\s*\n*$)'
    matches = re.findall(pattern, text, re.DOTALL)

    for page_num, content in matches:
        content = content.strip()
        if content and '未检测到文本' not in content:
            pages.append({
                'page_num': int(page_num),
                'content': content,
            })

    return pages


def create_document(cursor, title: str, doc_type: str, source: str,
                    total_pages: int, knowledge_points: list = None) -> int:
    """在 knowledge_documents 表中创建文档记录。

    Returns:
        新创建的 doc_id
    """
    import json

    cursor.execute(
        """INSERT INTO knowledge_documents
           (title, doc_type, source, source_page, knowledge_points, status)
           VALUES (%s, %s, %s, %s, %s, 'published')""",
        (
            title,
            doc_type,
            source,
            total_pages,
            json.dumps(knowledge_points or [], ensure_ascii=False),
        ),
    )
    return cursor.lastrowid


def main():
    parser = argparse.ArgumentParser(
        description='将 OCR Markdown 导入 RAG 知识库'
    )
    parser.add_argument('md_file', help='OCR 输出的 Markdown 文件路径')
    parser.add_argument(
        '--title', default=None,
        help='文档标题（默认使用文件名）'
    )
    parser.add_argument(
        '--doc-type', default='textbook',
        choices=['textbook', 'rfc', 'knowledge_entry', 'problem_solution',
                 'paper', 'lab', 'other'],
        help='文档类型（默认: textbook）'
    )
    parser.add_argument(
        '--source', default='',
        help='来源信息（如 "谢希仁《计算机网络》第8版"）'
    )
    parser.add_argument(
        '--chunk-size', type=int, default=512,
        help='分块大小（字符数，默认 512）'
    )
    parser.add_argument(
        '--overlap', type=int, default=64,
        help='块间重叠字符数（默认 64）'
    )
    parser.add_argument(
        '--dry-run', action='store_true',
        help='仅预览分块结果，不实际入库'
    )
    args = parser.parse_args()

    md_path = Path(args.md_file)
    if not md_path.exists():
        print(f"❌ 文件不存在: {md_path}")
        sys.exit(1)

    title = args.title or md_path.stem

    # ---- Step 1: 解析 Markdown 页面 ----
    print(f"📖 正在解析: {md_path}")
    pages = parse_markdown_pages(str(md_path))
    print(f"   解析出 {len(pages)} 个有效页面")

    if not pages:
        print("❌ 未找到有效页面内容")
        sys.exit(1)

    # ---- Step 2: 拼接全文 ----
    full_text = '\n\n'.join(
        f"(第 {p['page_num']} 页)\n{p['content']}" for p in pages
    )
    print(f"   全文共 {len(full_text)} 字符")

    # ---- Step 3: 智能分块 ----
    print(f"🔪 正在分块 (chunk_size={args.chunk_size}, overlap={args.overlap})...")
    chunks = EmbeddingService.chunk_document(
        full_text,
        chunk_size=args.chunk_size,
        overlap=args.overlap,
    )
    print(f"   分块完成: {len(chunks)} 个文本块")

    if args.dry_run:
        print("\n--- 分块预览（前 3 块）---")
        for i, chunk in enumerate(chunks[:3]):
            print(f"\n[块 {i + 1}] ({len(chunk)} 字符):")
            print(chunk[:200] + '...' if len(chunk) > 200 else chunk)
        print(f"\n... 共 {len(chunks)} 块")
        return

    # ---- Step 4: 创建文档记录 ----
    print("📝 正在创建文档记录...")
    conn = get_connection()
    if not conn:
        print("❌ 数据库连接失败")
        sys.exit(1)

    try:
        cursor = conn.cursor()
        doc_id = create_document(
            cursor=cursor,
            title=title,
            doc_type=args.doc_type,
            source=args.source or title,
            total_pages=len(pages),
        )
        conn.commit()
        print(f"   文档已创建: doc_id={doc_id}, title={title}")
    except Exception as e:
        print(f"❌ 创建文档失败: {e}")
        conn.close()
        sys.exit(1)

    # ---- Step 5: 入库到 RAG ----
    print("🧠 正在生成嵌入向量并入库到 ChromaDB...")
    rag = RAGService()

    chunks_data = [
        {
            'chunk_index': i,
            'content': chunk,
        }
        for i, chunk in enumerate(chunks)
    ]

    indexed = rag.index_chunks(doc_id, chunks_data)

    if indexed > 0:
        print(f"✅ 成功入库 {indexed} 个知识块！")
    else:
        print("⚠️  块已存入 MySQL，但嵌入向量生成失败（检查 DeepSeek API Key）")

    # ---- Step 6: 摘要 ----
    print("\n" + "=" * 50)
    print("入库摘要:")
    print(f"  文档 ID: {doc_id}")
    print(f"  标题:    {title}")
    print(f"  页数:    {len(pages)}")
    print(f"  文本块:  {len(chunks)}")
    print(f"  已索引:  {indexed}")
    print(f"  源文件:  {md_path}")
    print("=" * 50)

    conn.close()


if __name__ == '__main__':
    main()
```

### 6.2 执行入库

```bash
# 在项目根目录下运行

# Step 1: 先 dry-run 预览分块效果
python tools/pdf_ocr/ingest_to_rag.py tools/pdf_ocr/output/计算机网络.md --dry-run

# Step 2: 确认无误后正式入库
python tools/pdf_ocr/ingest_to_rag.py \
    tools/pdf_ocr/output/计算机网络.md \
    --title "计算机网络（谢希仁 第8版）" \
    --source "谢希仁《计算机网络》第8版 扫描OCR" \
    --doc-type textbook \
    --chunk-size 512

# 可选参数说明:
#   --title      文档标题（显示在知识搜索结果中）
#   --source     来源描述
#   --doc-type   文档类型: textbook(教材) / rfc(RFC标准) / paper(论文) 等
#   --chunk-size 分块大小，默认 512 字符 ≈ 1024 tokens
#   --overlap    块间重叠，默认 64 字符（保留上下文连贯）
```

### 6.3 验证入库效果

入库完成后，通过 API 验证：

```bash
# 方法 1: curl 调知识库搜索 API
curl "http://127.0.0.1:3001/api/knowledge/search?q=TCP三次握手&top_k=5"

# 方法 2: 浏览器打开 AI 对话，问一个教材相关的问题
# 打开 http://127.0.0.1:8888/dashboard.html，在聊天框输入：
#   "解释TCP的三次握手过程"
# 如果看到带「📚 来源引用」的回答，说明 RAG 检索成功
```

### 6.4 已有数据怎么办？

如果之前导入了占位数据（seed data），可以清理后重新导入：

```sql
-- 清理旧知识数据（保留表结构）
DELETE FROM knowledge_chunks;
DELETE FROM knowledge_documents;
DELETE FROM knowledge_relations;
DELETE FROM knowledge_sub_topics;

-- 也可以只清理特定文档
DELETE FROM knowledge_chunks WHERE doc_id = <你的doc_id>;
DELETE FROM knowledge_documents WHERE doc_id = <你的doc_id>;
```

```bash
# 然后重置 ChromaDB 集合（Python 交互）
python -c "
from AI_operate.rag_service import RAGService
rag = RAGService()
rag._collection.delete(where={})  # 清空所有向量
print('ChromaDB 已清空')
"

# 最后重新执行入库
python tools/pdf_ocr/ingest_to_rag.py tools/pdf_ocr/output/计算机网络.md ...
```

### 6.5 处理时间对照

| 步骤 | 耗时 | 说明 |
|------|------|------|
| PDF OCR (400页, 200 DPI) | ~12-20 分钟 | 纯 CPU |
| PDF OCR (400页, 300 DPI) | ~20-35 分钟 | 高质量 |
| Markdown 分块 | ~3 秒 | 本地计算 |
| 嵌入生成 (1000块) | ~2-5 分钟 | 本地 sentence-transformers |
| ChromaDB 入库 | ~10 秒 | 本地持久化 |

**总计**：从扫描 PDF 到可用的 RAG 知识库，约 **15-40 分钟**（取决于 DPI）。

---

## 7. 常见问题

### Q1: PaddleOCR 安装失败？

```bash
# Windows 上 paddlepaddle 只支持 CPU 版
pip install paddlepaddle  # 不要装 paddlepaddle-gpu

# 如果下载慢，使用清华镜像
pip install paddlepaddle -i https://pypi.tuna.tsinghua.edu.cn/simple
```

### Q2: 识别出来的文字有很多错字？

扫描质量是关键变量。可以尝试：

```bash
# 提高 DPI（质量优先）
python ocr_tool.py 教材.pdf --dpi 300

# 降低检测阈值（检出更多文本区域，但可能增加误检）
# 修改 ocr_engine.py 中的 det_db_thresh=0.2
```

### Q3: 处理太慢怎么办？

```bash
# 几种加速策略（按推荐顺序）:
# 1. 降低 DPI
python ocr_tool.py 教材.pdf --dpi 150

# 2. 增大 batch-size（多占内存，但更快）
python ocr_tool.py 教材.pdf --batch-size 10

# 3. 分章节并行处理（开多个终端窗口）
# 终端 1:
python ocr_tool.py 教材.pdf --start-page 1 --end-page 100 -o ./output/p1
# 终端 2:
python ocr_tool.py 教材.pdf --start-page 101 --end-page 200 -o ./output/p2
```

### Q4: 输出文件在哪里？

默认在 PDF 文件同级的 `output/` 目录下。可以用 `-o` 指定其他位置：

```bash
python ocr_tool.py 教材.pdf -o D:/我的输出目录/
```

### Q5: Markdown 可用于什么？

- 直接喂给 AI 对话（Claude/DeepSeek/ChatGPT）作为参考材料
- 导入 RAG 知识库（见第 6 节）
- 用 VS Code / Typora 打开阅读
- 搜索特定知识点：`Ctrl+F "三次握手"`

### Q6: 进度文件可以删除吗？

可以。删除 `output/.ocr_checkpoint.json` 后，下次运行会从头开始。
但如果正在处理中，不要删除——那是断点续传的保障。

### Q7: 处理到一半电脑蓝屏了怎么办？

不用担心。Markdown 文件每页写入后立即同步到磁盘，已处理的页面内容不会丢失。
重新开机后运行：

```bash
python ocr_tool.py "D:/教材/计算机网络.pdf" --resume -v
```

工具会检测到进度文件，自动从未完成的页面继续。
