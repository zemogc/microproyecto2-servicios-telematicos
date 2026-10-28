import os


def _bool(name, default=False):
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _mysql_uri():
    user = os.environ.get("MYSQL_USER", "opscenter")
    password = os.environ.get("MYSQL_PASSWORD", "opscenter")
    host = os.environ.get("MYSQL_HOST", "localhost")
    port = os.environ.get("MYSQL_PORT", "3306")
    name = os.environ.get("MYSQL_DB", "opscenter")
    return f"mysql+pymysql://{user}:{password}@{host}:{port}/{name}?charset=utf8mb4"


class Config:
    APP_NAME = "OpsCenter"
    APP_VERSION = os.environ.get("APP_VERSION", "2.0.0")
    SECRET_KEY = os.environ.get("SECRET_KEY", "change-me-in-production")

    SQLALCHEMY_DATABASE_URI = os.environ.get("DATABASE_URL") or _mysql_uri()
    SQLALCHEMY_ENGINE_OPTIONS = {"pool_pre_ping": True, "pool_recycle": 280}
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    SEED_DEMO_DATA = _bool("SEED_DEMO_DATA", True)

    PROMETHEUS_URL = os.environ.get("PROMETHEUS_URL", "http://prometheus:9090")
    GRAFANA_PUBLIC_URL = os.environ.get("GRAFANA_PUBLIC_URL", "")
    PROMETHEUS_PUBLIC_URL = os.environ.get("PROMETHEUS_PUBLIC_URL", "")

    ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
    AI_MODEL = os.environ.get("AI_MODEL", "claude-opus-5-5")
    AI_EFFORT = os.environ.get("AI_EFFORT", "low")


class TestConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = "sqlite://"
    SQLALCHEMY_ENGINE_OPTIONS = {}
    SEED_DEMO_DATA = False
    PROMETHEUS_URL = "http://prometheus.invalid:9090"
    ANTHROPIC_API_KEY = ""
