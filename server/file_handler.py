"""
文件处理服务 —— 星伴(StarPal) 资料库文本提取引擎。

负责:
- 文件类型自动检测（MIME + 文件头魔数双重验证）
- 安全校验（类型白名单、大小限制）
- 文本提取调度（扫描PDF→PaddleOCR / 文字PDF→PyMuPDF / Word→python-docx）

用法:
    from server.file_handler import detect_file_type, validate_file, extract_text

    ok, err = validate_file(file_path, mime_type)
    if not ok:
        raise ValueError(err)
    ftype = detect_file_type(file_path, mime_type)
    text = extract_text(file_path, ftype)
"""

import os
import struct
from pathlib import Path
from typing import Optional, Tuple

# 支持的文件类型白名单
ALLOWED_MIME_TYPES = {
    "application/pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
}

# 文件魔数（文件头字节签名）
FILE_SIGNATURES = {
    # PDF: %PDF-
    b"%PDF": "application/pdf",
    # DOCX: PK.. (ZIP 格式)
    b"PK\x03\x04": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
}

MAX_FILE_SIZE_MB = 200
MAX_FILE_SIZE_BYTES = MAX_FILE_SIZE_MB * 1024 * 1024


def detect_file_type(file_path: str, mime_type: Optional[str] = None) -> Optional[str]:
    """检测文件实际类型，返回类型标识符。

    检测优先级: 文件头魔数 > MIME type。

    Args:
        file_path: 文件路径。
        mime_type: 客户端报告的 MIME type（可选，作为辅助判断）。

    Returns:
        文件类型标识: 'scanned_pdf' | 'text_pdf' | 'word'
        无法识别时返回 None。
    """
    # Step 1: 读取文件头魔数
    detected_mime = _read_file_signature(file_path)
    effective_mime = detected_mime or mime_type

    if effective_mime is None:
        return None

    # Step 2: PDF 需要进一步区分扫描版和文字版
    if "pdf" in (effective_mime or "").lower():
        return _classify_pdf(file_path)

    # Step 3: DOCX
    if "wordprocessingml" in (effective_mime or "").lower() or "docx" in (effective_mime or "").lower():
        return "word"

    return None


def validate_file(file_path: str, mime_type: Optional[str] = None,
                  max_size_mb: int = MAX_FILE_SIZE_MB) -> Tuple[bool, str]:
    """安全校验上传文件。

    校验项:
    1. 文件是否存在
    2. 文件大小是否超限
    3. MIME type 是否在白名单
    4. 文件头魔数是否匹配

    Args:
        file_path: 文件路径。
        mime_type: 客户端报告的 MIME type。
        max_size_mb: 最大文件大小（MB）。

    Returns:
        (is_valid, error_message) 元组。is_valid=True 表示通过全部检查。
    """
    # 检查文件是否存在
    if not os.path.isfile(file_path):
        return False, "文件不存在或不可读"

    # 检查文件大小
    file_size = os.path.getsize(file_path)
    if file_size == 0:
        return False, "文件为空，请上传有效文件"
    if file_size > max_size_mb * 1024 * 1024:
        return False, f"文件过大（{file_size / 1024 / 1024:.1f}MB），请上传不超过 {max_size_mb}MB 的文件"

    # 检查 MIME type 白名单
    if mime_type and mime_type not in ALLOWED_MIME_TYPES:
        return False, f"不支持的文件格式（{mime_type}），仅支持 PDF 和 Word (.docx)"

    # 检查文件头魔数
    detected = _read_file_signature(file_path)
    if detected is None:
        return False, "无法识别文件类型，请确保上传的是有效的 PDF 或 Word 文档"
    if detected not in ALLOWED_MIME_TYPES:
        return False, f"不支持的文件格式，文件头显示为 {detected}"

    return True, ""


