"""
资料库处理管线编排器 —— 星伴(StarPal) 端到端文件处理调度。

协调文件提取 → 分块 → 入库 → 向量化 → 知识点映射 的完整流程，
并通过回调函数实时推送处理进度。

用法:
    from server.library_pipeline import LibraryPipeline

    pipeline = LibraryPipeline(progress_callback=lambda pct, detail: print(pct, detail))
    result = pipeline.process_upload(
        task_id="uuid-xxx",
        user_id=None,       # None=系统知识库, 具体值=个人资料库
        file_path="/path/to/file.pdf",
        file_name="计算机网络第8版.pdf",
        file_type="scanned_pdf",
        doc_type="textbook",
    )
"""

import os
import sys
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

BASE_DIR = Path(__file__).parent.parent
sys.path.append(str(BASE_DIR))

from AI_operate.embedding_service import EmbeddingService
from AI_operate.rag_service import RAGService
from database.db_connector import get_connection
from server.file_handler import extract_text, get_page_count
from server.knowledge_mapper import KnowledgeMapper


class LibraryPipeline:
    """端到端资料处理管线。

    处理步骤:
      1. 更新 library_tasks → status=processing
      2. 文本提取
      3. 创建 knowledge_documents 记录
      4. 智能分块 (EmbeddingService.chunk_document)
      5. 写入 knowledge_chunks (MySQL) + 向量索引 (ChromaDB)
      6. 知识点映射 (KnowledgeMapper.analyze_document)
      7. 更新 library_tasks → status=completed, progress=100

    异常处理: 任何步骤失败 → library_tasks.status=failed, 记录 error_message。
    """

    # 进度权重（用于计算总体进度百分比）
    STEP_WEIGHTS = {
        "extract": 20,
        "chunk": 15,
        "index": 30,
        "map": 30,
        "finish": 5,
    }

    def __init__(
        self,
        progress_callback: Optional[Callable[[float, Dict[str, Any]], None]] = None,
    ):
        """初始化管线。

        Args:
            progress_callback: 进度回调函数，签名为 (pct: float, detail: dict)。
                                detail 包含 step, page, total, message 等字段。
        """
        self._progress = progress_callback or (lambda pct, detail: None)
        self._rag = RAGService()
        self._embedding = EmbeddingService()
        self._mapper = KnowledgeMapper()
        self._base_progress = 0.0

    def process_upload(
        self,
        task_id: str,
        user_id: Optional[int],
        file_path: str,
        file_name: str,
        file_type: str,
        doc_type: str = "other",
        title: Optional[str] = None,
    ) -> Dict[str, Any]:
        """执行完整的资料处理管线。

        Args:
            task_id: 任务 UUID。
            user_id: 用户 ID（None=系统知识库）。
            file_path: 服务器端文件路径。
            file_name: 原始文件名。
            file_type: 文件类型标识 ('scanned_pdf'|'text_pdf'|'word')。
            doc_type: 文档类型标签 (textbook/rfc/paper/note/other)。
            title: 文档标题（默认取文件名）。

        Returns:
            处理结果: {success: bool, doc_id: int, chunks: int, message: str}
        """
        title = title or file_name
        self._task_id = task_id

        try:
            # Step 0: 标记为处理中
            self._update_task_status(task_id, "processing", 0, {"step": "start"})

            # Step 1: 文本提取 (0-20%)
            self._report_progress("extract", 0, "正在提取文本...")
            total_pages = get_page_count(file_path, file_type)
            self._report_progress("extract", 5, f"文本提取中 (共 {total_pages} 页)...")

            def ocr_progress(page, total):
                pct = 5 + int((page / max(total, 1)) * 55)  # 5%→60% 覆盖 OCR 阶段
                self._report_progress("extract", pct,
                    f"OCR 识别中 ({page}/{total} 页)")

            raw_text = extract_text(file_path, file_type, progress_callback=ocr_progress)
            if not raw_text or not raw_text.strip():
                raise RuntimeError("提取的文本内容为空")

            self._advance_progress("extract", 20)
            self._report_progress("extract", 20, f"文本提取完成 ({len(raw_text)} 字符)")

            # Step 2: 创建知识文档记录 (20-25%)
            self._report_progress("chunk", 20, "创建文档记录...")
            doc_id = self._create_document(
                title=title,
                doc_type=doc_type,
                file_name=file_name,
                user_id=user_id,
            )
            self._advance_progress("chunk", 25)

            # Step 3: 智能分块 (25-35%)
            self._report_progress("chunk", 25, "正在智能分块...")
            chunks_text = self._embedding.chunk_document(raw_text)
            if not chunks_text:
                raise RuntimeError("文档分块结果为空")

            self._advance_progress("chunk", 35)
            self._report_progress("chunk", 35, f"分块完成 ({len(chunks_text)} 块)")

            # Step 4: 写入 MySQL + ChromaDB 向量索引 (35-65%)
            self._report_progress("index", 35, "正在写入数据库并生成向量索引...")

            chunks_data = []
            for i, text in enumerate(chunks_text):
                chunks_data.append({
                    "chunk_index": i,
                    "content": text,
                    "content_hash": EmbeddingService.compute_content_hash(text),
                    "token_count": EmbeddingService.estimate_tokens(text),
                })

            indexed_count = self._rag.index_chunks(doc_id, chunks_data, user_id=user_id)
            self._advance_progress("index", 65)
            self._report_progress("index", 65, f"向量索引完成 ({indexed_count} 块)")

            # Step 5: 知识点映射 (65-95%)
            self._report_progress("map", 65, "正在进行知识点自动映射...")
            analysis = self._mapper.analyze_document(doc_id)
            self._advance_progress("map", 95)
            mapped = analysis.get("mapped_chunks", 0)
            coverage = analysis.get("coverage_pct", 0)
            self._report_progress(
                "map", 95,
                f"知识点映射完成 ({mapped} 块映射, 覆盖 {coverage}% 知识点)",
            )

            # Step 6: 完成任务 (95-100%)
            self._advance_progress("finish", 100)
            self._update_task_status(
                task_id, "completed", 100,
                {"step": "completed", "doc_id": doc_id, "chunks": indexed_count,
                 "mapped_chunks": mapped, "coverage_pct": coverage},
                doc_id=doc_id,
            )

            return {
                "success": True,
                "doc_id": doc_id,
                "chunks": indexed_count,
                "mapped_chunks": mapped,
                "coverage_pct": coverage,
                "message": f"处理完成：{indexed_count} 个知识块已索引，覆盖 {coverage}% 知识点",
            }

        except Exception as e:
            error_msg = str(e)
            self._update_task_status(
                task_id, "failed", self._base_progress,
                {"step": "failed", "error": error_msg},
            )
            print(f"[LibraryPipeline] 任务 {task_id} 处理失败: {error_msg}")
            return {
                "success": False,
                "doc_id": None,
                "chunks": 0,
                "message": f"处理失败: {error_msg}",
            }

    # ================================================================
    # 内部方法
    # ================================================================

    def _report_progress(self, step: str, pct: float, message: str) -> None:
        """报告处理进度并写入 DB。"""
        self._progress(pct, {"step": step, "message": message})
        if self._task_id:
            self._update_task_status(self._task_id, "processing", pct,
                                     {"step": step, "message": message})

    def _advance_progress(self, step: str, target_pct: float) -> None:
        """将进度推进到目标百分比。"""
        self._base_progress = target_pct

    def _create_document(
        self, title: str, doc_type: str, file_name: str,
        user_id: Optional[int],
    ) -> int:
        """在 knowledge_documents 中创建记录。

        Args:
            title: 文档标题。
            doc_type: 文档类型。
            file_name: 原始文件名。
            user_id: None=系统资料，具体值=个人资料。

        Returns:
            新创建的 doc_id。
        """
        conn = get_connection()
        if not conn:
            raise RuntimeError("数据库连接失败")

        try:
            cursor = conn.cursor()
            cursor.execute(
                """INSERT INTO knowledge_documents
                   (title, doc_type, source, status, user_id)
                   VALUES (%s, %s, %s, 'published', %s)""",
                (title, doc_type, file_name, user_id),
            )
            conn.commit()
            doc_id = cursor.lastrowid
            return doc_id
        except Exception as e:
            conn.rollback()
            raise RuntimeError(f"创建文档记录失败: {e}")
        finally:
            cursor.close()
            conn.close()

    def _update_task_status(
        self, task_id: str, status: str, progress_pct: float,
        detail: Dict[str, Any], doc_id: Optional[int] = None,
    ) -> None:
        """更新 library_tasks 表中的任务状态。"""
        import json

        conn = get_connection()
        if not conn:
            return

        try:
            cursor = conn.cursor()
            if doc_id:
                cursor.execute(
                    """UPDATE library_tasks
                       SET status=%s, progress_pct=%s, progress_detail=%s, doc_id=%s
                       WHERE task_id=%s""",
                    (status, progress_pct, json.dumps(detail, ensure_ascii=False),
                     doc_id, task_id),
                )
            else:
                cursor.execute(
                    """UPDATE library_tasks
                       SET status=%s, progress_pct=%s, progress_detail=%s
                       WHERE task_id=%s""",
                    (status, progress_pct, json.dumps(detail, ensure_ascii=False),
                     task_id),
                )
            conn.commit()
        except Exception as e:
            print(f"[LibraryPipeline] 更新任务状态失败: {e}")
        finally:
            cursor.close()
            conn.close()


# 模块独立测试
if __name__ == "__main__":
    def on_progress(pct, detail):
        step = detail.get("step", "?")
        msg = detail.get("message", "")
        print(f"  [{pct:5.1f}%] {step}: {msg}")

    pipeline = LibraryPipeline(progress_callback=on_progress)
    print("LibraryPipeline 已初始化（测试需要传入真实文件和 task_id）")
