import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app  # noqa: E402
from app.extensions import db  # noqa: E402


@pytest.fixture
def app():
    app = create_app("app.config.TestConfig")
    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()


@pytest.fixture
def client(app):
    return app.test_client()


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
