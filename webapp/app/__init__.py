import logging
import time

from flask import Flask, jsonify, render_template, request
from sqlalchemy.exc import OperationalError
from werkzeug.exceptions import HTTPException

from .extensions import db
from .metrics import init_metrics

log = logging.getLogger(__name__)

DEMO_USERS = [
    ("Juan Pérez", "juan@opscenter.dev", "juan", "admin"),
    ("María Gómez", "maria@opscenter.dev", "maria", "devops"),
    ("Andrés Rojas", "andres@opscenter.dev", "andres.r", "developer"),
    ("Laura Castillo", "laura@opscenter.dev", "lcastillo", "developer"),
    ("Sofía Herrera", "sofia@opscenter.dev", "sofi_h", "viewer"),
]


def create_app(config_object="app.config.Config", init_db=False):
    app = Flask(__name__)
    app.config.from_object(config_object)
    app.json.sort_keys = False
    db.init_app(app)

    from .api import insights, system, users

    app.register_blueprint(users.bp)
    app.register_blueprint(insights.bp)
    app.register_blueprint(system.bp)
    init_metrics(app)

    @app.get("/")
    def index():
        return render_template("index.html", config=app.config)

    @app.errorhandler(HTTPException)
    def http_error(exc):
        if request.path.startswith("/api/"):
            return jsonify({"error": exc.description}), exc.code
        return exc

    if init_db:
        bootstrap_database(app)
    return app


def bootstrap_database(app, attempts=30, delay=2):
    """Crea las tablas (esperando a que MySQL esté listo) y siembra datos demo."""
    from .models import User

    with app.app_context():
        for attempt in range(1, attempts + 1):
            try:
                db.create_all()
                break
            except OperationalError:
                log.warning("Base de datos no disponible (intento %s/%s)", attempt, attempts)
                time.sleep(delay)
        else:
            raise RuntimeError("No fue posible conectar con la base de datos")

        if app.config["SEED_DEMO_DATA"] and User.query.count() == 0:
            for name, email, username, role in DEMO_USERS:
                user = User(name=name, email=email, username=username, role=role)
                user.set_password("Demo1234!")
                db.session.add(user)
            db.session.commit()
            log.info("Sembrados %s usuarios demo", len(DEMO_USERS))
