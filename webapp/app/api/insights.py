from flask import Blueprint, current_app, jsonify, request

from ..metrics import AI_INSIGHTS
from ..services import insights
from ..services.copilot import CopilotUnavailable, ask_claude
from ..services.prometheus import PrometheusClient, PrometheusError

bp = Blueprint("insights", __name__, url_prefix="/api")

MAX_QUESTION = 500


def _prometheus():
    return PrometheusClient(current_app.config["PROMETHEUS_URL"])


@bp.get("/metrics/overview")
def overview():
    minutes = min(max(request.args.get("minutes", 30, type=int), 5), 360)
    prom = _prometheus()
    try:
        snapshot = prom.snapshot()
        series = prom.series(minutes=minutes, step=max(minutes, 15))
    except PrometheusError as exc:
        return jsonify({"error": str(exc)}), 503
    health = insights.evaluate(snapshot)
    return jsonify({**snapshot, "series": series, "health": {"status": health["status"], "score": health["score"]}})


@bp.post("/ai/insights")
def ai_insights():
    data = request.get_json(silent=True) or {}
    question = str(data.get("question") or "").strip()[:MAX_QUESTION]

    try:
        snapshot = _prometheus().snapshot()
    except PrometheusError as exc:
        AI_INSIGHTS.labels("none", "prometheus_error").inc()
        return jsonify({"error": str(exc)}), 503

    health = insights.evaluate(snapshot)
    cfg = current_app.config
    result = {"health": health, "snapshot": snapshot, "question": question}

    if cfg["ANTHROPIC_API_KEY"]:
        try:
            text, model = ask_claude(cfg["ANTHROPIC_API_KEY"], cfg["AI_MODEL"], cfg["AI_EFFORT"],
                                     snapshot, health, question)
            AI_INSIGHTS.labels("claude", "ok").inc()
            return jsonify({**result, "provider": "claude", "model": model, "analysis": text})
        except CopilotUnavailable as exc:
            AI_INSIGHTS.labels("claude", "fallback").inc()
            result["notice"] = f"{exc} Se muestra el análisis del motor de reglas local."
    else:
        result["notice"] = ("Modo local: define ANTHROPIC_API_KEY para obtener el diagnóstico "
                            "en lenguaje natural con Claude.")
        if question:
            result["notice"] += " Las preguntas libres solo se responden en modo IA."

    AI_INSIGHTS.labels("local", "ok").inc()
    return jsonify({**result, "provider": "local", "model": "reglas-opscenter", "analysis": insights.to_markdown(health)})