def extract_text(file_path: str, file_type: str,
                 progress_callback=None) -> str:
    """从文件中提取文本内容。

    Args:
        file_path: 文件路径。
        file_type: 文件类型标识 ('scanned_pdf' | 'text_pdf' | 'word')。
        progress_callback: 可选，OCR 进度回调 (page: int, total: int)。

    Returns:
        提取的纯文本内容。
    """
    if file_type == "word":
        return _extract_from_docx(file_path)
    elif file_type in ("text_pdf", "scanned_pdf"):
        return _extract_from_pdf(file_path, file_type, progress_callback)
    else:
        raise ValueError(f"不支持的文件类型: {file_type}")


def get_page_count(file_path: str, file_type: str) -> int:
    """获取文档总页数（用于进度估算）。

    Args:
        file_path: 文件路径。
        file_type: 文件类型标识。

    Returns:
        页数。无法获取时返回 0。
    """
    if file_type in ("text_pdf", "scanned_pdf"):
        try:
            import fitz  # PyMuPDF
            doc = fitz.open(file_path)
            count = doc.page_count
            doc.close()
            return count
        except Exception:
            return 0
    elif file_type == "word":
        # Word 文档没有明确的"页数"概念，返回 0 表示不分页
        return 0
    return 0


# ================================================================
# 内部实现
# ================================================================

def _read_file_signature(file_path: str) -> Optional[str]:
    """读取文件头魔数，返回对应的 MIME type。

    Args:
        file_path: 文件路径。

    Returns:
        MIME type 字符串，无法匹配时返回 None。
    """
    try:
        with open(file_path, "rb") as f:
            header = f.read(8)
    except (IOError, OSError):
        return None

    for signature, mime in FILE_SIGNATURES.items():
        if header.startswith(signature):
            return mime

    return None


def _classify_pdf(file_path: str) -> str:
    """区分 PDF 是扫描版还是文字版。

    策略: 提取前 3 页文本，如果提取到的有效文本字符数 < 50，
    则判定为扫描版（需要 OCR）。

    Args:
        file_path: PDF 文件路径。

    Returns:
        'text_pdf' 或 'scanned_pdf'。
    """
    try:
        import fitz  # PyMuPDF
        doc = fitz.open(file_path)
        pages_to_check = min(3, doc.page_count)
        total_chars = 0
        for i in range(pages_to_check):
            page = doc[i]
            text = page.get_text()
            total_chars += len(text.strip())
        doc.close()
        if total_chars >= 50:
            return "text_pdf"
        return "scanned_pdf"
    except Exception:
        # 无法读取时默认按文字 PDF 处理（让后续提取报错时再降级）
        return "text_pdf"


def _extract_from_pdf(file_path: str, file_type: str,
                      progress_callback=None) -> str:
    if file_type == "scanned_pdf":
        return _extract_via_ocr(file_path, progress_callback)
    return _extract_via_pymupdf(file_path)


def _extract_via_pymupdf(file_path: str) -> str:
    """使用 PyMuPDF 提取文字 PDF 的文本。

    每页之间插入分页标记。
    """
    try:
        import fitz  # PyMuPDF
    except ImportError:
        raise RuntimeError(
            "PyMuPDF (fitz) 未安装，无法提取 PDF 文本。"
            "请运行: pip install PyMuPDF"
        )

    try:
        doc = fitz.open(file_path)
        pages_text = []
        for i in range(doc.page_count):
            page = doc[i]
            text = page.get_text()
            if text.strip():
                pages_text.append(f"[第 {i + 1} 页]\n{text.strip()}")
        doc.close()

        if not pages_text:
            raise RuntimeError("该 PDF 文件中未检测到文本内容，可能是扫描版 PDF")

        return "\n\n".join(pages_text)
    except Exception as e:
        if "未检测到文本" in str(e):
            raise
        raise RuntimeError(f"PDF 文本提取失败: {e}")


