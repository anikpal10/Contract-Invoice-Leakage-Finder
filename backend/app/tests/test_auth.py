from fastapi import status

def test_user_registration(client):
    payload = {
        "email": "sarah.connor@cyberdyne.io",
        "password": "Password123!",
        "full_name": "Sarah Connor",
        "organization_name": "Cyberdyne Systems",
        "role": "ADMIN"
    }
    response = client.post("/v1/auth/register", json=payload)
    assert response.status_code == status.HTTP_201_CREATED
    data = response.json()
    assert "access_token" in data
    assert "refresh_token" in data
    assert data["email"] == "sarah.connor@cyberdyne.io"
    assert data["role"] == "ADMIN"
    assert data["organization_name"] == "Cyberdyne Systems"

def test_duplicate_registration_fails(client):
    payload = {
        "email": "dup@example.com",
        "password": "Password123!",
        "full_name": "First User",
        "organization_name": "Unique Corp"
    }
    r1 = client.post("/v1/auth/register", json=payload)
    assert r1.status_code == status.HTTP_201_CREATED

    r2 = client.post("/v1/auth/register", json=payload)
    assert r2.status_code == status.HTTP_400_BAD_REQUEST
    assert "already exists" in r2.json()["detail"]

def test_user_login_success(client, test_tenants):
    payload = {
        "email": "admin@acme.com",
        "password": "Secret123!"
    }
    response = client.post("/v1/auth/login", json=payload)
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["email"] == "admin@acme.com"
    assert "access_token" in data

def test_user_login_wrong_password(client, test_tenants):
    payload = {
        "email": "admin@acme.com",
        "password": "WrongPassword!"
    }
    response = client.post("/v1/auth/login", json=payload)
    assert response.status_code == status.HTTP_401_UNAUTHORIZED

def test_get_current_user_me(client, test_tenants):
    token = test_tenants["token1"]
    headers = {"Authorization": f"Bearer {token}"}
    response = client.get("/v1/auth/me", headers=headers)
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["email"] == "admin@acme.com"
    assert data["role"] == "ADMIN"

def test_refresh_token_endpoint(client, test_tenants):
    login_resp = client.post("/v1/auth/login", json={
        "email": "admin@acme.com",
        "password": "Secret123!"
    })
    tokens = login_resp.json()
    refresh_resp = client.post("/v1/auth/refresh", json={
        "refresh_token": tokens["refresh_token"]
    })
    assert refresh_resp.status_code == status.HTTP_200_OK
    refreshed_data = refresh_resp.json()
    assert "access_token" in refreshed_data

