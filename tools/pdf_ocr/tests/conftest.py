"""
测试 Fixtures —— 生成测试用 PDF + 模拟 OCR 结果。

所有测试使用 mock PaddleOCR，不加载真实模型（太重）。
"""

import os
import sys
import tempfile
from pathlib import Path

import pytest

# 将工具目录加入 sys.path
TOOL_DIR = str(Path(__file__).parent.parent.resolve())
if TOOL_DIR not in sys.path:
    sys.path.insert(0, TOOL_DIR)


# ---------------------------------------------------------------------------
# 测试 PDF 生成
# ---------------------------------------------------------------------------

def create_test_pdf(path: str, num_pages: int = 3):
    """使用 reportlab 生成包含中文文本的测试 PDF。

    Args:
        path: 输出路径
        num_pages: 页数
    """
    from reportlab.pdfgen import canvas
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont

    # 尝试注册中文字体（如果系统有的话）
    chinese_font = 'Helvetica'  # fallback
    try:
        # Windows 常见中文字体路径
        font_paths = [
            'C:/Windows/Fonts/msyh.ttc',       # 微软雅黑
            'C:/Windows/Fonts/simsun.ttc',      # 宋体
            'C:/Windows/Fonts/simhei.ttf',      # 黑体
        ]
        for fp in font_paths:
            if os.path.exists(fp):
                pdfmetrics.registerFont(TTFont('ChineseFont', fp))
                chinese_font = 'ChineseFont'
                break
    except Exception:
        pass

    c = canvas.Canvas(path, pagesize=A4)

    test_lines = [
        "计算机网络 — 测试文档",
        "",
        "计算机网络是指将多台计算机通过通信线路互联互通，",
        "实现资源共享和信息传递的系统。",
        "",
        "TCP/IP 协议是互联网的核心协议，",
        "其中 TCP 提供可靠的、面向连接的数据传输服务，",
        "通过三次握手建立连接。",
        "",
        f"—— 第 1 页测试内容",
    ]

    for page in range(1, num_pages + 1):
        y = 750
        for line in test_lines:
            if line.startswith("—— 第"):
                line = f"—— 第 {page} 页测试内容"
            c.setFont(chinese_font, 12)
            c.drawString(72, y, line)
            y -= 20

        c.showPage()

    c.save()


@pytest.fixture
def test_pdf_path(tmp_path):
    """生成一个 3 页的测试 PDF，返回路径。"""
    path = str(tmp_path / "test.pdf")
    create_test_pdf(path, num_pages=3)
    return path


@pytest.fixture
def test_pdf_10p(tmp_path):
    """生成一个 10 页的测试 PDF，用于测试分卷和进度。"""
    path = str(tmp_path / "test_10p.pdf")
    create_test_pdf(path, num_pages=10)
    return path


# ---------------------------------------------------------------------------
# 模拟 OCR 结果
# ---------------------------------------------------------------------------

@pytest.fixture
def sample_ocr_blocks():
    """模拟一页 OCR 识别结果（2 段文字）。"""
    return [
        # 第一段第一行
        {'text': '计算机网络', 'confidence': 0.99, 'bbox': [100, 100, 250, 130]},
        {'text': '是指', 'confidence': 0.95, 'bbox': [260, 102, 320, 128]},
        # 第一段第二行（Y 间距小 → 应合并为一段）
        {'text': '将多台计算机', 'confidence': 0.98, 'bbox': [100, 145, 280, 175]},
        {'text': '互联互通', 'confidence': 0.97, 'bbox': [290, 147, 380, 173]},
        # 第二段第一行（Y 间距大 → 新段落）
        {'text': 'TCP协议三次握手', 'confidence': 0.96, 'bbox': [100, 280, 330, 310]},
    ]


@pytest.fixture
def empty_ocr_blocks():
    """模拟空页面 OCR 结果。"""
    return []


# ---------------------------------------------------------------------------
# 模拟 PaddleOCR (用于 mock)
# ---------------------------------------------------------------------------

class MockPaddleOCR:
    """模拟 PaddleOCR，返回预设结果。"""
    def __init__(self, **kwargs):
        pass

    def ocr(self, img_array, cls=True):
        """返回模拟识别结果。"""
        import numpy as np
        # 返回与 PaddleOCR 相同格式的数据
        return [[
            [
                [[10, 10], [100, 10], [100, 30], [10, 30]],
                ('测试文本', 0.95),
            ],
            [
                [[10, 40], [200, 40], [200, 60], [10, 60]],
                ('计算机网络', 0.98),
            ],
        ]]
