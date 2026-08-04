"""
测试 ocr_engine.py — PaddleOCR 封装（使用 mock）。
"""

from unittest.mock import patch, MagicMock

import pytest
from PIL import Image

from ocr_engine import OcrEngine, OcrEngineError


class TestOcrEngineInit:
    """测试引擎初始化。"""

    def test_default_init(self):
        """默认参数初始化。"""
        engine = OcrEngine()
        assert engine.lang == 'ch'
        assert engine.use_gpu is False
        assert engine.is_loaded is False

    def test_invalid_lang(self):
        """不支持的语言抛出 ValueError。"""
        with pytest.raises(ValueError, match='不支持的语言'):
            OcrEngine(lang='jp')

    def test_custom_params(self):
        """自定义参数初始化。"""
        engine = OcrEngine(
            lang='ch_en',
            use_gpu=False,
            det_db_thresh=0.5,
            rec_batch_num=8,
        )
        assert engine.lang == 'ch_en'
        assert engine._det_db_thresh == 0.5
        assert engine._rec_batch_num == 8

    def test_get_info_before_load(self):
        """未加载模型时的信息查询。"""
        engine = OcrEngine()
        info = engine.get_info()
        assert info['model_loaded'] is False
        assert info['call_count'] == 0
        assert info['lang'] == 'ch'


class TestOcrEngineNormalize:
    """测试结果标准化。"""

    def test_normalize_valid_results(self):
        """标准化有效的 PaddleOCR 返回格式。"""
        raw = [[
            [
                [[10, 10], [100, 10], [100, 30], [10, 30]],
                ('测试文本', 0.95),
            ],
            [
                [[10, 40], [200, 40], [200, 60], [10, 60]],
                ('计算机网络', 0.98),
            ],
        ]]

        result = OcrEngine._normalize_results(raw)
        assert len(result) == 2
        assert result[0]['text'] == '测试文本'
        assert result[0]['confidence'] == 0.95
        assert result[0]['bbox'] == [10, 10, 100, 30]
        assert result[1]['text'] == '计算机网络'

    def test_normalize_empty_page(self):
        """空页面（无文本）返回空列表。"""
        assert OcrEngine._normalize_results(None) == []
        assert OcrEngine._normalize_results([None]) == []

    def test_normalize_malformed_input(self):
        """处理畸形的输入。"""
        raw = [[
            [],  # 空条目，应跳过
            [
                [[10, 10], [100, 10], [100, 30], [10, 30]],
                ('OK', 0.9),
            ],
        ]]
        result = OcrEngine._normalize_results(raw)
        assert len(result) == 1
        assert result[0]['text'] == 'OK'


class TestOcrEngineMocked:
    """使用 mock PaddleOCR 测试引擎方法。"""

    @pytest.fixture
    def mock_paddleocr(self):
        """Mock PaddleOCR —— 直接设置 _ocr 属性绕过懒加载。

        paddleocr 未安装时无法 mock 其模块路径，改为 mock OcrEngine._ensure_loaded。
        """
        mock_instance = MagicMock()
        mock_instance.ocr.return_value = [[
            [
                [[10, 10], [100, 10], [100, 30], [10, 30]],
                ('mock文本', 0.97),
            ],
        ]]

        original_ensure = OcrEngine._ensure_loaded

        def fake_ensure(self):
            self._ocr = mock_instance

        OcrEngine._ensure_loaded = fake_ensure
        yield mock_instance
        OcrEngine._ensure_loaded = original_ensure

    def test_recognize_page(self, mock_paddleocr):
        """单页识别返回结构化结果。"""
        engine = OcrEngine()
        img = Image.new('RGB', (200, 100), color='white')

        result = engine.recognize_page(img)
        assert engine.is_loaded is True
        assert len(result) == 1
        assert result[0]['text'] == 'mock文本'
        assert result[0]['confidence'] == 0.97

    def test_recognize_batch(self, mock_paddleocr):
        """批量识别返回每页结果。"""
        engine = OcrEngine()
        images = [
            Image.new('RGB', (200, 100), color='white'),
            Image.new('RGB', (200, 100), color='white'),
        ]

        results = engine.recognize_batch(images)
        assert len(results) == 2
        assert all(len(r) == 1 for r in results)

    def test_recognize_batch_error_isolation(self, mock_paddleocr):
        """批量识别中某页失败不影响其他页（直接操作 _ocr mock 模拟异常）。"""
        engine = OcrEngine()

        # 第一页正常返回，第二页抛异常
        mock_paddleocr.ocr.side_effect = [
            # 第一页: 正常结果
            [[
                [
                    [[10, 10], [100, 10], [100, 30], [10, 30]],
                    ('第一页文本', 0.95),
                ],
            ]],
            # 第二页: 抛异常
            RuntimeError("模拟识别失败"),
        ]

        images = [
            Image.new('RGB', (200, 100), color='white'),
            Image.new('RGB', (200, 100), color='white'),
        ]

        results = engine.recognize_batch(images)
        assert len(results) == 2
        # 第一页正常
        assert results[0][0]['text'] == '第一页文本'
        # 第二页返回错误标记
        assert '识别失败' in results[1][0]['text']
        assert results[1][0]['confidence'] == 0.0

    def test_clear_cache(self, mock_paddleocr):
        """缓存清理不抛异常。"""
        engine = OcrEngine()
        engine._ocr = MagicMock()
        # 不应抛异常
        engine.clear_cache()
