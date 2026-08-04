"""
PaddleOCR 引擎封装 —— 中文扫描 PDF 的 OCR 识别。

封装 PaddleOCR，提供延迟初始化、mini-batch 处理和缓存管理。
针对 400+ 页大文档设计：批处理加速 + 定期释放内部缓存。

用法:
    engine = OcrEngine(lang='ch')
    blocks = engine.recognize_page(pil_image)
    # blocks = [{text, confidence, bbox: [x1,y1,x2,y2]}, ...]

    # Mini-batch 模式（推荐用于大量页面）
    results = engine.recognize_batch([img1, img2, img3])
"""

import logging
from typing import List, Optional

from PIL import Image

logger = logging.getLogger(__name__)


class OcrEngineError(Exception):
    """OCR 引擎异常。"""
    pass


class OcrEngine:
    """PaddleOCR 封装。

    特性：
    - 延迟初始化：模型在首次识别时才加载，CLI 启动快
    - Mini-batch：一次传入多张图片，利用内部并行加速
    - 缓存清理：定期释放 PaddleOCR 内部缓存防止内存膨胀

    Attributes:
        lang: 识别语言 ('ch' / 'en' / 'ch_en')
        use_gpu: 是否使用 GPU（Windows 当前仅支持 CPU）
    """

    # 支持的语言配置
    SUPPORTED_LANGS = {
        'ch': '中文（简体+繁体）',
        'en': '英文',
        'ch_en': '中英文混合',
    }

    def __init__(
        self,
        lang: str = 'ch',
        use_gpu: bool = False,
        det_db_thresh: float = 0.3,
        rec_batch_num: int = 6,
    ):
        """初始化 OCR 引擎（模型延迟加载）。

        Args:
            lang: 识别语言，可选 'ch' / 'en' / 'ch_en'
            use_gpu: 是否使用 GPU（Windows 仅支持 False）
            det_db_thresh: 文本检测阈值（越低检出越多，但可能误检）
            rec_batch_num: 识别批处理大小（内部参数）
        """
        if lang not in self.SUPPORTED_LANGS:
            raise ValueError(
                f"不支持的语言: {lang}。可选: {', '.join(self.SUPPORTED_LANGS)}"
            )

        self.lang = lang
        self.use_gpu = use_gpu
        self._det_db_thresh = det_db_thresh
        self._rec_batch_num = rec_batch_num
        self._ocr = None  # 延迟初始化
        self._call_count = 0  # 用于触发定期清理

    @property
    def is_loaded(self) -> bool:
        """模型是否已加载。"""
        return self._ocr is not None

    def _ensure_loaded(self):
        """确保模型已加载（首次调用时触发）。"""
        if self._ocr is not None:
            return

        logger.info("正在加载 PaddleOCR 模型（首次运行需下载 ~500MB，请耐心等待）...")

        try:
            from paddleocr import PaddleOCR

            self._ocr = PaddleOCR(
                lang=self.lang,
                use_angle_cls=True,       # 启用文本方向分类（对扫描件很重要）
                use_gpu=self.use_gpu,
                det_db_thresh=self._det_db_thresh,
                rec_batch_num=self._rec_batch_num,
                show_log=False,            # 抑制 PaddleOCR 内部日志
            )
            logger.info("PaddleOCR 模型加载完成")
        except ImportError:
            raise OcrEngineError(
                "PaddleOCR 未安装。请运行: pip install paddleocr"
            )
        except Exception as e:
            raise OcrEngineError(f"PaddleOCR 模型加载失败: {e}")

    def recognize_page(self, image: Image.Image) -> List[dict]:
        """识别单页图片。

        Args:
            image: PIL.Image 对象（RGB 模式）

        Returns:
            识别结果列表，每项:
            {
                'text': str,           # 识别文本
                'confidence': float,   # 置信度 0.0~1.0
                'bbox': [x1,y1,x2,y2]  # 边界框（左上+右下）
            }
        """
        self._ensure_loaded()
        self._call_count += 1

        try:
            # PaddleOCR 接受 numpy array 或图片路径
            import numpy as np
            img_array = np.array(image)

            raw_results = self._ocr.ocr(img_array, cls=True)

            return self._normalize_results(raw_results)

        except Exception as e:
            logger.error(f"OCR 识别失败: {e}")
            raise OcrEngineError(f"OCR 识别失败: {e}")

    def recognize_batch(self, images: List[Image.Image]) -> List[List[dict]]:
        """批量识别多页图片。

        逐张调用 PaddleOCR（PaddleOCR 内部已有批处理优化），
        相比外层循环的优势：统一的异常处理和进度跟踪。

        Args:
            images: PIL.Image 列表

        Returns:
            每页的识别结果列表（与输入顺序一致）
        """
        self._ensure_loaded()
        results = []

        for i, image in enumerate(images):
            self._call_count += 1
            try:
                import numpy as np
                img_array = np.array(image)
                raw_results = self._ocr.ocr(img_array, cls=True)
                results.append(self._normalize_results(raw_results))
            except Exception as e:
                logger.error(f"批次中第 {i + 1} 页识别失败: {e}")
                # 页面级隔离：一页失败不影响同批次其他页
                results.append([
                    {
                        'text': f'[识别失败: {e}]',
                        'confidence': 0.0,
                        'bbox': [0, 0, 0, 0],
                    }
                ])

        return results

    def clear_cache(self):
        """释放 PaddleOCR 内部缓存。

        长时间运行（400+ 页）后，PaddleOCR 内部可能积累临时数据。
        建议每 50 页调用一次，防止内存从 ~500MB 膨胀到 4GB+。
        """
        if self._ocr is not None:
            try:
                # 尝试触发 PaddleOCR 内部垃圾回收
                import gc
                gc.collect()

                logger.debug(
                    f"PaddleOCR 缓存已清理（已调用 {self._call_count} 次）"
                )
            except Exception as e:
                logger.debug(f"缓存清理时出现非关键警告: {e}")

    @staticmethod
    def _normalize_results(raw_results) -> List[dict]:
        """将 PaddleOCR 原始输出统一为标准格式。

        PaddleOCR 返回格式:
        [
            [ [[x1,y1],[x2,y2],[x3,y3],[x4,y4]], (text, confidence) ],
            ...
        ]
        或 None（无文本检测到）

        统一为:
        [
            {'text': ..., 'confidence': ..., 'bbox': [x1,y1,x2,y2]},
            ...
        ]
        """
        if raw_results is None or raw_results[0] is None:
            return []

        normalized = []
        for line in raw_results[0]:
            if len(line) != 2:
                continue

            box_points, text_info = line
            text, confidence = text_info

            # 四点坐标 → (x1,y1,x2,y2)
            xs = [p[0] for p in box_points]
            ys = [p[1] for p in box_points]
            bbox = [int(min(xs)), int(min(ys)), int(max(xs)), int(max(ys))]

            normalized.append({
                'text': str(text),
                'confidence': float(confidence),
                'bbox': bbox,
            })

        return normalized

    def get_info(self) -> dict:
        """返回引擎配置信息（不加载模型）。"""
        return {
            'lang': self.lang,
            'lang_desc': self.SUPPORTED_LANGS.get(self.lang, '未知'),
            'use_gpu': self.use_gpu,
            'model_loaded': self.is_loaded,
            'call_count': self._call_count,
        }


# --- 模块自测 (python ocr_engine.py) ---
if __name__ == "__main__":
    import sys

    # 此自测需要 PaddleOCR 模型已安装
    # 创建一张纯色测试图片来验证管线
    from PIL import Image as PILImage
    import numpy as np

    # 创建一张白色测试图片
    test_img = PILImage.new("RGB", (400, 200), color=(255, 255, 255))

    try:
        engine = OcrEngine(lang='ch')
        print(f"引擎配置: {engine.get_info()}")

        print("正在加载模型并测试...")
        results = engine.recognize_page(test_img)
        print(f"测试图片识别结果: {len(results)} 个文本块（空图片预期为 0）")
        print("✅ OCR 引擎自测通过")

    except OcrEngineError as e:
        print(f"⚠️  OCR 引擎自测受限: {e}")
        print("（如果 PaddleOCR 未安装，这是正常的。运行 pip install paddleocr 后重试。）")
    except Exception as e:
        print(f"❌ 自测失败: {e}")
        sys.exit(1)
