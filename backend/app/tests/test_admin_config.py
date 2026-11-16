from decimal import Decimal
from fastapi import status

def test_admin_rule_config_lifecycle(client, test_tenants):
    token = test_tenants["token1"]  # Alice is ADMIN
    headers = {"Authorization": f"Bearer {token}"}

    # 1. Fetch default active rule config
    r_get = client.get("/v1/admin/rule-config", headers=headers)
    assert r_get.status_code == status.HTTP_200_OK
    data = r_get.json()
    assert data["version"] == 1
    assert data["is_active"] is True

    # 2. Update rule configuration - Creates version 2
    update_payload = {
        "price_variance_tolerance_pct": "1.50",
        "price_variance_tolerance_abs": "5.00",
        "quantity_variance_tolerance_pct": "2.00",
        "duplicate_window_days": 120,
        "fuzzy_match_threshold": 90,
        "high_severity_threshold": "750.00",
        "critical_severity_threshold": "3000.00",
        "require_grn_for_goods": True,
        "change_reason": "Executive approved Q4 audit policy update"
    }
    r_put = client.put("/v1/admin/rule-config", json=update_payload, headers=headers)
    assert r_put.status_code == status.HTTP_200_OK
    v2_data = r_put.json()
    assert v2_data["version"] == 2
    assert v2_data["is_active"] is True
    assert Decimal(str(v2_data["price_variance_tolerance_pct"])) == Decimal("1.50")
    assert v2_data["change_reason"] == "Executive approved Q4 audit policy update"

    # 3. Check rule configuration history
    r_hist = client.get("/v1/admin/rule-config/history", headers=headers)
    assert r_hist.status_code == status.HTTP_200_OK
    history = r_hist.json()
    assert len(history) == 2
    assert history[0]["version"] == 2
    assert history[1]["version"] == 1
    assert history[0]["is_active"] is True
    assert history[1]["is_active"] is False

def test_non_admin_cannot_update_rule_config(client, test_tenants):
    token = test_tenants["token2"]  # Bob is REVIEWER, not ADMIN
    headers = {"Authorization": f"Bearer {token}"}

    update_payload = {
        "price_variance_tolerance_pct": "5.00",
        "price_variance_tolerance_abs": "10.00"
    }
    r_put = client.put("/v1/admin/rule-config", json=update_payload, headers=headers)
    assert r_put.status_code == status.HTTP_403_FORBIDDEN

