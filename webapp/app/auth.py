import hashlib
import hmac
import logging
import secrets
from functools import wraps
from urllib.parse import urlparse

from flask import (Blueprint, current_app, jsonify, redirect, render_template, request, session,
                   url_for)

from werkzeug.security import check_password_hash, generate_password_hash

from .extensions import db
from .models import User

log = logging.getLogger(__name__)

bp = Blueprint("auth", __name__)

# Rutas accesibles sin sesión. Todo lo demás exige iniciar sesión.
PUBLIC_ENDPOINTS = {"auth.login", "auth.login_post", "system.health", "metrics", "static"}
UNSAFE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}
# Hash de relleno: el tiempo de respuesta no revela si el usuario existe.
_DUMMY_HASH = generate_password_hash(secrets.token_hex(16))


def _fingerprint(user):
    # Cambia al cambiar la contraseña, lo que invalida las sesiones abiertas.
    return hashlib.sha256(user.password_hash.encode()).hexdigest()[:16]


def login_user(user):
    session.clear()
    session.permanent = True
    session["uid"] = user.id
    session["fp"] = _fingerprint(user)


def current_user():
    # Se guarda en la petición (no en g) para que nunca se comparta entre peticiones.
    env = request.environ
    if "opscenter.user" not in env:
        env["opscenter.user"] = None
        uid = session.get("uid")
        if uid is not None:
            user = db.session.get(User, uid)
            if user and hmac.compare_digest(session.get("fp", ""), _fingerprint(user)):
                env["opscenter.user"] = user
            else:
                session.clear()
    return env["opscenter.user"]


def admin_required(view):
    @wraps(view)
    def wrapper(*args, **kwargs):
        user = current_user()
        if user is None or user.role != "admin":
            return jsonify({"error": "Solo un administrador puede realizar esta acción."}), 403
        return view(*args, **kwargs)
    return wrapper


def _same_origin():
    """Defensa CSRF: las peticiones que modifican datos deben venir del mismo sitio."""
    origin = request.headers.get("Origin") or request.headers.get("Referer")
    if not origin:
        return True  # clientes no navegador (curl, tests); la cookie SameSite cubre al navegador
    return urlparse(origin).hostname == request.host.split(":")[0]


def init_auth(app):
    app.register_blueprint(bp)

    @app.before_request
    def guard():
        if request.method in UNSAFE_METHODS and not _same_origin():
            return jsonify({"error": "Origen no permitido."}), 403
        if request.endpoint in PUBLIC_ENDPOINTS:
            return None
        if current_user() is None:
            if request.path.startswith("/api/"):
                return jsonify({"error": "Inicia sesión para continuar."}), 401
            return redirect(url_for("auth.login"))
        return None

    @app.context_processor
    def inject_user():
        return {"current_user": current_user()}


def ensure_admin(app):
    """Garantiza que exista la cuenta de administrador inicial."""
    username = app.config["ADMIN_USERNAME"]
    if User.query.filter_by(username=username).first():
        return
    password = app.config["ADMIN_PASSWORD"]
    if not password:
        password = secrets.token_urlsafe(12)
        log.warning("ADMIN_PASSWORD no definida. Contraseña generada para '%s': %s", username, password)
    admin = User(name="Administrador", email=f"{username}@opscenter.local", username=username, role="admin")
    admin.set_password(password)
    db.session.add(admin)
    db.session.commit()
    log.info("Creada la cuenta de administrador '%s'", username)


@bp.get("/login")
def login():
    if current_user():
        return redirect(url_for("index"))
    return render_template("login.html", config=current_app.config, error=None)


@bp.post("/login")
def login_post():
    username = (request.form.get("username") or "").strip()
    password = request.form.get("password") or ""
    user = User.query.filter_by(username=username).first()
    if user is None:
        check_password_hash(_DUMMY_HASH, password)
    if user is None or not user.check_password(password):
        log.warning("Inicio de sesión fallido para '%s' desde %s", username[:30], request.remote_addr)
        return render_template("login.html", config=current_app.config, username=username,
                               error="Usuario o contraseña incorrectos."), 401
    login_user(user)
    return redirect(url_for("index"))


@bp.post("/logout")
def logout():
    session.clear()
    return redirect(url_for("auth.login"))


@bp.get("/api/auth/me")
def me():
    return jsonify(current_user().to_dict())
