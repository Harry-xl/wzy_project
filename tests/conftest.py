"""
pytest 全局配置和 fixtures

使用方法:
    python -m pytest tests/ -v
    python -m pytest tests/ --cov=. --cov-report=term
"""

import os
import sys
import pytest

# 确保项目根目录在 Python 路径中
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)


@pytest.fixture(scope="session")
def app():
    """创建测试用 Flask 应用。

    使用测试配置（独立数据库 wzyProjectDb_test，关闭清理线程）。
    """
    # TODO: Stage 4 重构后改为:
    # from src.server import create_app
    # app = create_app(config='testing')
    # return app

    # 当前（重构前）:
    import server.app as app_module

    # 覆盖为测试配置
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