def _extract_via_ocr(file_path: str, progress_callback=None) -> str:
    """使用 PyMuPDF + EasyOCR 识别扫描版 PDF 的文本。

    每页渲染为图像后执行 OCR，逐页追加到结果文本中。
    每处理 5 页通过 progress_callback(page, total) 报告进度。
    """
    try:
        import fitz  # PyMuPDF
    except ImportError:
        raise RuntimeError("PyMuPDF (fitz) 未安装，pip install PyMuPDF")

    try:
        import easyocr
    except ImportError:
        raise RuntimeError("EasyOCR 未安装，pip install easyocr")

    try:
        import numpy as np
        doc = fitz.open(file_path)
        total_pages = min(doc.page_count, 600)
        print(f"[OCR] 开始处理 {total_pages} 页扫描 PDF...")

        if progress_callback:
            progress_callback(0, total_pages)

        # 模型加载（CPU 上约 1-3 分钟）
        print("[OCR] 正在加载 EasyOCR 中文模型 (CPU)...")
        reader = easyocr.Reader(['ch_sim'], gpu=False)
        print("[OCR] 模型加载完成，开始逐页识别...")

        pages_text = []
        for i in range(total_pages):
            try:
                page = doc[i]
                # 提高 DPI 改善中文识别率
                pix = page.get_pixmap(dpi=250)

                import tempfile
                with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as tmp:
                    tmp.write(pix.tobytes("png"))
                    tmp_path = tmp.name

                result = reader.readtext(tmp_path, detail=0)
                os.unlink(tmp_path)

                text = "\n".join(result) if result else ""

                if text.strip():
                    pages_text.append(f"[第 {i + 1} 页]\n{text.strip()}")

                if progress_callback and (i + 1) % 5 == 0:
                    progress_callback(i + 1, total_pages)

                if (i + 1) % 20 == 0:
                    print(f"[OCR] 进度: {i + 1}/{total_pages} 页, 已识别 {len(pages_text)} 页有文本")

            except Exception as page_err:
                print(f"[OCR] 第 {i + 1} 页失败: {page_err}")
                continue

        if progress_callback:
            progress_callback(total_pages, total_pages)

        doc.close()
        print(f"[OCR] 完成: {len(pages_text)}/{total_pages} 页有文本内容")

        if not pages_text:
            raise RuntimeError("OCR 未能从任何页面提取到文本")

        return "\n\n".join(pages_text)

    except Exception as e:
        raise RuntimeError(f"OCR 处理失败: {e}")


def _extract_from_docx(file_path: str) -> str:
    """使用 python-docx 提取 Word 文档的文本。

    保留段落结构，段落之间用换行分隔。
    """
    try:
        from docx import Document
    except ImportError:
        raise RuntimeError(
            "python-docx 未安装，无法提取 Word 文本。"
            "请运行: pip install python-docx"
        )

    try:
        doc = Document(file_path)
        paragraphs = []
        for para in doc.paragraphs:
            text = para.text.strip()
            if text:
                paragraphs.append(text)

        if not paragraphs:
            raise RuntimeError("该 Word 文档中未检测到文本内容")

        return "\n\n".join(paragraphs)
    except Exception as e:
        raise RuntimeError(f"Word 文本提取失败: {e}")


# 模块独立测试
if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("用法: python file_handler.py <文件路径>")
        sys.exit(1)

    path = sys.argv[1]
    print(f"文件: {path}")
    print(f"大小: {os.path.getsize(path) / 1024:.1f} KB")

    ok, err = validate_file(path)
    print(f"校验: {'✅ 通过' if ok else '❌ ' + err}")

    if ok:
        ftype = detect_file_type(path)
        print(f"类型: {ftype}")
        if ftype:
            pages = get_page_count(path, ftype)
            print(f"页数: {pages}")
            try:
                text = extract_text(path, ftype)
                print(f"文本: {len(text)} 字符")
                print(text[:500])
            except Exception as e:
                print(f"提取失败: {e}")
