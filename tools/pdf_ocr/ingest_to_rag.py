#!/usr/bin/env python3
"""
将 OCR 产出的 Markdown 文件导入 StarPal RAG 知识库。

完整管线:
    OCR Markdown → 按页码解析 → 拼接全文 → EmbeddingService 智能分块
    → RAGService 生成向量 + 入库 MySQL + ChromaDB

用法:
    # 预览分块（不写入数据库）
    python tools/pdf_ocr/ingest_to_rag.py output/计算机网络.md --dry-run

    # 正式入库
    python tools/pdf_ocr/ingest_to_rag.py output/计算机网络.md \
        --title "计算机网络（谢希仁 第8版）" \
        --source "谢希仁《计算机网络》第8版 扫描OCR"

    # 仅导入前100页（测试用）
    python tools/pdf_ocr/ingest_to_rag.py output/计算机网络.md \
        --max-pages 100 --dry-run

依赖: 需要在 StarPal 项目根目录下运行，确保数据库和模型可用。
"""

import argparse
import json
import re
import sys
from pathlib import Path

# 将项目根目录加入 sys.path，确保能导入项目模块
BASE_DIR = Path(__file__).parent.parent.parent.resolve()
sys.path.insert(0, str(BASE_DIR))

from database.db_connector import get_connection
from AI_operate.embedding_service import EmbeddingService
from AI_operate.rag_service import RAGService


# ---------------------------------------------------------------------------
# Markdown 页面解析
# ---------------------------------------------------------------------------

def parse_markdown_pages(md_path: str) -> list:
    """解析 OCR 产出的 Markdown 文件，按页码提取内容。

    OCR 产出的 Markdown 格式:
        ### 第 N 页
        <正文段落>

        ---

    Args:
        md_path: Markdown 文件路径

    Returns:
        [{'page_num': 1, 'content': '...'}, ...]
    """
    with open(md_path, 'r', encoding='utf-8-sig') as f:
        text = f.read()

    pages = []
    # 匹配 "### 第 N 页" 标记，提取后续内容直到下一个页码标记或分隔线
    pattern = r'### 第 (\d+) 页\s*\n(.*?)(?=\n---\s*\n### 第 \d+ 页|\n---\s*\n*$)'
    matches = re.findall(pattern, text, re.DOTALL)

    for page_num, content in matches:
        content = content.strip()
        # 跳过空页和仅包含"未检测到文本"标记的页
        if not content or content == '*（本页未检测到文本）*':
            continue
        pages.append({
            'page_num': int(page_num),
            'content': content,
        })

    return pages


# ---------------------------------------------------------------------------
# 文档记录创建
# ---------------------------------------------------------------------------

def create_document(
    cursor,
    title: str,
    doc_type: str,
    source: str,
    total_pages: int,
    knowledge_points: list = None,
) -> int:
    """在 knowledge_documents 表中创建文档记录。

    Args:
        cursor: 数据库游标
        title: 文档标题
        doc_type: 文档类型 (textbook/rfc/knowledge_entry/...)
        source: 来源描述
        total_pages: 总页数
        knowledge_points: 关联的知识点列表

    Returns:
        新创建的 doc_id
    """
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


# ---------------------------------------------------------------------------
# 文本合并
# ---------------------------------------------------------------------------

def merge_pages(pages: list, max_pages: int = None) -> str:
    """将按页解析的内容合并为全文。

    每页内容前插入页码标记，保留页码与内容的对应关系。

    Args:
        pages: parse_markdown_pages 的返回值
        max_pages: 最多合并多少页（None = 全部）

    Returns:
        拼接后的全文
    """
    if max_pages:
        pages = pages[:max_pages]

    parts = []
    for p in pages:
        parts.append(f"(第 {p['page_num']} 页)\n{p['content']}")

    return '\n\n'.join(parts)


