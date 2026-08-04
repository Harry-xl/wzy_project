"""
断点续传管理器 —— OCR 进度持久化与恢复。

对于 400+ 页大文档，支持：
- 每页完成后原子写入进度文件
- 通过 PDF 指纹识别同一文档，防止混淆
- 启动时自动检测已有进度，提示用户选择继续/重新开始
- Ctrl+C 优雅退出后，已处理页面不丢失

进度文件格式 (.ocr_checkpoint.json):
{
    "version": 1,
    "pdf_path": "C:/.../教材.pdf",
    "pdf_hash": "a1b2c3d4...",
    "total_pages": 432,
    "processed_pages": [1, 2, 3, ...],
    "failed_pages": {"15": "识别失败: ..."},
    "last_page": 42,
    "created_at": "2026-08-03T10:00:00",
    "updated_at": "2026-08-03T10:15:30"
}
"""

import hashlib
import json
import logging
import os
import tempfile
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional, Set

logger = logging.getLogger(__name__)

CHECKPOINT_FILENAME = ".ocr_checkpoint.json"
CHECKPOINT_VERSION = 1


@dataclass
class Checkpoint:
    """OCR 处理进度快照。"""
    pdf_path: str
    pdf_hash: str
    total_pages: int
    processed_pages: Set[int] = field(default_factory=set)
    failed_pages: Dict[int, str] = field(default_factory=dict)
    last_page: int = 0
    version: int = CHECKPOINT_VERSION
    created_at: str = ""
    updated_at: str = ""

    def __post_init__(self):
        now = datetime.now().isoformat(timespec='seconds')
        if not self.created_at:
            self.created_at = now
        if not self.updated_at:
            self.updated_at = now

    @property
    def completed_count(self) -> int:
        """成功完成的页面数。"""
        return len(self.processed_pages - set(self.failed_pages.keys()))

    @property
    def failed_count(self) -> int:
        """失败的页面数。"""
        return len(self.failed_pages)

    @property
    def pending_count(self) -> int:
        """待处理的页面数。"""
        return self.total_pages - len(self.processed_pages)

    @property
    def progress_pct(self) -> float:
        """完成百分比。"""
        if self.total_pages == 0:
            return 100.0
        return round(len(self.processed_pages) / self.total_pages * 100, 1)

    def to_dict(self) -> dict:
        """转为可序列化的字典。"""
        return {
            'version': self.version,
            'pdf_path': self.pdf_path,
            'pdf_hash': self.pdf_hash,
            'total_pages': self.total_pages,
            'processed_pages': sorted(list(self.processed_pages)),
            'failed_pages': {str(k): v for k, v in self.failed_pages.items()},
            'last_page': self.last_page,
            'created_at': self.created_at,
            'updated_at': datetime.now().isoformat(timespec='seconds'),
        }

    @classmethod
    def from_dict(cls, data: dict) -> 'Checkpoint':
        """从字典恢复。兼容旧版本格式。"""
        processed = set(data.get('processed_pages', []))
        failed = {
            int(k): v
            for k, v in data.get('failed_pages', {}).items()
        }
        return cls(
            version=data.get('version', 1),
            pdf_path=data.get('pdf_path', ''),
            pdf_hash=data.get('pdf_hash', ''),
            total_pages=data.get('total_pages', 0),
            processed_pages=processed,
            failed_pages=failed,
            last_page=data.get('last_page', 0),
            created_at=data.get('created_at', ''),
            updated_at=data.get('updated_at', ''),
        )


