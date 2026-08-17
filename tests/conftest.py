"""
pytest 全局配置和 fixtures

使用方法:
    python -m pytest tests/ -v
    python -m pytest tests/ --cov=. --cov-report=term
"""

import os
import sys
from unittest.mock import MagicMock

import pytest

# 确保项目根目录在 Python 路径中
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

# ================================================================
# 模块级预处理：在任何项目模块导入前 mock MySQL 连接池
# ================================================================

# ================================================================
# 模块级预处理：在任何项目模块导入前 mock MySQL 连接池
# ================================================================


def pytest_configure(config):
    """pytest 启动时立即执行，在任何测试模块加载前 mock MySQL 连接池。"""
    try:
        import mysql.connector.pooling
        mock_pool = MagicMock()
        mock_pool.get_connection = MagicMock()
        mysql.connector.pooling.MySQLConnectionPool = MagicMock(return_value=mock_pool)
    except ImportError:
        pass  # mysql-connector 未安装时跳过


# ================================================================
# Fixtures
# ================================================================


@pytest.fixture(scope="session")
def app():
    """创建测试用 Flask 应用。

    使用测试配置（独立数据库 wzyProjectDb_test，关闭清理线程）。
    """
    import server.app as app_module

    app_module.app.config["TESTING"] = True
    return app_module.app


@pytest.fixture
def client(app):
    """Flask 测试客户端"""
    return app.test_client()


@pytest.fixture
def sample_user():
    """标准测试用户数据"""
    return {
        "name": "测试学生",
        "email": "test_student@example.com",
        "password": "test123456",
    }


@pytest.fixture
def sample_problem():
    """标准测试题目数据"""
    return {
        "problem_num": "TEST-001",
        "problem": "测试题目：TCP 三次握手的第一步是什么？",
        "answer": "客户端发送 SYN",
        "difficulty": "简单",
        "knowledge_point": "TCP 协议",
    }


@pytest.fixture
def sample_problems():
    """批量测试题目数据"""
    return [
        {
            "problem_num": "TEST-001",
            "problem": "TCP 三次握手的第一步是什么？",
            "answer": "客户端发送 SYN",
            "difficulty": "简单",
            "knowledge_point": "TCP 协议",
        },
        {
            "problem_num": "TEST-002",
            "problem": "UDP 与 TCP 的主要区别是什么？",
            "answer": "UDP 无连接，TCP 面向连接",
            "difficulty": "中等",
            "knowledge_point": "传输层协议",
        },
        {
            "problem_num": "TEST-003",
            "problem": "BGP 运行在 OSI 模型的第几层？",
            "answer": "应用层",
            "difficulty": "困难",
            "knowledge_point": "路由协议",
        },
    ]