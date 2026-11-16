from fastapi import status

def test_tenant_user_isolation(client, test_tenants):
    token1 = test_tenants["token1"]  # Alice in Acme Corp
    token2 = test_tenants["token2"]  # Bob in Beta Industries

    # Alice lists users - should only see Alice, not Bob
    headers1 = {"Authorization": f"Bearer {token1}"}
    r1 = client.get("/v1/users/", headers=headers1)
    assert r1.status_code == status.HTTP_200_OK
    emails1 = [u["email"] for u in r1.json()]
    assert "admin@acme.com" in emails1
    assert "bob@beta.com" not in emails1

    # Bob lists users - should only see Bob, not Alice
    headers2 = {"Authorization": f"Bearer {token2}"}
    r2 = client.get("/v1/users/", headers=headers2)
    assert r2.status_code == status.HTTP_200_OK
    emails2 = [u["email"] for u in r2.json()]
    assert "bob@beta.com" in emails2
    assert "admin@acme.com" not in emails2

def test_tenant_workspace_isolation(client, test_tenants):
    token1 = test_tenants["token1"]
    token2 = test_tenants["token2"]

    headers1 = {"Authorization": f"Bearer {token1}"}
    r1 = client.get("/v1/workspaces/", headers=headers1)
    assert r1.status_code == status.HTTP_200_OK
    names1 = [w["name"] for w in r1.json()]
    assert "Acme Default WS" in names1
    assert "Beta Default WS" not in names1

    headers2 = {"Authorization": f"Bearer {token2}"}
    r2 = client.get("/v1/workspaces/", headers=headers2)
    assert r2.status_code == status.HTTP_200_OK
    names2 = [w["name"] for w in r2.json()]
    assert "Beta Default WS" in names2
    assert "Acme Default WS" not in names2

def test_tenant_cannot_modify_other_tenant_user(client, test_tenants):
    token1 = test_tenants["token1"] # Acme admin
    user2_id = test_tenants["user2"].id # Beta user

    headers1 = {"Authorization": f"Bearer {token1}"}
    # Alice attempts to deactivate Bob in Beta Corp
    r = client.patch(f"/v1/users/{user2_id}", json={"is_active": False}, headers=headers1)
    # Must return 404 Not Found to prevent IDOR / information leakage
    assert r.status_code == status.HTTP_404_NOT_FOUND

