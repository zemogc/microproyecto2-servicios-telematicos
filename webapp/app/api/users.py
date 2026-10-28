import re

from flask import Blueprint, jsonify, request
from sqlalchemy import func, or_

from ..extensions import db
from ..models import ROLES, User

bp = Blueprint("users", __name__, url_prefix="/api/users")

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
USERNAME_RE = re.compile(r"^[A-Za-z0-9_.-]{3,30}$")


def _error(message, status, fields=None):
    body = {"error": message}
    if fields:
        body["fields"] = fields
    return jsonify(body), status


def _validate(data, partial=False):
    """Valida el payload. En modo parcial (PUT) la contraseña es opcional."""
    errors = {}
    clean = {}

    name = (data.get("name") or "").strip()
    if not 2 <= len(name) <= 100:
        errors["name"] = "El nombre debe tener entre 2 y 100 caracteres."
    clean["name"] = name

    email = (data.get("email") or "").strip().lower()
    if not EMAIL_RE.match(email) or len(email) > 120:
        errors["email"] = "Correo electrónico no válido."
    clean["email"] = email

    username = (data.get("username") or "").strip()
    if not USERNAME_RE.match(username):
        errors["username"] = "Usuario de 3 a 30 caracteres: letras, números, punto, guion o guion bajo."
    clean["username"] = username

    role = (data.get("role") or "viewer").strip().lower()
    if role not in ROLES:
        errors["role"] = f"Rol no válido. Opciones: {', '.join(ROLES)}."
    clean["role"] = role

    password = data.get("password") or ""
    if password or not partial:
        if len(password) < 8:
            errors["password"] = "La contraseña debe tener al menos 8 caracteres."
        clean["password"] = password

    return clean, errors


def _conflicts(clean, exclude_id=None):
    errors = {}
    query = User.query
    if exclude_id is not None:
        query = query.filter(User.id != exclude_id)
    if query.filter(User.email == clean["email"]).first():
        errors["email"] = "Ya existe un usuario con ese correo."
    if query.filter(User.username == clean["username"]).first():
        errors["username"] = "Ese nombre de usuario ya está en uso."
    return errors


@bp.get("")
def list_users():
    q = (request.args.get("q") or "").strip()
    role = (request.args.get("role") or "").strip().lower()
    page = max(request.args.get("page", 1, type=int), 1)
    per_page = min(max(request.args.get("per_page", 50, type=int), 1), 100)

    query = User.query
    if q:
        like = f"%{q}%"
        query = query.filter(or_(User.name.ilike(like), User.email.ilike(like), User.username.ilike(like)))
    if role in ROLES:
        query = query.filter(User.role == role)

    total = query.count()
    items = query.order_by(User.created_at.desc(), User.id.desc()).offset((page - 1) * per_page).limit(per_page).all()
    return jsonify({
        "items": [u.to_dict() for u in items],
        "total": total,
        "page": page,
        "per_page": per_page,
        "pages": (total + per_page - 1) // per_page,
    })


@bp.get("/stats")
def stats():
    by_role = dict(db.session.query(User.role, func.count(User.id)).group_by(User.role).all())
    return jsonify({
        "total": User.query.count(),
        "by_role": {role: by_role.get(role, 0) for role in ROLES},
    })


@bp.get("/<int:user_id>")
def get_user(user_id):
    user = db.session.get(User, user_id)
    if user is None:
        return _error("Usuario no encontrado.", 404)
    return jsonify(user.to_dict())


@bp.post("")
def create_user():
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return _error("Se esperaba un cuerpo JSON.", 400)

    clean, errors = _validate(data)
    if errors:
        return _error("Datos inválidos.", 422, errors)
    conflicts = _conflicts(clean)
    if conflicts:
        return _error("Usuario duplicado.", 409, conflicts)

    user = User(name=clean["name"], email=clean["email"], username=clean["username"], role=clean["role"])
    user.set_password(clean["password"])
    db.session.add(user)
    db.session.commit()
    return jsonify(user.to_dict()), 201


@bp.put("/<int:user_id>")
def update_user(user_id):
    user = db.session.get(User, user_id)
    if user is None:
        return _error("Usuario no encontrado.", 404)
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return _error("Se esperaba un cuerpo JSON.", 400)

    clean, errors = _validate(data, partial=True)
    if errors:
        return _error("Datos inválidos.", 422, errors)
    conflicts = _conflicts(clean, exclude_id=user.id)
    if conflicts:
        return _error("Usuario duplicado.", 409, conflicts)

    user.name = clean["name"]
    user.email = clean["email"]
    user.username = clean["username"]
    user.role = clean["role"]
    if clean.get("password"):
        user.set_password(clean["password"])
    db.session.commit()
    return jsonify(user.to_dict())


@bp.delete("/<int:user_id>")
def delete_user(user_id):
    user = db.session.get(User, user_id)
    if user is None:
        return _error("Usuario no encontrado.", 404)
    db.session.delete(user)
    db.session.commit()
    return jsonify({"message": "Usuario eliminado."})
