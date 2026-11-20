"""End-to-end auth / authorisation behaviour through the HTTP API."""

from tests.conftest import login

USER_PASSWORD = "user-password-123"


def _create_user(client, admin_headers, username, is_admin=False):
    response = client.post(
        "/users/",
        headers=admin_headers,
        json={
            "username": username,
            "password": USER_PASSWORD,
            "is_admin": is_admin,
            "admin_password": "step-up-password",
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_protected_routes_require_auth(client):
    for path in ("/images/", "/settings/", "/users/", "/stats/", "/activity/", "/jobs/", "/presets/"):
        assert client.get(path).status_code == 401, path
    assert client.post("/imports/", json={"urls": ["https://example.com/a.jpg"]}).status_code == 401
    assert client.post("/playground/from-url", json={"url": "https://example.com/a.jpg"}).status_code == 401


def test_health_is_public_and_leaks_nothing(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_security_headers(client):
    response = client.get("/health")
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["x-frame-options"] == "DENY"


def test_bootstrap_admin_login_and_me(client, admin_headers):
    response = client.get("/auth/me", headers=admin_headers)
    assert response.json() == {"username": "admin", "is_admin": True}


def test_wrong_password_is_rejected_then_throttled(client):
    for _ in range(3):
        response = client.post("/auth/login", json={"username": "admin", "password": "nope"})
        assert response.status_code == 401
    response = client.post("/auth/login", json={"username": "admin", "password": "bootstrap-password"})
    assert response.status_code == 429
    assert int(response.headers["retry-after"]) > 0


def test_unknown_user_gets_same_error(client):
    response = client.post("/auth/login", json={"username": "ghost", "password": "whatever"})
    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid username or password"


def test_api_key_header_only(client):
    assert client.get("/auth/me", headers={"X-API-Key": "integration-key-for-tests"}).status_code == 200
    assert client.get("/auth/me?api_key=integration-key-for-tests").status_code == 401
    assert client.get("/auth/me", headers={"X-API-Key": "wrong"}).status_code == 401


def test_non_admin_user_cannot_use_admin_endpoints(client, admin_headers):
    _create_user(client, admin_headers, "operator1")
    headers = login(client, "operator1", USER_PASSWORD)

    assert client.get("/auth/me", headers=headers).json() == {"username": "operator1", "is_admin": False}
    assert client.get("/settings/", headers=headers).status_code == 200
    assert client.get("/users/", headers=headers).status_code == 403
    assert client.patch("/settings/", headers=headers, json={"group_depth": 2}).status_code == 403
    assert (
        client.post(
            "/settings/reset-db", headers=headers, json={"admin_password": "step-up-password", "confirm": "RESET"}
        ).status_code
        == 403
    )


def test_admin_user_role(client, admin_headers):
    _create_user(client, admin_headers, "admin2", is_admin=True)
    headers = login(client, "admin2", USER_PASSWORD)
    assert client.get("/users/", headers=headers).status_code == 200


def test_deleted_user_token_is_revoked_immediately(client, admin_headers):
    user = _create_user(client, admin_headers, "temp_user")
    headers = login(client, "temp_user", USER_PASSWORD)
    assert client.get("/auth/me", headers=headers).status_code == 200

    response = client.request(
        "DELETE", f"/users/{user['id']}", headers=admin_headers, json={"admin_password": "step-up-password"}
    )
    assert response.status_code == 204
    assert client.get("/auth/me", headers=headers).status_code == 401


def test_user_creation_validation(client, admin_headers):
    base = {"password": USER_PASSWORD, "admin_password": "step-up-password"}
    assert client.post("/users/", headers=admin_headers, json={**base, "username": "bad name!"}).status_code == 422
    weak = client.post("/users/", headers=admin_headers, json={**base, "username": "weakpw", "password": "123"})
    assert weak.status_code == 422  # too short for the request model
    too_long = client.post("/users/", headers=admin_headers, json={**base, "username": "longpw", "password": "é" * 40})
    assert too_long.status_code == 400  # 80 bytes: over bcrypt's 72-byte limit, caught by the password policy
    assert "72 bytes" in too_long.json()["detail"]
    assert (
        client.post(
            "/users/", headers=admin_headers, json={**base, "username": "x_user", "admin_password": "wrong"}
        ).status_code
        == 403
    )
    assert client.post("/users/", headers=admin_headers, json={**base, "username": "admin"}).status_code == 409


def test_settings_validation(client, admin_headers):
    assert client.patch("/settings/", headers=admin_headers, json={"process_concurrency": 10**9}).status_code == 422
    assert client.patch("/settings/", headers=admin_headers, json={"group_depth": 6}).status_code == 422
    response = client.patch("/settings/", headers=admin_headers, json={"max_retry_count": 5})
    assert response.status_code == 200
    assert response.json()["max_retry_count"] == 5


def test_admin_prefixes_validation(client, admin_headers):
    body = {"admin_password": "step-up-password"}
    assert (
        client.patch("/settings/admin", headers=admin_headers, json={**body, "backup_prefix": "../x/"}).status_code
        == 422
    )
    assert (
        client.patch(
            "/settings/admin", headers=admin_headers, json={**body, "backup_prefix": "images/backup/"}
        ).status_code
        == 400
    )  # nested inside the source prefix
    wrong = {"admin_password": "wrong", "source_prefix": "pics/"}
    assert client.patch("/settings/admin", headers=admin_headers, json=wrong).status_code == 403


def test_admin_publish_and_filter_validation(client, admin_headers):
    body = {"admin_password": "step-up-password"}
    webp_copy = {"derivatives": [{"name": "{stem}.webp", "format": "webp"}]}
    # A .webp derivative would overwrite .webp sources while webp is an allowed source extension.
    response = client.patch("/settings/admin", headers=admin_headers, json={**body, "publish": webp_copy})
    assert response.status_code == 400
    response = client.patch(
        "/settings/admin",
        headers=admin_headers,
        json={**body, "publish": webp_copy, "source_filters": {"extensions": ["jpg", "jpeg", "png"]}},
    )
    assert response.status_code == 200, response.text
    assert response.json()["publish"]["derivatives"][0]["name"] == "{stem}.webp"
    bad_template = {"derivatives": [{"name": "../{stem}.{ext}"}]}
    assert (
        client.patch("/settings/admin", headers=admin_headers, json={**body, "publish": bad_template}).status_code
        == 422
    )
    # Back to the defaults for the other tests.
    response = client.patch(
        "/settings/admin",
        headers=admin_headers,
        json={**body, "publish": {}, "source_filters": {}},
    )
    assert response.status_code == 200
    assert response.json()["source_filters"]["extensions"] == ["jpg", "jpeg", "png", "webp"]


def test_reset_db_requires_confirmation(client, admin_headers):
    assert (
        client.post(
            "/settings/reset-db", headers=admin_headers, json={"admin_password": "step-up-password"}
        ).status_code
        == 422
    )
    assert (
        client.post(
            "/settings/reset-db", headers=admin_headers, json={"admin_password": "wrong", "confirm": "RESET"}
        ).status_code
        == 403
    )
