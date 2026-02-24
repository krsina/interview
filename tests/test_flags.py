"""Pytest tests for Feature Flag API endpoints. Requires PostgreSQL (see .env)."""
import uuid

import pytest


class TestHealth:
    def test_health_returns_200_and_healthy(self, client, api_prefix):
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json() == {"status": "healthy"}


class TestCreateFlag:
    def test_create_flag_returns_201_and_body(self, client, api_prefix):
        payload = {
            "name": f"test-flag-{uuid.uuid4().hex[:8]}",
            "description": "A test flag",
            "is_enabled": False,
        }
        response = client.post(f"{api_prefix}/flags/", json=payload)
        assert response.status_code == 201
        data = response.json()
        assert "id" in data
        assert data["name"] == payload["name"]
        assert data["description"] == payload["description"]
        assert data["is_enabled"] is False
        assert "created_at" in data
        assert "updated_at" in data

    def test_create_duplicate_flag_name_returns_409(self, client, api_prefix):
        name = f"dup-{uuid.uuid4().hex[:8]}"
        client.post(f"{api_prefix}/flags/", json={"name": name, "is_enabled": False})
        response = client.post(f"{api_prefix}/flags/", json={"name": name, "is_enabled": True})
        assert response.status_code == 409
        assert "already exists" in response.json()["detail"]


class TestListFlags:
    def test_list_flags_returns_200_with_items_and_total(self, client, api_prefix):
        response = client.get(f"{api_prefix}/flags/")
        assert response.status_code == 200
        data = response.json()
        assert "items" in data
        assert "total" in data
        assert isinstance(data["items"], list)
        assert isinstance(data["total"], int)

    def test_list_flags_pagination(self, client, api_prefix):
        response = client.get(f"{api_prefix}/flags/?skip=0&limit=2")
        assert response.status_code == 200
        assert len(response.json()["items"]) <= 2

    def test_list_flags_enabled_only_filter(self, client, api_prefix):
        response = client.get(f"{api_prefix}/flags/?enabled_only=true")
        assert response.status_code == 200
        for item in response.json()["items"]:
            assert item["is_enabled"] is True


class TestGetFlag:
    def test_get_flag_returns_200_when_exists(self, client, api_prefix):
        create = client.post(
            f"{api_prefix}/flags/",
            json={"name": f"get-{uuid.uuid4().hex[:8]}", "is_enabled": True},
        )
        assert create.status_code == 201
        flag_id = create.json()["id"]
        response = client.get(f"{api_prefix}/flags/{flag_id}")
        assert response.status_code == 200
        assert response.json()["id"] == flag_id

    def test_get_flag_returns_404_when_not_found(self, client, api_prefix):
        fake_id = str(uuid.uuid4())
        response = client.get(f"{api_prefix}/flags/{fake_id}")
        assert response.status_code == 404


class TestUpdateFlag:
    def test_update_flag_returns_200(self, client, api_prefix):
        create = client.post(
            f"{api_prefix}/flags/",
            json={"name": f"upd-{uuid.uuid4().hex[:8]}", "is_enabled": False},
        )
        assert create.status_code == 201
        flag_id = create.json()["id"]
        response = client.patch(
            f"{api_prefix}/flags/{flag_id}",
            json={"description": "Updated", "is_enabled": True},
        )
        assert response.status_code == 200
        assert response.json()["description"] == "Updated"
        assert response.json()["is_enabled"] is True

    def test_update_flag_empty_body_returns_422(self, client, api_prefix):
        create = client.post(
            f"{api_prefix}/flags/",
            json={"name": f"upd422-{uuid.uuid4().hex[:8]}", "is_enabled": False},
        )
        assert create.status_code == 201
        flag_id = create.json()["id"]
        response = client.patch(f"{api_prefix}/flags/{flag_id}", json={})
        assert response.status_code == 422


class TestToggleFlag:
    def test_toggle_flag_returns_200(self, client, api_prefix):
        create = client.post(
            f"{api_prefix}/flags/",
            json={"name": f"tog-{uuid.uuid4().hex[:8]}", "is_enabled": False},
        )
        assert create.status_code == 201
        flag_id = create.json()["id"]
        response = client.patch(
            f"{api_prefix}/flags/{flag_id}/toggle",
            json={"is_enabled": True},
        )
        assert response.status_code == 200
        assert response.json()["is_enabled"] is True


class TestDeleteFlag:
    def test_delete_flag_returns_200_and_message(self, client, api_prefix):
        create = client.post(
            f"{api_prefix}/flags/",
            json={"name": f"del-{uuid.uuid4().hex[:8]}", "is_enabled": False},
        )
        assert create.status_code == 201
        flag_id = create.json()["id"]
        name = create.json()["name"]
        response = client.delete(f"{api_prefix}/flags/{flag_id}")
        assert response.status_code == 200
        assert "deleted" in response.json()["detail"].lower()
        assert name in response.json()["detail"]
        get_response = client.get(f"{api_prefix}/flags/{flag_id}")
        assert get_response.status_code == 404


