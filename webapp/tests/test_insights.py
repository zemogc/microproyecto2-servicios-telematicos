from types import SimpleNamespace

import pytest

from app.services import insights
from app.services.copilot import CopilotUnavailable
from app.services.prometheus import PrometheusClient, PrometheusError

HEALTHY = {
    "metrics": {
        "cpu_percent": 12.0, "memory_percent": 40.0, "disk_percent": 30.0, "load1": 0.4, "cpu_cores": 4,
        "uptime_seconds": 3600, "request_rate": 1.2, "error_rate_percent": 0.0, "latency_p95_ms": 20.0,
        "targets_down": 0, "targets_total": 3,
    },
    "alerts": [],
    "collected_at": 0,
}


def _snapshot(**metrics):
    return {**HEALTHY, "metrics": {**HEALTHY["metrics"], **metrics}}


def test_healthy_system_scores_100():
    health = insights.evaluate(HEALTHY)
    assert health["status"] == "healthy"
    assert health["score"] == 100


def test_critical_cpu_and_down_target():
    health = insights.evaluate(_snapshot(cpu_percent=97.0, targets_down=1))
    assert health["status"] == "critical"
    assert health["findings"][0]["level"] == "critical"
    assert health["score"] == 30
    assert any("docker compose ps" in r for r in health["recommendations"])


def test_warning_memory_and_firing_alert():
    snap = _snapshot(memory_percent=85.0)
    snap["alerts"] = [{"name": "LatenciaAlta", "severity": "warning", "state": "firing", "summary": "p95"}]
    health = insights.evaluate(snap)
    assert health["status"] == "warning"
    assert {f["metric"] for f in health["findings"] if f["level"] == "warning"} == {"memory_percent", "alert"}


def test_missing_traffic_metrics_are_not_penalized():
    health = insights.evaluate(_snapshot(latency_p95_ms=None, error_rate_percent=None))
    assert health["score"] == 100


def test_markdown_has_sections():
    md = insights.to_markdown(insights.evaluate(_snapshot(disk_percent=90.0)))
    assert "## Diagnóstico" in md and "## Acciones recomendadas" in md
    assert "Disco crítica" in md


class FakeResponse:
    def __init__(self, body):
        self._body = body

    def raise_for_status(self):
        pass

    def json(self):
        return self._body


class FakeSession:
    def get(self, url, params=None, timeout=None):
        if url.endswith("/alerts"):
            return FakeResponse({"status": "success", "data": {"alerts": []}})
        if url.endswith("/query_range"):
            return FakeResponse({"status": "success", "data": {"result": [{"values": [[1, "1.5"], [2, "NaN"]]}]}})
        return FakeResponse({"status": "success", "data": {"result": [{"value": [1, "42.123456"]}]}})


def test_prometheus_client_parses_values():
    prom = PrometheusClient("http://prom:9090", session=FakeSession())
    assert prom.query("up") == 42.123
    assert prom.query_range("up") == [[1, 1.5], [2, None]]
    snap = prom.snapshot()
    assert snap["metrics"]["cpu_percent"] == 42.123
    assert snap["alerts"] == []


@pytest.fixture
def fake_prometheus(monkeypatch):
    monkeypatch.setattr(PrometheusClient, "snapshot", lambda self: _snapshot(cpu_percent=90.0))
    monkeypatch.setattr(PrometheusClient, "series", lambda self, minutes=30, step=60: {"cpu_percent": [[1, 90.0]]})


def test_overview_endpoint(client, fake_prometheus):
    data = client.get("/api/metrics/overview").get_json()
    assert data["health"]["status"] == "critical"
    assert data["series"]["cpu_percent"] == [[1, 90.0]]


def test_insights_local_mode_without_key(client, fake_prometheus):
    data = client.post("/api/ai/insights", json={"question": "¿Por qué va lento?"}).get_json()
    assert data["provider"] == "local"
    assert "ANTHROPIC_API_KEY" in data["notice"]
    assert "CPU crítica" in data["analysis"]


def test_insights_uses_claude_when_key_present(app, client, fake_prometheus, monkeypatch):
    app.config["ANTHROPIC_API_KEY"] = "sk-test"
    seen = {}

    def fake_ask(api_key, model, effort, snapshot, health, question=""):
        seen.update(model=model, question=question, status=health["status"])
        return "## Diagnóstico\nCPU saturada.", "claude-opus-5-5"

    monkeypatch.setattr("app.api.insights.ask_claude", fake_ask)
    data = client.post("/api/ai/insights", json={"question": "x" * 900}).get_json()
    assert data["provider"] == "claude"
    assert data["analysis"].startswith("## Diagnóstico")
    assert seen["status"] == "critical"
    assert len(seen["question"]) == 500


def test_insights_falls_back_when_claude_fails(app, client, fake_prometheus, monkeypatch):
    app.config["ANTHROPIC_API_KEY"] = "sk-test"

    def boom(*args, **kwargs):
        raise CopilotUnavailable("La clave de Anthropic no es válida.")

    monkeypatch.setattr("app.api.insights.ask_claude", boom)
    data = client.post("/api/ai/insights", json={}).get_json()
    assert data["provider"] == "local"
    assert data["notice"].startswith("La clave de Anthropic no es válida.")


def test_insights_returns_503_without_prometheus(client, monkeypatch):
    def down(self):
        raise PrometheusError("Prometheus no disponible")

    monkeypatch.setattr(PrometheusClient, "snapshot", down)
    assert client.post("/api/ai/insights", json={}).status_code == 503


def test_ask_claude_builds_request(monkeypatch):
    from app.services import copilot

    captured = {}

    class FakeMessages:
        def create(self, **kwargs):
            captured.update(kwargs)
            return SimpleNamespace(
                stop_reason="end_turn",
                model=kwargs["model"],
                content=[SimpleNamespace(type="thinking", thinking=""), SimpleNamespace(type="text", text="Hola")],
            )

    class FakeClient:
        def __init__(self, **kwargs):
            self.beta = SimpleNamespace(messages=FakeMessages())

    monkeypatch.setattr(copilot.anthropic, "Anthropic", FakeClient)
    text, model = copilot.ask_claude("k", "claude-opus-5-5", "low", HEALTHY, insights.evaluate(HEALTHY), "¿todo bien?")
    assert (text, model) == ("Hola", "claude-opus-5-5")
    assert captured["extra_body"] == {"fallbacks": "default"}
    assert captured["output_config"] == {"effort": "low"}
    assert "¿todo bien?" in captured["messages"][0]["content"]


def test_ask_claude_refusal_raises(monkeypatch):
    from app.services import copilot

    class FakeClient:
        def __init__(self, **kwargs):
            create = lambda **kw: SimpleNamespace(stop_reason="refusal", model="m", content=[])  # noqa: E731
            self.beta = SimpleNamespace(messages=SimpleNamespace(create=create))

    monkeypatch.setattr(copilot.anthropic, "Anthropic", FakeClient)
    with pytest.raises(CopilotUnavailable):
        copilot.ask_claude("k", "m", "low", HEALTHY, insights.evaluate(HEALTHY))
