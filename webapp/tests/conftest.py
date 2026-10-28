import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app  # noqa: E402
from app.auth import ensure_admin  # noqa: E402
from app.extensions import db  # noqa: E402


@pytest.fixture
def app():
    app = create_app("app.config.TestConfig")
    with app.app_context():
        db.create_all()
        ensure_admin(app)
        yield app
        db.session.remove()
        db.drop_all()


@pytest.fixture
def anon(app):
    """Cliente sin sesión."""
    return app.test_client()


def login(client, username="admin", password="admin-test-pass"):
    return client.post("/login", data={"username": username, "password": password})


@pytest.fixture
def client(app):
    """Cliente con sesión de administrador."""
    c = app.test_client()
    assert login(c).status_code == 302
    return c


@pytest.fixture
def make_user(client):
    def _make(**overrides):
        payload = {
            "name": "Ada Lovelace",
            "email": "ada@example.com",
            "username": "ada",
            "password": "supersecreta",
            "role": "admin",
        }
        payload.update(overrides)
        return client.post("/api/users", json=payload)

    return _make