class CheckpointManager:
    """管理 OCR 处理进度的持久化与恢复。

    用法:
        ckpt_mgr = CheckpointManager("教材.pdf", "./output")
        checkpoint = ckpt_mgr.load()      # 尝试加载上次进度
        ...
        ckpt_mgr.mark_done(42)           # 每页完成后标记
        ckpt_mgr.mark_failed(43, "识别失败")
    """

    def __init__(self, pdf_path: str, output_dir: str):
        """初始化断点管理器。

        Args:
            pdf_path: 源 PDF 文件路径（用于计算指纹）
            output_dir: 输出目录（进度文件存放于此）
        """
        self.pdf_path = str(Path(pdf_path).resolve())
        self.output_dir = str(Path(output_dir).resolve())
        self._checkpoint_path = os.path.join(self.output_dir, CHECKPOINT_FILENAME)
        self._current: Optional[Checkpoint] = None

        # 确保输出目录存在
        os.makedirs(self.output_dir, exist_ok=True)

    @property
    def current(self) -> Optional[Checkpoint]:
        """当前活跃的进度快照。"""
        return self._current

    def load(self) -> Optional[Checkpoint]:
        """尝试加载上次的进度文件。

        通过 PDF 指纹验证进度是否属于当前文件：
        - 匹配 → 返回 Checkpoint，调用方决定是否继续
        - 不匹配 → 返回 None（旧进度属于其他 PDF）

        Returns:
            Checkpoint 或 None
        """
        if not os.path.isfile(self._checkpoint_path):
            logger.debug("未找到进度文件，将从头开始")
            return None

        try:
            with open(self._checkpoint_path, 'r', encoding='utf-8') as f:
                data = json.load(f)

            checkpoint = Checkpoint.from_dict(data)

            # 验证 PDF 指纹
            current_hash = self.pdf_hash(self.pdf_path)
            if checkpoint.pdf_hash != current_hash:
                logger.warning(
                    f"进度文件与当前 PDF 不匹配（hash: {checkpoint.pdf_hash[:8]}... "
                    f"vs {current_hash[:8]}...），将忽略旧进度"
                )
                return None

            # 验证页数一致
            current_total = self._get_total_pages()
            if checkpoint.total_pages != current_total:
                logger.warning(
                    f"PDF 页数已变更（{checkpoint.total_pages} → {current_total}），"
                    f"将忽略旧进度"
                )
                return None

            self._current = checkpoint
            logger.info(
                f"已加载进度: {checkpoint.completed_count}/{checkpoint.total_pages} 页完成, "
                f"{checkpoint.failed_count} 页失败 "
                f"({checkpoint.progress_pct}%)"
            )
            return checkpoint

        except (json.JSONDecodeError, KeyError, TypeError) as e:
            logger.warning(f"进度文件损坏（{e}），将忽略并重新开始")
            return None

    def create(self, total_pages: int) -> Checkpoint:
        """创建新的进度记录。

        Args:
            total_pages: PDF 总页数
        """
        self._current = Checkpoint(
            pdf_path=self.pdf_path,
            pdf_hash=self.pdf_hash(self.pdf_path),
            total_pages=total_pages,
        )
        self._save()
        logger.info(f"已创建新进度: {total_pages} 页待处理")
        return self._current

    def mark_done(self, page_num: int):
        """标记一页处理完成，立即保存进度。

        Args:
            page_num: 页码（1-based）
        """
        if self._current is None:
            return

        self._current.processed_pages.add(page_num)
        self._current.last_page = page_num
        # 如果之前标记过失败，现在成功了就移除失败标记
        self._current.failed_pages.pop(page_num, None)
        self._save()

    def mark_failed(self, page_num: int, error: str):
        """标记一页处理失败，立即保存进度。

        Args:
            page_num: 页码（1-based）
            error: 错误描述
        """
        if self._current is None:
            return

        self._current.processed_pages.add(page_num)
        self._current.failed_pages[page_num] = error
        self._current.last_page = page_num
        self._save()

    def get_pending_pages(
        self, start_page: int = 1, end_page: Optional[int] = None
    ) -> list:
        """获取待处理的页码列表。

        Args:
            start_page: 起始页码
            end_page: 结束页码（None 表示最后一页）

        Returns:
            待处理的页码列表（已排除 checkpoin͏t 中已完成的页）
        """
        if self._current is None:
            total = self._get_total_pages()
        else:
            total = self._current.total_pages

        if end_page is None or end_page < 0:
            end_page = total

        # 生成范围内所有页码
        all_pages = list(range(start_page, min(end_page, total) + 1))

        # 排除已处理的
        if self._current is not None:
            return [
                p for p in all_pages
                if p not in self._current.processed_pages
            ]

        return all_pages

    def clear(self):
        """删除进度文件，重新开始。"""
        if os.path.isfile(self._checkpoint_path):
            os.remove(self._checkpoint_path)
            logger.info("已清除旧进度文件")
        self._current = None

    def print_summary(self):
        """打印处理摘要。"""
        if self._current is None:
            return

        c = self._current
        logger.info("=" * 50)
        logger.info("处理摘要:")
        logger.info(f"  总页数: {c.total_pages}")
        logger.info(f"  已完成: {c.completed_count} 页")
        logger.info(f"  失败:   {c.failed_count} 页")
        logger.info(f"  进度:   {c.progress_pct}%")
        if c.failed_pages:
            logger.info(f"  失败页码: {sorted(c.failed_pages.keys())}")
        logger.info("=" * 50)

    # --- 内部方法 ---

    def _save(self):
        """原子写入进度文件（先写临时文件再 rename，防止写入中途崩溃损坏）。"""
        if self._current is None:
            return

        data = self._current.to_dict()
        json_str = json.dumps(data, ensure_ascii=False, indent=2)

        # 原子写入
        try:
            fd, tmp_path = tempfile.mkstemp(
                suffix='.tmp',
                prefix='.ocr_checkpoint_',
                dir=self.output_dir,
            )
            with os.fdopen(fd, 'w', encoding='utf-8') as f:
                f.write(json_str)

            os.replace(tmp_path, self._checkpoint_path)

        except OSError as e:
            logger.error(f"保存进度文件失败: {e}")

    def _get_total_pages(self) -> int:
        """获取 PDF 总页数（不依赖 Checkpoint）。"""
        try:
            import fitz
            doc = fitz.open(self.pdf_path)
            count = len(doc)
            doc.close()
            return count
        except Exception:
            return 0

    @staticmethod
    def pdf_hash(path: str) -> str:
        """计算 PDF 指纹（前 64KB 的 MD5 + 文件大小）。

        用于唯一标识一个 PDF 文件，防止不同 PDF 的进度混淆。

        Args:
            path: PDF 文件路径

        Returns:
            16 进制 hash 字符串
        """
        file_size = os.path.getsize(path)
        md5 = hashlib.md5()

        with open(path, 'rb') as f:
            # 读取前 64KB
            md5.update(f.read(65536))

        # 混入文件大小
        md5.update(str(file_size).encode())

        return md5.hexdigest()


