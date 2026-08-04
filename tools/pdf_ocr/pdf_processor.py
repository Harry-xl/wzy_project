"""
PDF 页面提取器 —— 将扫描 PDF 逐页转为 PIL Image。

使用 PyMuPDF (fitz) 渲染 PDF 页面，支持迭代器模式和随机访问。
针对 400+ 页大文档设计：每次只在内存中保留一页图片。

用法:
    processor = PdfProcessor("教材.pdf", dpi=200)
    for page_num, image in processor:
        # image 是 PIL.Image 对象
        ...
    # 或随机访问
    img = processor.extract_page(42)
"""

import os
from pathlib import Path
from typing import Iterator, Optional, Tuple

import fitz  # PyMuPDF
from PIL import Image


class PdfProcessorError(Exception):
    """PDF 处理异常。"""
    pass


class PdfProcessor:
    """将扫描 PDF 逐页转为 PIL Image。

    支持：
    - 迭代器模式（逐页 yield，内存友好）
    - 随机访问（extract_page，断点续传用）
    - 总页数查询

    Attributes:
        pdf_path: PDF 文件绝对路径
        dpi: 渲染分辨率（默认 200）
        total_pages: 总页数
    """

    def __init__(self, pdf_path: str, dpi: int = 200):
        """初始化 PDF 处理器。

        Args:
            pdf_path: PDF 文件路径（相对或绝对）
            dpi: 渲染 DPI，范围 72-600，默认 200
                400页文档建议 200（速度优先），追求质量可用 300

        Raises:
            PdfProcessorError: 文件不存在或不是有效 PDF
            ValueError: DPI 参数不合法
        """
        if dpi < 72 or dpi > 600:
            raise ValueError(f"DPI 参数必须在 72-600 之间，当前值: {dpi}")

        self.pdf_path = str(Path(pdf_path).resolve())
        self.dpi = dpi

        if not os.path.isfile(self.pdf_path):
            raise PdfProcessorError(f"PDF 文件不存在: {self.pdf_path}")

        try:
            self._doc = fitz.open(self.pdf_path)
        except Exception as e:
            raise PdfProcessorError(f"无法打开 PDF 文件（可能不是有效 PDF）: {e}")

        self.total_pages = len(self._doc)
        if self.total_pages == 0:
            raise PdfProcessorError(f"PDF 文件没有页面: {self.pdf_path}")

    def __len__(self) -> int:
        """返回总页数。"""
        return self.total_pages

    def __iter__(self) -> Iterator[Tuple[int, Image.Image]]:
        """逐页迭代，yield (1-based 页码, PIL Image)。

        每次只在内存中保留一页图片，适合 400+ 页大文档。
        """
        for page_num in range(1, self.total_pages + 1):
            yield page_num, self.extract_page(page_num)

    def extract_page(self, page_num: int) -> Image.Image:
        """提取指定页为 PIL Image（随机访问）。

        Args:
            page_num: 页码（1-based）

        Returns:
            PIL.Image 对象（RGB 模式）

        Raises:
            PdfProcessorError: 页码越界或渲染失败
        """
        if page_num < 1 or page_num > self.total_pages:
            raise PdfProcessorError(
                f"页码越界: {page_num}（有效范围 1-{self.total_pages}）"
            )

        try:
            # 缩放矩阵：将 PDF points 转为指定 DPI 的像素
            zoom = self.dpi / 72.0
            mat = fitz.Matrix(zoom, zoom)

            page = self._doc[page_num - 1]  # fitz 是 0-based
            pix = page.get_pixmap(matrix=mat)

            # 转为 PIL Image
            if pix.n < 4:  # RGB 或无 alpha
                img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
            else:  # RGBA → RGB
                img = Image.frombytes("RGBA", [pix.width, pix.height], pix.samples)
                img = img.convert("RGB")

            return img

        except Exception as e:
            raise PdfProcessorError(f"提取第 {page_num} 页失败: {e}")

    def get_page_size(self, page_num: int = 1) -> Tuple[float, float]:
        """获取页面原始尺寸（points）。

        Args:
            page_num: 页码（1-based，默认第1页）

        Returns:
            (宽度, 高度) 单位 points
        """
        if page_num < 1 or page_num > self.total_pages:
            raise PdfProcessorError(
                f"页码越界: {page_num}（有效范围 1-{self.total_pages}）"
            )
        rect = self._doc[page_num - 1].rect
        return (rect.width, rect.height)

    @staticmethod
    def is_valid_pdf(path: str) -> Tuple[bool, Optional[str]]:
        """快速校验文件是否为有效 PDF（不加载全部页面）。

        两重校验：
        1. 检查文件头是否包含 PDF 魔数 %PDF
        2. 用 PyMuPDF 打开验证页数 > 0

        Args:
            path: 文件路径

        Returns:
            (是否有效, 错误信息) — 有效时错误信息为 None
        """
        path = str(Path(path).resolve())

        if not os.path.isfile(path):
            return False, f"文件不存在: {path}"

        # 检查 PDF 魔数
        try:
            with open(path, 'rb') as f:
                header = f.read(5)
            if not header.startswith(b'%PDF'):
                return False, "文件不是有效的 PDF 格式（缺少 PDF 文件头标识）"
        except OSError as e:
            return False, f"无法读取文件: {e}"

        try:
            doc = fitz.open(path)
            page_count = len(doc)
            doc.close()

            if page_count == 0:
                return False, "PDF 文件没有页面"
            return True, None

        except Exception as e:
            return False, f"PDF 文件损坏或无法打开: {e}"

    def close(self):
        """关闭 PDF 文档，释放资源。"""
        if hasattr(self, '_doc') and self._doc:
            self._doc.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()


# --- 模块自测 (python pdf_processor.py) ---
if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("用法: python pdf_processor.py <PDF文件路径> [DPI]")
        print("示例: python pdf_processor.py 教材.pdf 200")
        sys.exit(1)

    pdf_path = sys.argv[1]
    dpi = int(sys.argv[2]) if len(sys.argv) > 2 else 200

    # 先校验
    valid, err = PdfProcessor.is_valid_pdf(pdf_path)
    if not valid:
        print(f"❌ {err}")
        sys.exit(1)

    with PdfProcessor(pdf_path, dpi=dpi) as proc:
        print(f"PDF 有效: {proc.total_pages} 页, {dpi} DPI")
        print(f"第1页尺寸: {proc.get_page_size(1)}")

        # 提取前 3 页做测试
        for page_num, img in proc:
            print(f"  第 {page_num} 页: {img.size[0]}x{img.size[1]} px, "
                  f"内存 {img.size[0] * img.size[1] * 3 // (1024*1024)} MB")
            if page_num >= 3:
                break

    print("✅ 自测通过")