# ---------------------------------------------------------------------------
# 主管线
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description='将 OCR Markdown 导入 StarPal RAG 知识库',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 预览分块效果
  python ingest_to_rag.py output/计算机网络.md --dry-run

  # 正式入库
  python ingest_to_rag.py output/计算机网络.md --title "计算机网络" --source "谢希仁 第8版"

  # 仅导入前100页测试
  python ingest_to_rag.py output/计算机网络.md --max-pages 100
        """,
    )

    parser.add_argument(
        'md_file',
        help='OCR 输出的 Markdown 文件路径',
    )
    parser.add_argument(
        '--title', default=None,
        help='文档标题（默认使用文件名）',
    )
    parser.add_argument(
        '--doc-type', default='textbook',
        choices=[
            'textbook', 'rfc', 'knowledge_entry',
            'problem_solution', 'paper', 'lab', 'other',
        ],
        help='文档类型（默认: textbook）',
    )
    parser.add_argument(
        '--source', default='',
        help='来源描述（如 "谢希仁《计算机网络》第8版 扫描OCR"）',
    )
    parser.add_argument(
        '--chunk-size', type=int, default=512,
        help='分块大小，字符数（默认: 512，约 1024 tokens）',
    )
    parser.add_argument(
        '--overlap', type=int, default=64,
        help='块间重叠字符数（默认: 64）',
    )
    parser.add_argument(
        '--max-pages', type=int, default=None,
        help='最多导入页数（用于测试，默认全部）',
    )
    parser.add_argument(
        '--dry-run', action='store_true',
        help='仅预览分块结果，不实际写入数据库',
    )
    parser.add_argument(
        '-v', '--verbose', action='store_true',
        help='详细输出',
    )

    args = parser.parse_args()

    # ---- 校验输入文件 ----
    md_path = Path(args.md_file)
    if not md_path.exists():
        print(f"[ERROR] 文件不存在: {md_path}")
        sys.exit(1)

    title = args.title or md_path.stem
    source = args.source or title

    # ---- Step 1: 解析 Markdown ----
    print(f"[1/5] 解析 Markdown: {md_path.name}")
    pages = parse_markdown_pages(str(md_path))
    print(f"      解析出 {len(pages)} 个有效页面")

    if not pages:
        print("[ERROR] 未找到有效页面内容（Markdown 中无 '### 第 N 页' 标记？）")
        sys.exit(1)

    if args.max_pages:
        pages = pages[:args.max_pages]
        print(f"      限制为前 {args.max_pages} 页")

    # ---- Step 2: 拼接全文 ----
    print(f"[2/5] 拼接全文...")
    full_text = merge_pages(pages)
    print(f"      全文 {len(full_text):,} 字符")

    if args.verbose:
        # 显示前 500 字符预览
        print(f"      --- 预览（前 500 字符）---")
        print(full_text[:500])
        print(f"      --- 预览结束 ---")

    # ---- Step 3: 智能分块 ----
    print(f"[3/5] 智能分块 (chunk_size={args.chunk_size}, overlap={args.overlap})...")
    chunks = EmbeddingService.chunk_document(
        full_text,
        chunk_size=args.chunk_size,
        overlap=args.overlap,
    )
    print(f"      分块完成: {len(chunks)} 个文本块")
    print(f"      平均每块: {sum(len(c) for c in chunks) // max(len(chunks), 1):,} 字符")

    # ---- Dry-run 模式: 仅预览 ----
    if args.dry_run:
        print("\n" + "=" * 60)
        print("DRY-RUN 模式 — 仅预览，不写入数据库")
        print("=" * 60)

        # 显示分块统计
        chunk_sizes = [len(c) for c in chunks]
        print(f"\n分块统计:")
        print(f"  总块数: {len(chunks)}")
        print(f"  最小块: {min(chunk_sizes)} 字符")
        print(f"  最大块: {max(chunk_sizes)} 字符")
        print(f"  平均块: {sum(chunk_sizes) // len(chunks)} 字符")

        # 显示前 3 块
        print(f"\n前 3 块预览:")
        for i, chunk in enumerate(chunks[:3]):
            print(f"\n  [块 {i + 1}] ({len(chunk)} 字符):")
            preview = chunk[:300] + '...' if len(chunk) > 300 else chunk
            # 缩进处理
            for line in preview.split('\n'):
                print(f"    {line}")

        print(f"\n  ... 共 {len(chunks)} 块")
        print(f"\n如需正式入库，去掉 --dry-run 参数重新运行。")
        return

    # ---- Step 4: 创建文档记录 ----
    print(f"[4/5] 创建文档记录...")
    conn = get_connection()
    if not conn:
        print("[ERROR] 数据库连接失败！请确认 MySQL 已启动且配置正确。")
        sys.exit(1)

    doc_id = None
    try:
        cursor = conn.cursor()
        doc_id = create_document(
            cursor=cursor,
            title=title,
            doc_type=args.doc_type,
            source=source,
            total_pages=len(pages),
        )
        conn.commit()
        print(f"      文档已创建: doc_id={doc_id}")
        print(f"      标题: {title}")
        print(f"      类型: {args.doc_type}")
    except Exception as e:
        print(f"[ERROR] 创建文档记录失败: {e}")
        conn.close()
        sys.exit(1)

    # ---- Step 5: 向量化 + 入库 ----
    print(f"[5/5] 生成嵌入向量并入库...")
    print(f"      使用模型: {EmbeddingService.LOCAL_MODEL_NAME}")
    print(f"      这可能需要 2-5 分钟（取决于块数量）...")

    rag = RAGService()
    chunks_data = [
        {
            'chunk_index': i,
            'content': chunk,
        }
        for i, chunk in enumerate(chunks)
    ]

    try:
        indexed = rag.index_chunks(doc_id, chunks_data)
    except Exception as e:
        print(f"[ERROR] 入库失败: {e}")
        print(f"       文档记录已创建 (doc_id={doc_id})，可修复后重试。")
        conn.close()
        sys.exit(1)

    conn.close()

    # ---- 摘要 ----
    print("\n" + "=" * 60)
    print("入库完成!")
    print("=" * 60)
    print(f"  文档 ID:   {doc_id}")
    print(f"  标题:      {title}")
    print(f"  源文件:    {md_path}")
    print(f"  有效页数:  {len(pages)}")
    print(f"  文本块数:  {len(chunks)}")
    print(f"  已索引:    {indexed} 块")
    print(f"  全文大小:  {len(full_text):,} 字符")
    print("=" * 60)

    if indexed > 0:
        print(f"\n验证: curl \"http://127.0.0.1:3001/api/knowledge/search?q=TCP&top_k=3\"")
    else:
        print(f"\n[WARNING] 嵌入生成可能失败，块已存入 MySQL 但未索引到 ChromaDB。")
        print(f"          请检查 EmbeddingService 配置。")

    print(f"\n提示: 打开 http://127.0.0.1:8888/dashboard.html 在 AI 对话中测试 RAG 效果。")


if __name__ == '__main__':
    main()
