from app.extensions import db
from app.models import User


def test_create_user_hashes_password_and_hides_it(client, make_user):
    resp = make_user()
    assert resp.status_code == 201
    body = resp.get_json()
    assert "password" not in body and "password_hash" not in body

    user = db.session.get(User, body["id"])
    assert user.password_hash != "supersecreta"
    assert user.check_password("supersecreta")


def test_validation_errors_are_reported_per_field(client):
    resp = client.post("/api/users", json={"name": "A", "email": "nope", "username": "x", "password": "123"})
    assert resp.status_code == 422
    fields = resp.get_json()["fields"]
    assert set(fields) == {"name", "email", "username", "password"}


def test_rejects_non_json_body(client):
    resp = client.post("/api/users", data="hola", content_type="text/plain")
    assert resp.status_code == 400


def test_duplicate_email_and_username_conflict(client, make_user):
    make_user()
    resp = make_user(name="Otra Persona")
    assert resp.status_code == 409
    assert set(resp.get_json()["fields"]) == {"email", "username"}


def test_list_search_and_filter(client, make_user):
    make_user()
    make_user(name="Grace Hopper", email="grace@example.com", username="grace", role="devops")

    data = client.get("/api/users").get_json()
    assert data["total"] == 3  # incluye la cuenta admin inicial

    data = client.get("/api/users?q=grace").get_json()
    assert [u["username"] for u in data["items"]] == ["grace"]

    data = client.get("/api/users?role=devops").get_json()
    assert [u["username"] for u in data["items"]] == ["grace"]


def test_update_keeps_password_when_omitted(client, make_user):
    user_id = make_user().get_json()["id"]
    resp = client.put(f"/api/users/{user_id}", json={
        "name": "Ada King", "email": "ada@example.com", "username": "ada", "role": "devops",
    })
    assert resp.status_code == 200
    assert resp.get_json()["role"] == "devops"
    assert db.session.get(User, user_id).check_password("supersecreta")


def test_delete_and_404(client, make_user):
    user_id = make_user().get_json()["id"]
    assert client.delete(f"/api/users/{user_id}").status_code == 200
    assert client.get(f"/api/users/{user_id}").status_code == 404
    assert client.delete(f"/api/users/{user_id}").status_code == 404


def test_stats_counts_by_role(client, make_user):
    make_user()
    stats = client.get("/api/users/stats").get_json()
    assert stats["total"] == 2
    assert stats["by_role"]["admin"] == 2
    assert stats["by_role"]["viewer"] == 0