# --- 模块自测 (python checkpoint.py) ---
if __name__ == "__main__":
    import sys
    import tempfile
    import shutil

    # 使用 reportlab 生成真实测试 PDF
    from reportlab.pdfgen import canvas
    from reportlab.lib.pagesizes import A4

    tmp_dir = tempfile.mkdtemp()
    real_pdf = os.path.join(tmp_dir, "test.pdf")
    c = canvas.Canvas(real_pdf, pagesize=A4)
    for i in range(10):  # 生成10页PDF，匹配 checkpoint 测试数据
        c.drawString(100, 700, f"Test Page {i+1}")
        c.showPage()
    c.save()

    output_dir = os.path.join(tmp_dir, "output")
    os.makedirs(output_dir, exist_ok=True)

    # 测试 1: 创建和保存
    print("=== Test 1: Create & Save ===")
    mgr = CheckpointManager(real_pdf, output_dir)
    mgr.create(total_pages=10)

    mgr.mark_done(1)
    mgr.mark_done(2)
    mgr.mark_failed(3, "mock error")
    mgr.mark_done(4)

    print(f"Done: {mgr.current.completed_count}, Failed: {mgr.current.failed_count}")
    assert mgr.current.completed_count == 3  # 1,2,4
    assert mgr.current.failed_count == 1     # 3

    # 测试 2: 重新加载
    print("\n=== Test 2: Reload ===")
    mgr2 = CheckpointManager(real_pdf, output_dir)
    loaded = mgr2.load()
    assert loaded is not None
    assert loaded.completed_count == 3
    print(f"Loaded: {loaded.completed_count} pages done")

    # 测试 3: 获取待处理页
    print("\n=== Test 3: Pending Pages ===")
    pending = mgr2.get_pending_pages(start_page=1, end_page=5)
    assert pending == [5]  # 1,2,3,4 done
    print(f"Pending: {pending}")

    # 测试 4: 清除
    print("\n=== Test 4: Clear ===")
    mgr2.clear()
    assert mgr2.load() is None
    print("Cleared")

    # 清理
    shutil.rmtree(tmp_dir, ignore_errors=True)
    print("\n[OK] CheckpointManager self-test passed")
