from flask import Blueprint, current_app, jsonify
from sqlalchemy import text

from ..extensions import db

bp = Blueprint("system", __name__)


@bp.get("/health")
def health():
    try:
        db.session.execute(text("SELECT 1"))
        database = "ok"
    except Exception:
        database = "down"
    healthy = database == "ok"
    return jsonify({
        "status": "ok" if healthy else "degraded",
        "database": database,
        "version": current_app.config["APP_VERSION"],
    }), 200 if healthy else 503


@bp.get("/api/config")
def public_config():
    cfg = current_app.config
    return jsonify({
        "app": cfg["APP_NAME"],
        "version": cfg["APP_VERSION"],
        "grafana_url": cfg["GRAFANA_PUBLIC_URL"],
        "prometheus_url": cfg["PROMETHEUS_PUBLIC_URL"],
    })
