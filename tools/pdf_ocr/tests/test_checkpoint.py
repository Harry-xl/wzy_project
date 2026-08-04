"""
测试 checkpoint.py — 断点续传管理器。
"""

import json
import os

import pytest

from checkpoint import Checkpoint, CheckpointManager, CHECKPOINT_FILENAME


class TestCheckpoint:
    """测试 Checkpoint 数据类。"""

    def test_create_new(self):
        """创建新的 Checkpoint。"""
        c = Checkpoint(
            pdf_path="/test/test.pdf",
            pdf_hash="abc123",
            total_pages=100,
        )
        assert c.total_pages == 100
        assert c.completed_count == 0
        assert c.failed_count == 0
        assert c.pending_count == 100
        assert c.progress_pct == 0.0

    def test_progress_calculation(self):
        """进度计算正确。"""
        c = Checkpoint(
            pdf_path="/test/test.pdf",
            pdf_hash="abc",
            total_pages=100,
            processed_pages=set(range(1, 51)),  # 50 pages
        )
        assert c.completed_count == 50
        assert c.progress_pct == 50.0

    def test_failed_pages_separate_tracking(self):
        """失败页面单独跟踪，不影响成功计数。"""
        c = Checkpoint(
            pdf_path="/test/test.pdf",
            pdf_hash="abc",
            total_pages=10,
            processed_pages={1, 2, 3, 4, 5},
            failed_pages={3: 'error', 5: 'error2'},
        )
        assert c.completed_count == 3  # 5 total - 2 failed
        assert c.failed_count == 2

    def test_to_dict_and_back(self):
        """序列化往返一致性。"""
        c = Checkpoint(
            pdf_path="/test/test.pdf",
            pdf_hash="abc123",
            total_pages=100,
            processed_pages={1, 2, 3},
            failed_pages={3: 'test error'},
            last_page=3,
        )

        data = c.to_dict()
        # 验证 JSON 可序列化
        json_str = json.dumps(data, ensure_ascii=False)
        restored_data = json.loads(json_str)
        restored = Checkpoint.from_dict(restored_data)

        assert restored.pdf_path == c.pdf_path
        assert restored.pdf_hash == c.pdf_hash
        assert restored.total_pages == c.total_pages
        assert restored.processed_pages == c.processed_pages
        assert restored.failed_pages == c.failed_pages

    def test_empty_checkpoint(self):
        """空 checkpoint 序列化。"""
        c = Checkpoint(pdf_path="", pdf_hash="", total_pages=0)
        data = c.to_dict()
        restored = Checkpoint.from_dict(data)
        assert restored.total_pages == 0
        assert restored.processed_pages == set()


class TestCheckpointManager:
    """测试 CheckpointManager 持久化功能。"""

    @pytest.fixture
    def manager(self, test_pdf_path, tmp_path):
        """创建 CheckpointManager（使用真实测试 PDF）。"""
        output_dir = str(tmp_path / "output")
        return CheckpointManager(test_pdf_path, output_dir)

    def test_create_and_save(self, manager):
        """创建进度并保存到文件。"""
        checkpoint = manager.create(total_pages=3)
        assert checkpoint.total_pages == 3
        assert os.path.exists(manager._checkpoint_path)

    def test_mark_done(self, manager):
        """标记页面完成。"""
        manager.create(total_pages=3)
        manager.mark_done(1)
        manager.mark_done(2)

        assert manager.current.completed_count == 2
        assert 1 in manager.current.processed_pages
        assert 2 in manager.current.processed_pages

    def test_mark_failed(self, manager):
        """标记页面失败。"""
        manager.create(total_pages=3)
        manager.mark_failed(1, "测试错误")

        assert manager.current.failed_count == 1
        assert manager.current.completed_count == 0
        assert manager.current.failed_pages[1] == "测试错误"

    def test_mark_done_clears_failed(self, manager):
        """成功后清除失败标记。"""
        manager.create(total_pages=3)
        manager.mark_failed(1, "临时错误")
        manager.mark_done(1)  # 重试成功

        assert manager.current.failed_count == 0
        assert manager.current.completed_count == 1

    def test_load_and_resume(self, manager):
        """保存后重新加载。"""
        manager.create(total_pages=3)
        manager.mark_done(1)
        manager.mark_failed(2, "错误")
        manager.mark_done(3)

        # 新 manager 重新加载
        manager2 = CheckpointManager(manager.pdf_path, manager.output_dir)
        loaded = manager2.load()

        assert loaded is not None
        assert loaded.completed_count == 2  # 1,3 成功
        assert loaded.failed_count == 1     # 2 失败

    def test_get_pending_pages(self, manager):
        """获取待处理页面（排除已完成）。"""
        manager.create(total_pages=10)
        manager.mark_done(1)
        manager.mark_done(2)
        manager.mark_failed(3, "err")

        pending = manager.get_pending_pages(start_page=1, end_page=5)
        assert pending == [4, 5]  # 1,2,3 已处理，4,5 待处理

    def test_get_pending_pages_all(self, manager):
        """无 checkpoint 时返回全部页面（限制在 PDF 总页数内）。"""
        pending = manager.get_pending_pages(start_page=1, end_page=5)
        # PDF 只有 3 页，所以返回 [1, 2, 3]
        assert pending == [1, 2, 3]

    def test_clear(self, manager):
        """清除进度文件。"""
        manager.create(total_pages=3)
        assert os.path.exists(manager._checkpoint_path)

        manager.clear()
        assert not os.path.exists(manager._checkpoint_path)
        assert manager.current is None

    def test_pdf_hash(self, test_pdf_path):
        """PDF 指纹计算。"""
        h = CheckpointManager.pdf_hash(test_pdf_path)
        assert isinstance(h, str)
        assert len(h) == 32  # MD5 hex

    def test_pdf_hash_different_for_different_files(self, test_pdf_path, test_pdf_10p):
        """不同 PDF 有不同的指纹。"""
        h1 = CheckpointManager.pdf_hash(test_pdf_path)
        h2 = CheckpointManager.pdf_hash(test_pdf_10p)
        assert h1 != h2
