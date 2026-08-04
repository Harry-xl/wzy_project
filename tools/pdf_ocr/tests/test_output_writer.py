"""
测试 output_writer.py — 流式输出 MD/DOCX。
"""

import os
import tempfile
import shutil

import pytest
from PIL import Image

from output_writer import OutputWriter, OutputWriterError


class TestParagraphReconstruction:
    """测试段落重排算法。"""

    def test_two_paragraphs(self, sample_ocr_blocks):
        """两个段落的文本块应重排为两个段落。"""
        paragraphs = OutputWriter._reconstruct_paragraphs(sample_ocr_blocks)
        assert len(paragraphs) == 2

        # 第一段应包含"计算机网络"和"互联互通"
        assert '计算机网络' in paragraphs[0]
        assert '互联互通' in paragraphs[0]

        # 第二段是 TCP
        assert 'TCP协议' in paragraphs[1]

    def test_empty_blocks(self, empty_ocr_blocks):
        """空列表返回空列表。"""
        paragraphs = OutputWriter._reconstruct_paragraphs(empty_ocr_blocks)
        assert paragraphs == []

    def test_single_block(self):
        """单个文本块返回单段落。"""
        blocks = [
            {'text': '独立文本', 'confidence': 0.95, 'bbox': [100, 100, 200, 130]},
        ]
        paragraphs = OutputWriter._reconstruct_paragraphs(blocks)
        assert len(paragraphs) == 1
        assert '独立文本' in paragraphs[0]

    def test_same_line_merge(self):
        """同一行的文本块应合并。"""
        blocks = [
            {'text': '左', 'confidence': 0.99, 'bbox': [10, 100, 50, 120]},
            {'text': '中', 'confidence': 0.98, 'bbox': [60, 101, 100, 119]},
            {'text': '右', 'confidence': 0.97, 'bbox': [110, 100, 150, 120]},
        ]
        paragraphs = OutputWriter._reconstruct_paragraphs(blocks)
        # 只有一行，一个段落
        assert len(paragraphs) == 1
        # "左 中 右" should appear in order
        assert '左' in paragraphs[0]
        assert '中' in paragraphs[0]
        assert '右' in paragraphs[0]


class TestMarkdownOutput:
    """测试 Markdown 输出。"""

    @pytest.fixture
    def writer(self, tmp_path):
        """创建仅输出 MD 的 writer。"""
        output_dir = str(tmp_path / "output")
        return OutputWriter(output_dir, "test", md_enabled=True, docx_enabled=False)

    def test_write_single_page(self, writer, sample_ocr_blocks):
        """写入单页 MD。"""
        writer.write_page(1, sample_ocr_blocks)
        writer.finalize('md')

        assert len(writer.output_paths) == 1
        assert os.path.exists(writer.output_paths[0])

        with open(writer.output_paths[0], 'r', encoding='utf-8-sig') as f:
            content = f.read()

        assert '### 第 1 页' in content
        assert '计算机网络' in content
        assert '---' in content

    def test_write_multiple_pages(self, writer, sample_ocr_blocks):
        """写入多页 MD。"""
        for page in range(1, 6):
            writer.write_page(page, sample_ocr_blocks)
        writer.finalize('md')

        with open(writer.output_paths[0], 'r', encoding='utf-8-sig') as f:
            content = f.read()

        assert '### 第 1 页' in content
        assert '### 第 5 页' in content
        assert content.count('### 第') == 5

    def test_empty_page(self, writer, empty_ocr_blocks):
        """空页面应显示占位文本。"""
        writer.write_page(1, empty_ocr_blocks)
        writer.finalize('md')

        with open(writer.output_paths[0], 'r', encoding='utf-8-sig') as f:
            content = f.read()

        assert '未检测到文本' in content

    def test_streaming_flush(self, writer, sample_ocr_blocks):
        """验证流式写入：未 finalize 时文件已有内容。"""
        writer.write_page(1, sample_ocr_blocks)
        # 未调用 finalize，但文件应已有内容（flush 已执行）
        assert os.path.exists(writer._md_path)
        with open(writer._md_path, 'r', encoding='utf-8-sig') as f:
            content = f.read()
        assert '计算机网络' in content

        writer.finalize('md')


class TestDocxOutput:
    """测试 DOCX 输出。"""

    @pytest.fixture
    def writer(self, tmp_path):
        """创建仅输出 DOCX 的 writer。"""
        output_dir = str(tmp_path / "output")
        return OutputWriter(output_dir, "test", md_enabled=False, docx_enabled=True)

    def test_write_single_page_docx(self, writer, sample_ocr_blocks):
        """写入单页 DOCX。"""
        writer.write_page(1, sample_ocr_blocks)
        writer.finalize('docx')

        assert len(writer.output_paths) == 1
        assert writer.output_paths[0].endswith('.docx')
        assert os.path.getsize(writer.output_paths[0]) > 0

    def test_docx_is_valid(self, writer, sample_ocr_blocks):
        """DOCX 文件可被 python-docx 重新读取。"""
        writer.write_page(1, sample_ocr_blocks)
        writer.finalize('docx')

        from docx import Document
        doc = Document(writer.output_paths[0])
        # 应有至少一个段落
        paragraphs_text = [p.text for p in doc.paragraphs]
        assert any('计算机网络' in t for t in paragraphs_text)

    def test_split_pages(self, tmp_path, sample_ocr_blocks):
        """分卷模式：每 2 页生成一个 DOCX。"""
        output_dir = str(tmp_path / "output")
        writer = OutputWriter(
            output_dir, "test", split_pages=2,
            md_enabled=False, docx_enabled=True,
        )

        # 写入 5 页 → 应生成 3 个文件（1-2, 3-4, 5）
        for page in range(1, 6):
            writer.write_page(page, sample_ocr_blocks)
        writer.finalize('docx')

        paths = writer.output_paths
        assert len(paths) == 3
        assert 'p001-002' in paths[0]
        assert 'p003-004' in paths[1]
        assert 'p005-005' in paths[2]  # Could be just "p005" since only 1 page


class TestBothOutput:
    """测试同时输出 MD+DOCX。"""

    def test_both_formats(self, tmp_path, sample_ocr_blocks):
        """同时输出 MD 和 DOCX。"""
        output_dir = str(tmp_path / "output")
        writer = OutputWriter(output_dir, "test", md_enabled=True, docx_enabled=True)

        writer.write_page(1, sample_ocr_blocks)
        writer.finalize('both')

        paths = writer.output_paths
        assert len(paths) == 2
        assert any(p.endswith('.md') for p in paths)
        assert any(p.endswith('.docx') for p in paths)
