"""Motor de reglas que evalúa la salud del sistema a partir de las métricas.

Funciona sin conexión a ningún proveedor de IA y además le da al copiloto
un punto de partida objetivo (puntaje y hallazgos) sobre el cual razonar.
"""

# metric: (etiqueta, unidad, umbral warning, umbral critical)
RULES = {
    "cpu_percent": ("CPU", "%", 70, 85),
    "memory_percent": ("Memoria", "%", 80, 90),
    "disk_percent": ("Disco", "%", 75, 85),
    "error_rate_percent": ("Errores 5xx", "%", 1, 5),
    "latency_p95_ms": ("Latencia p95", " ms", 500, 1000),
}

ADVICE = {
    "cpu_percent": "Identifica el proceso con `docker stats` y considera limitar CPU o escalar la app.",
    "memory_percent": "Revisa fugas con `docker stats`, ajusta límites de memoria o añade swap/RAM.",
    "disk_percent": "Libera espacio con `docker system prune` y reduce la retención de Prometheus.",
    "error_rate_percent": "Revisa `docker compose logs app` para encontrar la excepción que genera los 5xx.",
    "latency_p95_ms": "Busca consultas lentas en MySQL y verifica saturación de hilos de gunicorn.",
}

PENALTY = {"critical": 35, "warning": 15, "unknown": 5}


def _finding(level, metric, title, detail):
    return {"level": level, "metric": metric, "title": title, "detail": detail}


def evaluate(snapshot):
    metrics = snapshot.get("metrics", {})
    findings, recommendations = [], []

    for key, (label, unit, warn, crit) in RULES.items():
        value = metrics.get(key)
        if value is None:
            # Sin tráfico no hay latencia ni errores: no es un problema.
            if key in ("latency_p95_ms", "error_rate_percent"):
                continue
            findings.append(_finding("unknown", key, f"{label}: sin datos", "Prometheus no devolvió valor."))
            continue
        shown = f"{value:.1f}{unit}"
        if value >= crit:
            findings.append(_finding("critical", key, f"{label} crítica: {shown}", f"Supera el umbral de {crit}{unit}."))
            recommendations.append(ADVICE[key])
        elif value >= warn:
            findings.append(_finding("warning", key, f"{label} elevada: {shown}", f"Supera el umbral de {warn}{unit}."))
            recommendations.append(ADVICE[key])
        else:
            findings.append(_finding("ok", key, f"{label} normal: {shown}", f"Por debajo de {warn}{unit}."))

    load, cores = metrics.get("load1"), metrics.get("cpu_cores")
    if load is not None and cores:
        per_core = load / cores
        level = "critical" if per_core >= 2 else "warning" if per_core >= 1 else "ok"
        findings.append(_finding(level, "load1", f"Carga 1m: {load:.2f} ({per_core:.2f} por núcleo)",
                                 f"{int(cores)} núcleos disponibles."))
        if level != "ok":
            recommendations.append("Hay más procesos listos que núcleos: revisa qué contenedor acapara la CPU.")

    down = metrics.get("targets_down") or 0
    if down:
        findings.append(_finding("critical", "targets_down", f"{int(down)} target(s) caídos",
                                 "Prometheus no puede leer uno o más servicios."))
        recommendations.append("Ejecuta `docker compose ps` y revisa la página /targets de Prometheus.")

    for alert in snapshot.get("alerts", []):
        if alert.get("state") != "firing":
            continue
        level = "critical" if alert.get("severity") == "critical" else "warning"
        findings.append(_finding(level, "alert", f"Alerta activa: {alert['name']}", alert.get("summary", "")))

    score = 100
    for f in findings:
        score -= PENALTY.get(f["level"], 0)
    score = max(score, 0)

    levels = {f["level"] for f in findings}
    status = "critical" if "critical" in levels else "warning" if "warning" in levels else "healthy"
    if not recommendations:
        recommendations.append("Todo en orden. Mantén las alertas activas y revisa el dashboard de Grafana a diario.")

    order = {"critical": 0, "warning": 1, "unknown": 2, "ok": 3}
    findings.sort(key=lambda f: order[f["level"]])
    return {
        "status": status,
        "score": score,
        "findings": findings,
        "recommendations": list(dict.fromkeys(recommendations)),
    }


STATUS_TEXT = {
    "healthy": "El sistema está **saludable**.",
    "warning": "El sistema presenta **advertencias** que conviene atender.",
    "critical": "El sistema está en **estado crítico** y requiere acción inmediata.",
}


def to_markdown(health):
    lines = ["## Diagnóstico", f"{STATUS_TEXT[health['status']]} Puntaje de salud: **{health['score']}/100**.", ""]
    issues = [f for f in health["findings"] if f["level"] in ("critical", "warning", "unknown")]
    if issues:
        lines.append("## Hallazgos")
        lines += [f"- {f['title']}. {f['detail']}" for f in issues]
        lines.append("")
    lines.append("## Acciones recomendadas")
    lines += [f"- {r}" for r in health["recommendations"]]
    return "\n".join(lines)
