"""
测试 pdf_processor.py — PDF 页面提取。
"""

import os

import pytest
from PIL import Image

from pdf_processor import PdfProcessor, PdfProcessorError


class TestPdfValidation:
    """测试 PDF 文件校验。"""

    def test_valid_pdf(self, test_pdf_path):
        """有效 PDF 应返回 True。"""
        valid, err = PdfProcessor.is_valid_pdf(test_pdf_path)
        assert valid is True
        assert err is None

    def test_nonexistent_file(self):
        """不存在的文件应返回 False。"""
        valid, err = PdfProcessor.is_valid_pdf("/nonexistent/file.pdf")
        assert valid is False
        assert err is not None

    def test_not_a_pdf(self, tmp_path):
        """非 PDF 文件应返回 False。"""
        path = str(tmp_path / "not_a_pdf.txt")
        # 写入明确的非 PDF 二进制内容
        with open(path, 'wb') as f:
            f.write(b'\x00\x01\x02\x03This is not a PDF file\xff\xfe\xfd')
        valid, err = PdfProcessor.is_valid_pdf(path)
        assert valid is False, f"非 PDF 文件不应通过校验: {err}"


class TestPdfProcessor:
    """测试 PDF 处理器基本功能。"""

    def test_open_valid_pdf(self, test_pdf_path):
        """成功打开有效 PDF。"""
        with PdfProcessor(test_pdf_path, dpi=200) as proc:
            assert proc.total_pages == 3
            assert len(proc) == 3

    def test_dpi_out_of_range(self, test_pdf_path):
        """DPI 参数非法时抛出 ValueError。"""
        with pytest.raises(ValueError):
            PdfProcessor(test_pdf_path, dpi=50)
        with pytest.raises(ValueError):
            PdfProcessor(test_pdf_path, dpi=700)

    def test_open_nonexistent(self):
        """打开不存在的文件抛出 PdfProcessorError。"""
        with pytest.raises(PdfProcessorError):
            PdfProcessor("/nonexistent.pdf")

    def test_extract_page(self, test_pdf_path):
        """提取页面返回 PIL Image。"""
        with PdfProcessor(test_pdf_path, dpi=150) as proc:
            img = proc.extract_page(1)
            assert isinstance(img, Image.Image)
            assert img.mode == 'RGB'
            assert img.width > 0 and img.height > 0

    def test_extract_page_out_of_range(self, test_pdf_path):
        """页码越界抛出 PdfProcessorError。"""
        with PdfProcessor(test_pdf_path) as proc:
            with pytest.raises(PdfProcessorError, match='越界'):
                proc.extract_page(999)
            with pytest.raises(PdfProcessorError, match='越界'):
                proc.extract_page(0)

    def test_get_page_size(self, test_pdf_path):
        """获取页面尺寸返回 (width, height) in points。"""
        with PdfProcessor(test_pdf_path) as proc:
            w, h = proc.get_page_size(1)
            assert w > 0 and h > 0
            # A4 = 595 x 842 points
            assert 500 < w < 700

    def test_dpi_affects_image_size(self, test_pdf_path):
        """DPI 影响输出图片尺寸。"""
        with PdfProcessor(test_pdf_path, dpi=100) as proc_low:
            img_low = proc_low.extract_page(1)

        with PdfProcessor(test_pdf_path, dpi=300) as proc_high:
            img_high = proc_high.extract_page(1)

        # 高 DPI 的图片尺寸应更大
        assert img_high.width > img_low.width
        assert img_high.height > img_low.height

    def test_context_manager(self, test_pdf_path):
        """支持 with 语句。"""
        with PdfProcessor(test_pdf_path) as proc:
            _ = proc.extract_page(1)
        # 离开 with 块后应已关闭
        # （PyMuPDF 关闭后访问会抛异常）
        assert proc._doc.is_closed

    def test_iterator(self, test_pdf_path):
        """迭代器逐页 yield。"""
        with PdfProcessor(test_pdf_path) as proc:
            pages = list(proc)
            assert len(pages) == 3
            for page_num, img in pages:
                assert isinstance(page_num, int)
                assert 1 <= page_num <= 3
                assert isinstance(img, Image.Image)

    def test_large_page_count(self, test_pdf_10p):
        """10 页 PDF 迭代器测试（验证大页数场景的内存安全）。"""
        with PdfProcessor(test_pdf_10p) as proc:
            assert proc.total_pages == 10
            count = 0
            for page_num, img in proc:
                count += 1
                assert img.width > 0
                # 模拟：每次迭代后不保留图片引用（确保可被 GC）
            assert count == 10
