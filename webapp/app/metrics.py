"""Métricas propias de la aplicación expuestas en /metrics para Prometheus."""
import time

from flask import Response, g, request
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Gauge, Histogram, Info, generate_latest

HTTP_REQUESTS = Counter(
    "opscenter_http_requests_total",
    "Peticiones HTTP atendidas por la aplicación",
    ["method", "endpoint", "status"],
)
HTTP_LATENCY = Histogram(
    "opscenter_http_request_duration_seconds",
    "Latencia de las peticiones HTTP",
    ["method", "endpoint"],
    buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10),
)
USERS_TOTAL = Gauge("opscenter_users_total", "Usuarios registrados en la base de datos")
AI_INSIGHTS = Counter(
    "opscenter_ai_insights_total",
    "Diagnósticos generados por el copiloto",
    ["provider", "outcome"],
)
BUILD_INFO = Info("opscenter_build", "Información de la versión desplegada")


def init_metrics(app):
    BUILD_INFO.info({"version": app.config["APP_VERSION"], "app": app.config["APP_NAME"]})

    @app.before_request
    def _start_timer():
        g._start = time.perf_counter()

    @app.after_request
    def _record(response):
        if request.path == "/metrics" or not hasattr(g, "_start"):
            return response
        endpoint = request.url_rule.rule if request.url_rule else "unmatched"
        HTTP_LATENCY.labels(request.method, endpoint).observe(time.perf_counter() - g._start)
        HTTP_REQUESTS.labels(request.method, endpoint, str(response.status_code)).inc()
        return response

    @app.get("/metrics")
    def metrics():
        from .models import User

        try:
            USERS_TOTAL.set(User.query.count())
        except Exception:  # la BD caída no debe tumbar el scrape
            pass
        return Response(generate_latest(), mimetype=CONTENT_TYPE_LATEST)
