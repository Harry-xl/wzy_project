"""
学习卡片服务单元测试

仅测试 LearningCardService 的核心逻辑（不依赖 MySQL/Flask test client）。
Mock: get_connection 在 lazy import 之前 patch。
"""

import json
import sys
import os
from unittest.mock import MagicMock, patch

import pytest

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, PROJECT_ROOT)


def _mock_conn(fetchone_seq=None, fetchall_returns=None, rowcount=0):
    """创建 mock MySQL 连接 (conn + cursor)。"""
    cursor = MagicMock()
    cursor.__enter__ = MagicMock(return_value=cursor)
    cursor.__exit__ = MagicMock(return_value=False)
    if fetchone_seq:
        cursor.fetchone = MagicMock(side_effect=fetchone_seq)
    else:
        cursor.fetchone = MagicMock(return_value=None)
    cursor.fetchall = MagicMock(return_value=fetchall_returns or [])
    cursor.rowcount = rowcount
    conn = MagicMock()
    conn.cursor.return_value = cursor
    return conn, cursor


@pytest.fixture
def sample_topic():
    return {
        "sub_topic_id": 10, "sub_topic_name": "三次握手",
        "parent_kp": "TCP连接管理",
        "description": "TCP连接建立的三次握手过程。",
    }


@pytest.fixture
def cached_card():
    return {
        "sub_topic_id": 10, "sub_topic_name": "三次握手",
        "parent_kp": "TCP连接管理",
        "slim_content": "【定义】\n三次握手。\n【核心要点】\n- SYN\n- ACK",
        "full_content": None,
        "source_doc_ids": json.dumps([1, 2]),
        "is_regenerating": 0,
        "generated_at": "2026-08-07 12:00:00",
    }


def _mock_ai_response():
    return (
        "【定义】\nTCP三次握手是建立可靠连接的过程。\n\n"
        "【核心要点】\n- SYN\n- SYN-ACK\n- ACK\n"
        "【来源】\n- 计算机网络(第8版)"
    )


# ================================================================
# get_card tests
# ================================================================


class TestGetCard:

    def test_cache_hit(self, cached_card):
        conn, _ = _mock_conn(fetchone_seq=[cached_card])
        with patch("database.db_connector.get_connection", return_value=conn):
            from server.learning_card_service import LearningCardService
            svc = LearningCardService()
            card = svc.get_card(sub_topic_id=10, user_id=1)
        assert card["from_cache"] is True
        assert card["sub_topic_name"] == "三次握手"

    def test_topic_not_found(self):
        conn, _ = _mock_conn(fetchone_seq=[None])
        with patch("database.db_connector.get_connection", return_value=conn):
            from server.learning_card_service import LearningCardService
            svc = LearningCardService()
            card = svc.get_card(sub_topic_id=999, user_id=None)
        assert "error" in card

    def test_cache_miss_generates_slim(self, sample_topic):
        conn, _ = _mock_conn(fetchone_seq=[None, sample_topic])

        # Mock DeepSeek
        from AI_operate.deepseek_chat import deepseek_chat as dc
        with patch.object(dc, "chat_with_deepseek", return_value=_mock_ai_response()):
            with patch("database.db_connector.get_connection", return_value=conn):
                from server.learning_card_service import LearningCardService
                svc = LearningCardService()
                card = svc.get_card(sub_topic_id=10, user_id=None)

        assert card["from_cache"] is False
        assert "TCP三次握手" in card["slim_content"]
        assert card["full_content"] is None

    def test_regenerating_triggers_refresh(self, cached_card, sample_topic):
        regen = dict(cached_card)
        regen["is_regenerating"] = 1
        conn, _ = _mock_conn(fetchone_seq=[regen, sample_topic])

        from AI_operate.deepseek_chat import deepseek_chat as dc
        with patch.object(dc, "chat_with_deepseek", return_value=_mock_ai_response()):
            with patch("database.db_connector.get_connection", return_value=conn):
                from server.learning_card_service import LearningCardService
                svc = LearningCardService()
                card = svc.get_card(sub_topic_id=10, user_id=1)
        assert card["from_cache"] is False


# ================================================================
# SSE stream tests
# ================================================================


