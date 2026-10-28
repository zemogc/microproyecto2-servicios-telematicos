from app.extensions import db
from app.models import User

from conftest import login


def test_dashboard_and_api_require_login(anon):
    resp = anon.get("/")
    assert resp.status_code == 302 and resp.headers["Location"].endswith("/login")
    assert anon.get("/api/users").status_code == 401
    assert anon.get("/api/config").status_code == 401
    assert anon.post("/api/ai/insights", json={}).status_code == 401
    assert anon.get("/login").status_code == 200
    assert anon.get("/health").status_code == 200


def test_wrong_password_is_rejected(anon):
    resp = login(anon, password="incorrecta")
    assert resp.status_code == 401
    assert "incorrectos" in resp.get_data(as_text=True)
    assert anon.get("/api/users").status_code == 401


def test_login_logout_and_me(anon):
    assert login(anon).status_code == 302
    me = anon.get("/api/auth/me").get_json()
    assert me["username"] == "admin" and me["role"] == "admin"
    assert "password_hash" not in me
    assert anon.post("/logout").status_code == 302
    assert anon.get("/api/users").status_code == 401


def test_session_cookie_is_hardened(anon):
    login(anon)
    cookie = anon.get_cookie("opscenter_session")
    assert cookie.http_only and cookie.same_site == "Lax"


def test_non_admin_is_read_only(client, anon, make_user):
    make_user(username="lector", email="lector@example.com", role="viewer")
    assert login(anon, "lector", "supersecreta").status_code == 302
    assert anon.get("/api/users").status_code == 200
    assert anon.get("/api/metrics/overview").status_code in (200, 503)
    target = make_user(username="otro", email="otro@example.com").get_json()["id"]
    assert anon.delete(f"/api/users/{target}").status_code == 403
    assert anon.put(f"/api/users/{target}", json={}).status_code == 403
    assert anon.post("/api/users", json={}).status_code == 403


def test_admin_cannot_delete_or_demote_self(client):
    admin = User.query.filter_by(username="admin").first()
    assert client.delete(f"/api/users/{admin.id}").status_code == 400
    resp = client.put(f"/api/users/{admin.id}", json={
        "name": "Admin", "email": admin.email, "username": "admin", "role": "viewer",
    })
    assert resp.status_code == 422 and "role" in resp.get_json()["fields"]


def test_password_change_invalidates_sessions(client, anon, make_user):
    user_id = make_user(username="pepe", email="pepe@example.com", role="viewer").get_json()["id"]
    login(anon, "pepe", "supersecreta")
    assert anon.get("/api/users").status_code == 200
    user = db.session.get(User, user_id)
    user.set_password("otra-clave-segura")
    db.session.commit()
    assert anon.get("/api/users").status_code == 401


def test_cross_origin_writes_are_blocked(client):
    resp = client.post("/api/users", json={}, headers={"Origin": "https://evil.example"})
    assert resp.status_code == 403
    resp = client.post("/api/users", json={}, headers={"Origin": "http://localhost"})
    assert resp.status_code == 422


def test_admin_account_is_created_once(app):
    from app.auth import ensure_admin
    ensure_admin(app)
    assert User.query.filter_by(username="admin").count() == 1
    assert User.query.filter_by(username="admin").first().check_password("admin-test-pass")
