"""Tests for auth API endpoints."""

from typing import Any

import pytest
from httpx import ASGITransport, AsyncClient

from app.api.v1.dependencies.auth import get_auth_service
from app.main import app
from app.services import auth_service as auth_module
from app.services.auth_service import AuthService

pytestmark = pytest.mark.asyncio

PASSWORD = "StrongPass123!"


@pytest.fixture(autouse=True)
def fast_password_hashing(monkeypatch: pytest.MonkeyPatch) -> None:
    """Patch bcrypt helpers to keep endpoint tests fast."""

    def fake_hash(password: str) -> str:
        return f"hashed:{password}"

    def fake_verify(password: str, hashed_password: str) -> bool:
        return hashed_password == f"hashed:{password}"

    monkeypatch.setattr(auth_module, "get_password_hash", fake_hash)
    monkeypatch.setattr(auth_module, "verify_password", fake_verify)


@pytest.fixture(autouse=True)
def auth_override(fake_user_repository: Any, mock_redis: Any) -> None:
    """Override AuthService dependency with fake dependencies."""
    service = AuthService(fake_user_repository, mock_redis)
    app.dependency_overrides[get_auth_service] = lambda: service
    app.state.limiter.reset()
    yield
    app.dependency_overrides.clear()
    app.state.limiter.reset()


def register_payload(
    email: str | None = "user@example.com",
    password: str = PASSWORD,
    phone: str = "0901234567",
) -> dict[str, str]:
    payload = {
        "password": password,
        "full_name": "Nguyen Van A",
        "phone": phone,
    }
    if email is not None:
        payload["email"] = email
    return payload


async def test_register_endpoint_returns_201(test_client: AsyncClient) -> None:
    response = await test_client.post("/api/v1/auth/register", json=register_payload())

    assert response.status_code == 201
    assert response.json()["email"] == "user@example.com"
    assert "hashed_password" not in response.text


async def test_register_with_duplicate_email_returns_409(test_client: AsyncClient) -> None:
    await test_client.post("/api/v1/auth/register", json=register_payload())

    # Same email, different phone: only the email collision should be reported.
    response = await test_client.post(
        "/api/v1/auth/register",
        json=register_payload("USER@example.com", phone="0907654321"),
    )

    assert response.status_code == 409
    assert response.json()["error_code"] == "email_already_exists"
    assert response.json()["detail"] == "Email này đã được sử dụng."


async def test_register_with_duplicate_phone_returns_409(test_client: AsyncClient) -> None:
    await test_client.post("/api/v1/auth/register", json=register_payload())

    # Same phone, different email: the phone collision wins.
    response = await test_client.post(
        "/api/v1/auth/register",
        json=register_payload("other@example.com"),
    )

    assert response.status_code == 409
    assert response.json()["error_code"] == "phone_already_exists"
    assert response.json()["detail"] == "Số điện thoại đã được đăng ký."


async def test_register_without_email_returns_201(test_client: AsyncClient) -> None:
    response = await test_client.post("/api/v1/auth/register", json=register_payload(email=None))

    assert response.status_code == 201
    assert response.json()["email"] is None
    assert response.json()["phone"] == "+84901234567"


async def test_register_without_phone_returns_422(test_client: AsyncClient) -> None:
    payload = register_payload()
    del payload["phone"]

    response = await test_client.post("/api/v1/auth/register", json=payload)

    assert response.status_code == 422


async def test_login_by_phone_returns_tokens(test_client: AsyncClient) -> None:
    await test_client.post("/api/v1/auth/register", json=register_payload())

    response = await test_client.post(
        "/api/v1/auth/login",
        json={"identifier": "0901234567", "password": PASSWORD},
    )

    assert response.status_code == 200
    assert response.cookies.get("gasbot_access_token")


async def test_register_with_weak_password_returns_422(test_client: AsyncClient) -> None:
    response = await test_client.post(
        "/api/v1/auth/register",
        json=register_payload(password="weak"),
    )

    assert response.status_code == 422


async def test_register_with_invalid_phone_returns_422(test_client: AsyncClient) -> None:
    payload = register_payload()
    payload["phone"] = "123"

    response = await test_client.post("/api/v1/auth/register", json=payload)

    assert response.status_code == 422


async def test_login_returns_tokens(test_client: AsyncClient) -> None:
    await test_client.post("/api/v1/auth/register", json=register_payload())

    response = await test_client.post(
        "/api/v1/auth/login",
        json={"identifier": "user@example.com", "password": PASSWORD},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["token_type"] == "bearer"
    assert "access_token" not in body
    assert "refresh_token" not in body
    assert response.cookies.get("gasbot_access_token")
    assert response.cookies.get("gasbot_refresh_token")
    set_cookie = response.headers.get_list("set-cookie")
    assert any(
        "gasbot_access_token=" in value and "HttpOnly" in value and "Path=/" in value
        for value in set_cookie
    )
    assert any(
        "gasbot_refresh_token=" in value and "HttpOnly" in value and "Path=/" in value
        for value in set_cookie
    )
    assert all("SameSite=lax" in value for value in set_cookie)
    assert all("SameSite=none" not in value for value in set_cookie)


async def test_login_with_wrong_password_returns_401(test_client: AsyncClient) -> None:
    await test_client.post("/api/v1/auth/register", json=register_payload())

    response = await test_client.post(
        "/api/v1/auth/login",
        json={"identifier": "user@example.com", "password": "wrong"},
    )

    assert response.status_code == 401
    assert response.json()["detail"] == "Số điện thoại/email hoặc mật khẩu không đúng."


async def test_account_locks_after_5_failed_logins(test_client: AsyncClient) -> None:
    await test_client.post("/api/v1/auth/register", json=register_payload())

    for index in range(5):
        transport = ASGITransport(app=app, client=(f"127.0.0.{index + 1}", 123))
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            await client.post(
                "/api/v1/auth/login",
                json={"identifier": "user@example.com", "password": "wrong"},
            )

    transport = ASGITransport(app=app, client=("127.0.0.6", 123))
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/api/v1/auth/login",
            json={"identifier": "user@example.com", "password": PASSWORD},
        )

    assert response.status_code == 401
    assert response.json()["error_code"] == "account_locked"


