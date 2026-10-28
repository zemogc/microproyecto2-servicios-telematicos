def test_health_ok(anon):
    client = anon
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.get_json()["database"] == "ok"


def test_metrics_exposes_app_series(client, make_user):
    make_user()
    client.get("/api/users")
    text = client.get("/metrics").get_data(as_text=True)
    assert "opscenter_http_requests_total" in text
    assert 'endpoint="/api/users"' in text
    assert "opscenter_users_total 2.0" in text


def test_unknown_api_route_returns_json(client):
    resp = client.get("/api/no-existe")
    assert resp.status_code == 404
    assert "error" in resp.get_json()


def test_index_renders(client):
    assert client.get("/").status_code == 200
