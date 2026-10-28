import os
import secrets


def _secret(name, default=""):
    """Lee NAME_FILE (secreto montado por Docker) o, en su defecto, la variable NAME."""
    path = os.environ.get(f"{name}_FILE")
    if path and os.path.isfile(path):
        with open(path, encoding="utf-8") as fh:
            value = fh.read().strip()
        if value:
            return value
    return os.environ.get(name, default)


def _bool(name, default=False):
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _mysql_uri():
    user = os.environ.get("MYSQL_USER", "opscenter")
    password = _secret("MYSQL_PASSWORD", "opscenter")
    host = os.environ.get("MYSQL_HOST", "localhost")
    port = os.environ.get("MYSQL_PORT", "3306")
    name = os.environ.get("MYSQL_DB", "opscenter")
    return f"mysql+pymysql://{user}:{password}@{host}:{port}/{name}?charset=utf8mb4"


class Config:
    APP_NAME = "OpsCenter"
    APP_VERSION = os.environ.get("APP_VERSION", "2.0.0")
    # Sin clave configurada se genera una aleatoria: las sesiones se invalidan al reiniciar.
    SECRET_KEY = _secret("SECRET_KEY") or secrets.token_urlsafe(48)

    SESSION_COOKIE_SECURE = _bool("SESSION_COOKIE_SECURE", True)
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_NAME = "opscenter_session"
    PERMANENT_SESSION_LIFETIME = 8 * 3600

    ADMIN_USERNAME = os.environ.get("ADMIN_USERNAME", "admin")
    ADMIN_PASSWORD = _secret("ADMIN_PASSWORD")

    SQLALCHEMY_DATABASE_URI = os.environ.get("DATABASE_URL") or _mysql_uri()
    SQLALCHEMY_ENGINE_OPTIONS = {"pool_pre_ping": True, "pool_recycle": 280}
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    SEED_DEMO_DATA = _bool("SEED_DEMO_DATA", True)

    PROMETHEUS_URL = os.environ.get("PROMETHEUS_URL", "http://prometheus:9090")
    GRAFANA_PUBLIC_URL = os.environ.get("GRAFANA_PUBLIC_URL", "")
    PROMETHEUS_PUBLIC_URL = os.environ.get("PROMETHEUS_PUBLIC_URL", "")

    ANTHROPIC_API_KEY = _secret("ANTHROPIC_API_KEY")
    AI_MODEL = os.environ.get("AI_MODEL", "claude-opus-5-5")
    AI_EFFORT = os.environ.get("AI_EFFORT", "low")


class TestConfig(Config):
    TESTING = True
    SECRET_KEY = "test"
    SESSION_COOKIE_SECURE = False
    ADMIN_PASSWORD = "admin-test-pass"
    SQLALCHEMY_DATABASE_URI = "sqlite://"
    SQLALCHEMY_ENGINE_OPTIONS = {}
    SEED_DEMO_DATA = False
    PROMETHEUS_URL = "http://prometheus.invalid:9090"
    ANTHROPIC_API_KEY = ""
