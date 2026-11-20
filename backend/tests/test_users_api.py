"""User deactivation: `PATCH /users/{id}` (admin + step-up password)."""

from tests.conftest import login

PASSWORD = "user-password-123"
STEP_UP = {"admin_password": "step-up-password"}


def _create(client, admin_headers, username: str, is_admin: bool = False) -> dict:
    body = {"username": username, "password": PASSWORD, "is_admin": is_admin, **STEP_UP}
    response = client.post("/users/", headers=admin_headers, json=body)
    assert response.status_code == 201, response.text
    return response.json()


def _set_active(client, headers, user_id: int, is_active: bool, **overrides):
    return client.patch(f"/users/{user_id}", headers=headers, json={"is_active": is_active, **STEP_UP, **overrides})


def test_deactivation_revokes_access_at_once_and_reactivation_restores_it(client, admin_headers):
    user = _create(client, admin_headers, "deact_user")
    assert user["is_active"] is True
    headers = login(client, "deact_user", PASSWORD)
    assert client.get("/auth/me", headers=headers).status_code == 200

    response = _set_active(client, admin_headers, user["id"], False)
    assert response.status_code == 200, response.text
    assert response.json() == {**user, "is_active": False}

    # The token issued before the change stops working immediately...
    assert client.get("/auth/me", headers=headers).status_code == 401
    assert client.get("/images/", headers=headers).status_code == 401
    # ...and signing in again is refused with the same answer as a wrong password.
    refused = client.post("/auth/login", json={"username": "deact_user", "password": PASSWORD})
    assert refused.status_code == 401
    assert refused.json()["detail"] == "Invalid username or password"

    listed = {u["username"]: u for u in client.get("/users/", headers=admin_headers).json()}
    assert listed["deact_user"]["is_active"] is False

    assert _set_active(client, admin_headers, user["id"], True).json()["is_active"] is True
    assert client.get("/auth/me", headers=headers).status_code == 200  # the old token is valid again
    assert client.get("/auth/me", headers=login(client, "deact_user", PASSWORD)).status_code == 200

    events = client.get("/activity/", headers=admin_headers, params={"search": "deact_user", "limit": 200}).json()
    by_type = {e["event_type"]: e for e in events}
    assert {"user.deactivated", "user.activated"} <= set(by_type)
    assert by_type["user.deactivated"]["username"] == "admin"


def test_an_admin_cannot_deactivate_their_own_account(client, admin_headers):
    me = _create(client, admin_headers, "deact_admin", is_admin=True)
    headers = login(client, "deact_admin", PASSWORD)

    response = _set_active(client, headers, me["id"], False)
    assert response.status_code == 400
    assert response.json()["detail"] == "You cannot deactivate your own account"
    assert client.get("/auth/me", headers=headers).status_code == 200
    assert _set_active(client, headers, me["id"], True).status_code == 200  # a no-op is fine


def test_deactivation_needs_the_admin_role_and_the_step_up_password(client, admin_headers):
    target = _create(client, admin_headers, "deact_target")
    _create(client, admin_headers, "deact_operator")
    operator = login(client, "deact_operator", PASSWORD)

    assert _set_active(client, operator, target["id"], False).status_code == 403
    assert _set_active(client, admin_headers, target["id"], False, admin_password="wrong").status_code == 403
    assert client.patch(f"/users/{target['id']}", headers=admin_headers, json={"is_active": False}).status_code == 422
    assert client.patch(f"/users/{target['id']}", headers=admin_headers, json=STEP_UP).status_code == 422
    assert client.patch(f"/users/{target['id']}", json={"is_active": False, **STEP_UP}).status_code == 401
    assert client.get("/auth/me", headers=login(client, "deact_target", PASSWORD)).status_code == 200


def test_user_ids_are_validated(client, admin_headers):
    assert _set_active(client, admin_headers, 999_999, False).status_code == 404
    assert _set_active(client, admin_headers, 0, False).status_code == 422
    assert client.request("DELETE", "/users/0", headers=admin_headers, json=STEP_UP).status_code == 422
    assert client.request("DELETE", "/users/999999", headers=admin_headers, json=STEP_UP).status_code == 404
    assert client.delete("/presets/0", headers=admin_headers).status_code == 422
    assert client.post("/presets/0/default", headers=admin_headers).status_code == 422
