"""
认证 API 集成测试

测试范围:
- POST /api/signup — 用户注册
- POST /api/login — 用户登录
"""

import pytest


class TestSignup:
    """用户注册测试"""

    def test_signup_success(self, client, sample_user):
        """正常注册新用户"""
        response = client.post(
            "/api/signup",
            json=sample_user,
        )
        data = response.get_json()

        assert response.status_code == 200
        assert data["success"] is True

    def test_signup_duplicate_email(self, client, sample_user):
        """重复邮箱注册应返回失败"""
        # 第一次注册
        client.post("/api/signup", json=sample_user)
        # 第二次注册（重复）
        response = client.post("/api/signup", json=sample_user)
        data = response.get_json()

        assert response.status_code == 200
        assert data["success"] is False
        assert "message" in data

    def test_signup_missing_fields(self, client):
        """缺少必填字段应返回 400"""
        response = client.post("/api/signup", json={})
        assert response.status_code == 400

        response = client.post("/api/signup", json={"name": "test"})
        assert response.status_code == 400

    def test_signup_empty_name(self, client):
        """空昵称应被拒绝"""
        response = client.post(
            "/api/signup",
            json={
                "name": "",
                "email": "test@example.com",
                "password": "123456",
            },
        )
        assert response.status_code == 400

    def test_signup_invalid_email(self, client):
        """无效邮箱格式应被拒绝"""
        response = client.post(
            "/api/signup",
            json={
                "name": "test",
                "email": "not-an-email",
                "password": "123456",
            },
        )
        assert response.status_code == 400


class TestLogin:
    """用户登录测试"""

    @pytest.fixture(autouse=True)
    def register_user(self, client, sample_user):
        """每个测试前注册一个测试用户"""
        client.post("/api/signup", json=sample_user)

    def test_login_success(self, client, sample_user):
        """正确凭据登录成功"""
        response = client.post(
            "/api/login",
            json={
                "email": sample_user["email"],
                "password": sample_user["password"],
            },
        )
        data = response.get_json()

        assert response.status_code == 200
        assert data["success"] is True
        assert "user_id" in data
        assert data["name"] == sample_user["name"]

    def test_login_wrong_password(self, client, sample_user):
        """错误密码登录失败"""
        response = client.post(
            "/api/login",
            json={
                "email": sample_user["email"],
                "password": "wrong_password",
            },
        )
        data = response.get_json()

        assert response.status_code == 200
        assert data["success"] is False

    def test_login_nonexistent_user(self, client):
        """不存在的用户登录失败"""
        response = client.post(
            "/api/login",
            json={
                "email": "nonexistent@example.com",
                "password": "123456",
            },
        )
        data = response.get_json()

        assert response.status_code == 200
        assert data["success"] is False

    def test_login_missing_fields(self, client):
        """缺少必填字段"""
        response = client.post("/api/login", json={})
        assert response.status_code == 400