async def test_me_endpoint_returns_current_user(test_client: AsyncClient) -> None:
    await test_client.post("/api/v1/auth/register", json=register_payload())
    await test_client.post(
        "/api/v1/auth/login",
        json={"identifier": "user@example.com", "password": PASSWORD},
    )

    response = await test_client.get("/api/v1/auth/me")

    assert response.status_code == 200
    assert response.json()["email"] == "user@example.com"


async def test_me_endpoint_without_auth_returns_401(test_client: AsyncClient) -> None:
    response = await test_client.get("/api/v1/auth/me")

    assert response.status_code == 401


async def test_protected_endpoint_with_blacklisted_token_returns_401(
    test_client: AsyncClient,
) -> None:
    await test_client.post("/api/v1/auth/register", json=register_payload())
    login = await test_client.post(
        "/api/v1/auth/login",
        json={"identifier": "user@example.com", "password": PASSWORD},
    )
    token = login.cookies["gasbot_access_token"]
    await test_client.post("/api/v1/auth/logout")

    response = await test_client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 401


async def test_logout_revokes_refresh_token(test_client: AsyncClient) -> None:
    await test_client.post("/api/v1/auth/register", json=register_payload())
    login = await test_client.post(
        "/api/v1/auth/login",
        json={"identifier": "user@example.com", "password": PASSWORD},
    )
    refresh_token = login.cookies["gasbot_refresh_token"]

    await test_client.post("/api/v1/auth/logout")
    response = await test_client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": refresh_token},
    )

    assert response.status_code == 401
    assert response.json()["error_code"] == "token_revoked"


async def test_logout_deletes_refresh_cookie_at_root_path(test_client: AsyncClient) -> None:
    await test_client.post("/api/v1/auth/register", json=register_payload())
    await test_client.post(
        "/api/v1/auth/login",
        json={"identifier": "user@example.com", "password": PASSWORD},
    )

    response = await test_client.post("/api/v1/auth/logout")

    assert response.status_code == 204
    set_cookie = response.headers.get_list("set-cookie")
    assert any(
        "gasbot_refresh_token=" in value and "Max-Age=0" in value and "Path=/" in value
        for value in set_cookie
    )


async def test_refresh_endpoint_with_valid_token(test_client: AsyncClient) -> None:
    await test_client.post("/api/v1/auth/register", json=register_payload())
    await test_client.post(
        "/api/v1/auth/login",
        json={"identifier": "user@example.com", "password": PASSWORD},
    )

    response = await test_client.post("/api/v1/auth/refresh")

    assert response.status_code == 200
    assert response.cookies.get("gasbot_access_token")
    set_cookie = response.headers.get_list("set-cookie")
    assert any(
        "gasbot_refresh_token=" in value and "HttpOnly" in value and "Path=/" in value
        for value in set_cookie
    )
    assert "access_token" not in response.json()


async def test_email_otp_request_returns_generic_message(test_client: AsyncClient) -> None:
    await test_client.post("/api/v1/auth/register", json=register_payload())

    response = await test_client.post(
        "/api/v1/auth/email/otp-request",
        json={"email": "user@example.com"},
    )

    assert response.status_code == 200
    assert response.json()["detail"] == "Nếu email hợp lệ, mã xác minh đã được gửi."


async def test_email_otp_request_unknown_email_is_generic(test_client: AsyncClient) -> None:
    response = await test_client.post(
        "/api/v1/auth/email/otp-request",
        json={"email": "missing@example.com"},
    )

    assert response.status_code == 200
    assert response.json()["detail"] == "Nếu email hợp lệ, mã xác minh đã được gửi."


async def test_email_otp_verify_succeeds_with_correct_code(
    test_client: AsyncClient, mock_redis: Any
) -> None:
    register = await test_client.post("/api/v1/auth/register", json=register_payload())
    user_id = register.json()["id"]
    await test_client.post("/api/v1/auth/email/otp-request", json={"email": "user@example.com"})
    code = await mock_redis.get(f"email_otp:{user_id}")

    response = await test_client.post(
        "/api/v1/auth/email/otp-verify",
        json={"email": "user@example.com", "code": code},
    )

    assert response.status_code == 200
    assert response.json() == {"verified": True}
    assert await mock_redis.get(f"email_otp:{user_id}") is None


async def test_email_otp_verify_wrong_code_returns_400(test_client: AsyncClient) -> None:
    await test_client.post("/api/v1/auth/register", json=register_payload())
    await test_client.post("/api/v1/auth/email/otp-request", json={"email": "user@example.com"})

    response = await test_client.post(
        "/api/v1/auth/email/otp-verify",
        json={"email": "user@example.com", "code": "000000"},
    )

    assert response.status_code == 400
    assert response.json()["error_code"] == "invalid_email_otp"