class TestEvaluate:
    def test_evaluate_returns_default_when_no_override(self, client, api_prefix):
        name = f"eval-default-{uuid.uuid4().hex[:8]}"
        create = client.post(
            f"{api_prefix}/flags/",
            json={"name": name, "is_enabled": True},
        )
        assert create.status_code == 201
        response = client.get(
            f"{api_prefix}/flags/evaluate",
            params={"flag_name": name, "user_id": "user_1"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["enabled"] is True
        assert data["flag_name"] == name
        assert data["user_id"] == "user_1"
        assert data["source"] == "default"

    def test_evaluate_returns_override_when_present(self, client, api_prefix):
        name = f"eval-override-{uuid.uuid4().hex[:8]}"
        create = client.post(
            f"{api_prefix}/flags/",
            json={"name": name, "is_enabled": True},
        )
        assert create.status_code == 201
        flag_id = create.json()["id"]
        client.put(
            f"{api_prefix}/flags/{flag_id}/users/user_2",
            json={"is_enabled": False},
        )
        response = client.get(
            f"{api_prefix}/flags/evaluate",
            params={"flag_name": name, "user_id": "user_2"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["enabled"] is False
        assert data["source"] == "override"

    def test_evaluate_returns_404_when_flag_not_found(self, client, api_prefix):
        response = client.get(
            f"{api_prefix}/flags/evaluate",
            params={"flag_name": "nonexistent-flag-name", "user_id": "user_1"},
        )
        assert response.status_code == 404


class TestUserOverrides:
    def test_put_override_creates_and_returns_201(self, client, api_prefix):
        create = client.post(
            f"{api_prefix}/flags/",
            json={"name": f"ov-create-{uuid.uuid4().hex[:8]}", "is_enabled": False},
        )
        assert create.status_code == 201
        flag_id = create.json()["id"]
        response = client.put(
            f"{api_prefix}/flags/{flag_id}/users/user_alpha",
            json={"is_enabled": True},
        )
        assert response.status_code == 201
        data = response.json()
        assert data["flag_id"] == flag_id
        assert data["user_id"] == "user_alpha"
        assert data["is_enabled"] is True

    def test_put_override_updates_existing_returns_200(self, client, api_prefix):
        create = client.post(
            f"{api_prefix}/flags/",
            json={"name": f"ov-upd-{uuid.uuid4().hex[:8]}", "is_enabled": False},
        )
        assert create.status_code == 201
        flag_id = create.json()["id"]
        client.put(
            f"{api_prefix}/flags/{flag_id}/users/user_beta",
            json={"is_enabled": True},
        )
        response = client.put(
            f"{api_prefix}/flags/{flag_id}/users/user_beta",
            json={"is_enabled": False},
        )
        assert response.status_code == 200
        assert response.json()["is_enabled"] is False

    def test_put_override_404_when_flag_missing(self, client, api_prefix):
        fake_id = str(uuid.uuid4())
        response = client.put(
            f"{api_prefix}/flags/{fake_id}/users/user_x",
            json={"is_enabled": True},
        )
        assert response.status_code == 404

    def test_delete_override_returns_204(self, client, api_prefix):
        create = client.post(
            f"{api_prefix}/flags/",
            json={"name": f"ov-del-{uuid.uuid4().hex[:8]}", "is_enabled": False},
        )
        assert create.status_code == 201
        flag_id = create.json()["id"]
        client.put(
            f"{api_prefix}/flags/{flag_id}/users/user_gamma",
            json={"is_enabled": True},
        )
        response = client.delete(f"{api_prefix}/flags/{flag_id}/users/user_gamma")
        assert response.status_code == 204

    def test_delete_override_404_when_override_missing(self, client, api_prefix):
        create = client.post(
            f"{api_prefix}/flags/",
            json={"name": f"ov-404-{uuid.uuid4().hex[:8]}", "is_enabled": False},
        )
        assert create.status_code == 201
        flag_id = create.json()["id"]
        response = client.delete(f"{api_prefix}/flags/{flag_id}/users/nonexistent_user")
        assert response.status_code == 404

    def test_list_overrides_returns_200_with_items_and_total(self, client, api_prefix):
        create = client.post(
            f"{api_prefix}/flags/",
            json={"name": f"ov-list-{uuid.uuid4().hex[:8]}", "is_enabled": False},
        )
        assert create.status_code == 201
        flag_id = create.json()["id"]
        response = client.get(f"{api_prefix}/flags/{flag_id}/users")
        assert response.status_code == 200
        data = response.json()
        assert "items" in data
        assert "total" in data
        assert isinstance(data["items"], list)
        assert isinstance(data["total"], int)

    def test_list_overrides_404_when_flag_missing(self, client, api_prefix):
        fake_id = str(uuid.uuid4())
        response = client.get(f"{api_prefix}/flags/{fake_id}/users")
        assert response.status_code == 404