class TestFullCardStream:

    def test_topic_not_found_streams_error(self):
        conn, _ = _mock_conn(fetchone_seq=[None])
        with patch("database.db_connector.get_connection", return_value=conn):
            from server.learning_card_service import LearningCardService
            svc = LearningCardService()
            chunks = list(svc.generate_full_card_stream(sub_topic_id=999, user_id=None))
        assert any("error" in c for c in chunks)
        assert 'data: [DONE]\n\n' in chunks

    def test_cached_full_returned_immediately(self, cached_card):
        """完整版已缓存时直接序列化返回。"""
        full = dict(cached_card)
        full["full_content"] = "完整讲解..."

        # Mock get_card 返回有完整内容的卡片
        card_result = {
            "sub_topic_id": 10, "sub_topic_name": "三次握手",
            "parent_kp": "TCP连接管理",
            "slim_content": "精简版...",
            "full_content": "完整讲解...",
            "source_doc_ids": [1, 2],
            "is_regenerating": False, "from_cache": True,
        }

        from server.learning_card_service import LearningCardService
        with patch.object(LearningCardService, "get_card", return_value=card_result):
            svc = LearningCardService()
            chunks = list(svc.generate_full_card_stream(sub_topic_id=10, user_id=1))
        assert any('"cached": true' in c for c in chunks)

    def test_streaming_generation(self):
        """SSE 流式生成完整版内容。"""
        # Mock get_card → 返回卡片（无 full_content）
        card_result = {
            "sub_topic_id": 10, "sub_topic_name": "三次握手",
            "parent_kp": "TCP连接管理",
            "slim_content": "精简版...",
            "full_content": None,  # 没有完整版
            "source_doc_ids": [],
            "is_regenerating": False, "from_cache": True,
        }

        ai_chunks = ["【详细讲解】\n", "TCP协议是面向连接的..."]

        from server.learning_card_service import LearningCardService
        with patch.object(LearningCardService, "get_card", return_value=card_result):
            with patch.object(LearningCardService, "_get_topic_info", return_value={"sub_topic_id": 10, "sub_topic_name": "三次握手", "parent_kp": "TCP连接管理", "description": "desc"}):
                with patch.object(LearningCardService, "_collect_source_content", return_value={"text": "test", "doc_ids": [], "doc_names": [], "problem_nums": []}):
                    with patch.object(LearningCardService, "_set_regenerating"):
                        with patch.object(LearningCardService, "_save_full_content"):
                            # 必须 patch learning_card_service 模块内的 deepseek_chat 引用
                            with patch("server.learning_card_service.deepseek_chat.chat_with_deepseek_stream", return_value=iter(ai_chunks)):
                                svc = LearningCardService()
                                chunks = list(svc.generate_full_card_stream(sub_topic_id=10, user_id=1))
        assert any("TCP协议是面向连接的" in c for c in chunks)
        assert 'data: [DONE]\n\n' in chunks


# ================================================================
# Card invalidation tests
# ================================================================


class TestCardInvalidation:

    def test_invalidate_by_document(self):
        conn, _ = _mock_conn(fetchall_returns=[(5,), (10,)], rowcount=1)
        with patch("database.db_connector.get_connection", return_value=conn):
            from server.learning_card_service import LearningCardService
            svc = LearningCardService()
            count = svc.invalidate_cards_for_document(doc_id=1)
        assert count >= 0

    def test_invalidate_by_sub_topic(self):
        conn, _ = _mock_conn()
        with patch("database.db_connector.get_connection", return_value=conn):
            from server.learning_card_service import LearningCardService
            svc = LearningCardService()
            result = svc.invalidate_cards_for_sub_topic(sub_topic_id=10)
        assert result is True

    def test_invalidate_no_topics(self):
        conn, _ = _mock_conn(fetchall_returns=[])
        with patch("database.db_connector.get_connection", return_value=conn):
            from server.learning_card_service import LearningCardService
            svc = LearningCardService()
            count = svc.invalidate_cards_for_document(doc_id=1)
        assert count == 0


# ================================================================
# Fallback content tests
# ================================================================


class TestFallbackSlim:

    def test_fallback_contains_sections(self, sample_topic):
        conn, _ = _mock_conn()
        with patch("database.db_connector.get_connection", return_value=conn):
            from server.learning_card_service import LearningCardService
            svc = LearningCardService()
        sources = {"text": "", "doc_ids": [], "doc_names": [], "problem_nums": []}
        content = svc._fallback_slim(sample_topic, sources)
        assert "【定义】" in content
        assert sample_topic["parent_kp"] in content
        assert "【核心要点】" in content

    def test_fallback_includes_doc_names(self, sample_topic):
        conn, _ = _mock_conn()
        with patch("database.db_connector.get_connection", return_value=conn):
            from server.learning_card_service import LearningCardService
            svc = LearningCardService()
        sources = {
            "text": "x", "doc_ids": [1], "doc_names": ["计算机网络"],
            "problem_nums": [],
        }
        content = svc._fallback_slim(sample_topic, sources)
        assert "计算机网络" in content


# ================================================================
# Service init
# ================================================================


class TestServiceInit:

    def test_instantiate(self):
        conn, _ = _mock_conn()
        with patch("database.db_connector.get_connection", return_value=conn):
            from server.learning_card_service import LearningCardService
            svc = LearningCardService()
            assert hasattr(svc, 'get_card')
            assert hasattr(svc, 'generate_full_card_stream')
            assert hasattr(svc, 'invalidate_cards_for_document')