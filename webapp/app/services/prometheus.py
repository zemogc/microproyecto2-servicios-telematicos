"""Cliente mínimo de la API HTTP de Prometheus."""
import math
import time

import requests

# PromQL de cada indicador que muestra la interfaz y que analiza el copiloto.
QUERIES = {
    "cpu_percent": '100 - (avg(rate(node_cpu_seconds_total{mode="idle"}[2m])) * 100)',
    "memory_percent": "(1 - sum(node_memory_MemAvailable_bytes) / sum(node_memory_MemTotal_bytes)) * 100",
    "disk_percent": (
        'max((1 - node_filesystem_avail_bytes{fstype=~"ext4|xfs|btrfs|zfs"}'
        ' / node_filesystem_size_bytes{fstype=~"ext4|xfs|btrfs|zfs"}) * 100'
        " and on (device, mountpoint) node_filesystem_readonly == 0)"
    ),
    "load1": "max(node_load1)",
    "cpu_cores": "count(count by (cpu) (node_cpu_seconds_total))",
    "uptime_seconds": "max(time() - node_boot_time_seconds)",
    "request_rate": "sum(rate(opscenter_http_requests_total[5m]))",
    "error_rate_percent": (
        '(sum(rate(opscenter_http_requests_total{status=~"5.."}[5m])) or vector(0))'
        " / clamp_min(sum(rate(opscenter_http_requests_total[5m])), 0.001) * 100"
    ),
    "latency_p95_ms": (
        "histogram_quantile(0.95, sum by (le) (rate(opscenter_http_request_duration_seconds_bucket[5m]))) * 1000"
    ),
    "targets_down": "count(up == 0) or vector(0)",
    "targets_total": "count(up)",
}

SERIES = {
    "cpu_percent": QUERIES["cpu_percent"],
    "memory_percent": QUERIES["memory_percent"],
    "request_rate": QUERIES["request_rate"],
    "latency_p95_ms": QUERIES["latency_p95_ms"],
}


class PrometheusError(RuntimeError):
    pass


def _to_float(raw):
    try:
        value = float(raw)
    except (TypeError, ValueError):
        return None
    return None if math.isnan(value) or math.isinf(value) else round(value, 3)


class PrometheusClient:
    def __init__(self, base_url, timeout=3.0, session=None):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.http = session or requests.Session()

    def _get(self, path, params=None):
        try:
            resp = self.http.get(f"{self.base_url}{path}", params=params, timeout=self.timeout)
            resp.raise_for_status()
            body = resp.json()
        except (requests.RequestException, ValueError) as exc:
            raise PrometheusError(f"Prometheus no disponible: {exc}") from exc
        if body.get("status") != "success":
            raise PrometheusError(body.get("error", "respuesta inválida de Prometheus"))
        return body["data"]

    def query(self, promql):
        result = self._get("/api/v1/query", {"query": promql})["result"]
        return _to_float(result[0]["value"][1]) if result else None

    def query_range(self, promql, minutes=30, step=60):
        end = time.time()
        params = {"query": promql, "start": end - minutes * 60, "end": end, "step": step}
        result = self._get("/api/v1/query_range", params)["result"]
        if not result:
            return []
        return [[int(ts), _to_float(v)] for ts, v in result[0]["values"]]

    def alerts(self):
        alerts = self._get("/api/v1/alerts")["alerts"]
        return [
            {
                "name": a["labels"].get("alertname"),
                "severity": a["labels"].get("severity", "info"),
                "state": a.get("state"),
                "summary": a.get("annotations", {}).get("summary", ""),
            }
            for a in alerts
        ]

    def snapshot(self):
        """Valores actuales de todos los indicadores más las alertas activas."""
        metrics = {key: self.query(expr) for key, expr in QUERIES.items()}
        return {"metrics": metrics, "alerts": self.alerts(), "collected_at": int(time.time())}

    def series(self, minutes=30, step=60):
        return {key: self.query_range(expr, minutes, step) for key, expr in SERIES.items()}
