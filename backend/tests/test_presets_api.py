"""Preset CRUD and the single-default rule through the HTTP API."""

from tests.conftest import login

STEP_UP = {"admin_password": "step-up-password"}


def _presets(client, headers) -> list[dict]:
    response = client.get("/presets/", headers=headers)
    assert response.status_code == 200
    return response.json()


def _defaults(client, headers) -> list[int]:
    return [p["id"] for p in _presets(client, headers) if p["is_default"]]


def test_builtin_presets_are_seeded_with_one_default(client, admin_headers):
    presets = {p["name"]: p for p in _presets(client, admin_headers)}
    assert {"White background (square)", "Transparent cutout", "Upscale only", "Web optimize"} <= set(presets)
    assert len(_defaults(client, admin_headers)) == 1
    web = presets["Web optimize"]["config"]
    assert web["output"] == {"format": "webp", "quality": 82, "max_bytes": 512000}


def test_create_update_and_delete(client, admin_headers):
    response = client.post(
        "/presets/",
        headers=admin_headers,
        json={"name": "Thumbs", "description": "small", "config": {"canvas": {"width": 200, "height": 200}}},
    )
    assert response.status_code == 201, response.text
    created = response.json()
    assert created["config"]["canvas"]["width"] == 200
    assert created["config"]["canvas"]["fill_ratio"] == 0.85  # filled from defaults
    assert created["is_default"] is False

    duplicate = client.post("/presets/", headers=admin_headers, json={"name": "Thumbs"})
    assert duplicate.status_code == 409

    response = client.patch(
        f"/presets/{created['id']}",
        headers=admin_headers,
        json={"name": "Thumbs v2", "config": {"output": {"format": "png"}}},
    )
    assert response.status_code == 200
    updated = response.json()
    assert updated["name"] == "Thumbs v2"
    assert updated["config"]["output"]["format"] == "png"
    assert updated["config"]["canvas"]["width"] == 1000  # config is replaced, not merged

    assert client.delete(f"/presets/{created['id']}", headers=admin_headers).status_code == 204
    assert client.delete(f"/presets/{created['id']}", headers=admin_headers).status_code == 404


def test_invalid_config_is_422(client, admin_headers):
    body = {
        "name": "Bad",
        "config": {"canvas": {"enabled": True, "background": "transparent"}, "output": {"format": "jpeg"}},
    }
    assert client.post("/presets/", headers=admin_headers, json=body).status_code == 422
    assert client.post("/presets/", headers=admin_headers, json={"name": "x" * 65}).status_code == 422


def test_default_rules(client, admin_headers):
    (original_default,) = _defaults(client, admin_headers)
    other = client.post("/presets/", headers=admin_headers, json={"name": "Next default"}).json()

    response = client.post(f"/presets/{other['id']}/default", headers=admin_headers)
    assert response.status_code == 200 and response.json()["is_default"] is True
    assert _defaults(client, admin_headers) == [other["id"]]
    assert client.get("/settings/", headers=admin_headers).json()["default_preset_id"] == other["id"]
    assert client.delete(f"/presets/{other['id']}", headers=admin_headers).status_code == 409

    # PATCH /settings default_preset_id is the same operation.
    response = client.patch("/settings/", headers=admin_headers, json={"default_preset_id": original_default})
    assert response.status_code == 200 and response.json()["default_preset_id"] == original_default
    assert _defaults(client, admin_headers) == [original_default]
    assert client.patch("/settings/", headers=admin_headers, json={"default_preset_id": 99999}).status_code == 422
    assert client.delete(f"/presets/{other['id']}", headers=admin_headers).status_code == 204


def test_non_admins_can_read_but_not_change(client, admin_headers):
    client.post(
        "/users/",
        headers=admin_headers,
        json={"username": "preset_viewer", "password": "viewer-password-1", **STEP_UP},
    )
    headers = login(client, "preset_viewer", "viewer-password-1")
    preset_id = _presets(client, headers)[0]["id"]
    assert client.post("/presets/", headers=headers, json={"name": "Nope"}).status_code == 403
    assert client.patch(f"/presets/{preset_id}", headers=headers, json={"name": "Nope"}).status_code == 403
    assert client.delete(f"/presets/{preset_id}", headers=headers).status_code == 403
    assert client.post(f"/presets/{preset_id}/default", headers=headers).status_code == 403
