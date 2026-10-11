import pytest
import httpx


@pytest.mark.asyncio
async def test_user_registration_and_login(client: httpx.AsyncClient):
    """Verify user registration, duplicate prevention, and login token generation."""
    reg_payload = {
        "username": "operator1",
        "email": "operator1@websync.ai",
        "password": "secure_password_123",
        "role": "operator",
    }
    # 1. Register
    reg_res = await client.post("/api/v1/auth/register", json=reg_payload)
    assert reg_res.status_code == 201
    user_data = reg_res.json()
    assert user_data["username"] == "operator1"
    assert "hashed_password" not in user_data

    # 2. Duplicate registration fails
    dup_res = await client.post("/api/v1/auth/register", json=reg_payload)
    assert dup_res.status_code == 409

    # 3. Successful login
    login_res = await client.post(
        "/api/v1/auth/login",
        json={"username": "operator1", "password": "secure_password_123"},
    )
    assert login_res.status_code == 200
    token_data = login_res.json()
    assert "access_token" in token_data
    token = token_data["access_token"]

    # 4. Access /auth/me with Bearer token
    me_res = await client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert me_res.status_code == 200
    assert me_res.json()["username"] == "operator1"

    # 5. Bad password fails
    bad_login = await client.post(
        "/api/v1/auth/login",
        json={"username": "operator1", "password": "wrong_password"},
    )
    assert bad_login.status_code == 401
