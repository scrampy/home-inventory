"""App settings, read from environment variables.

APP_ENV picks the profile: "development" (default), "testing" or "production".
Production refuses to start without the settings it needs.
"""

import os


class ConfigError(RuntimeError):
    pass


def _bool(name, default=False):
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in ("1", "true", "yes", "on")


def load_config(instance_path, overrides=None):
    env = (overrides or {}).get("APP_ENV") or os.environ.get("APP_ENV", "development")
    if env not in ("development", "testing", "production"):
        raise ConfigError(f"APP_ENV must be development, testing or production, not {env!r}")

    default_db = "sqlite:///" + os.path.join(instance_path, "homeinv.db").replace("\\", "/")

    # Older names from the first version of the app are accepted too, so
    # variables already set in Coolify keep working.
    def env_var(name, *old_names, default=None):
        for key in (name, *old_names):
            if os.environ.get(key):
                return os.environ[key]
        return default

    config = {
        "APP_ENV": env,
        "SECRET_KEY": env_var("SECRET_KEY", "FLASK_SECRET_KEY"),
        "SQLALCHEMY_DATABASE_URI": os.environ.get("DATABASE_URL", default_db),
        # Base URL used to build links in emails. Never taken from the request's
        # Host header in production, so a forged header can't poison reset links.
        "APP_BASE_URL": (os.environ.get("APP_BASE_URL") or "").rstrip("/") or None,
        "MAILJET_API_KEY": os.environ.get("MAILJET_API_KEY"),
        "MAILJET_SECRET_KEY": os.environ.get("MAILJET_SECRET_KEY"),
        "MAIL_FROM_EMAIL": env_var("MAIL_FROM_EMAIL", "MAILJET_SENDER_EMAIL", default="noreply@example.com"),
        "MAIL_FROM_NAME": env_var("MAIL_FROM_NAME", "MAILJET_SENDER_NAME", default="Home Inventory"),
        # "mailjet", "console" (prints emails to the log) or "memory" (tests).
        "EMAIL_BACKEND": os.environ.get("EMAIL_BACKEND"),
        # Number of reverse proxies in front of the app (Cloudflare Tunnel -> Traefik = 2).
        # Only used to find the visitor's IP address for rate limits.
        "PROXY_HOPS": int(os.environ.get("PROXY_HOPS", "0")),
        "RATELIMIT_ENABLED": _bool("RATELIMIT_ENABLED", True),
        "RATELIMIT_STORAGE_URI": os.environ.get("RATELIMIT_STORAGE_URI", "memory://"),
        "PASSWORD_RESET_MAX_AGE": 60 * 60,  # 1 hour
        "INVITE_MAX_AGE_DAYS": 7,
        "SESSION_COOKIE_HTTPONLY": True,
        "SESSION_COOKIE_SAMESITE": "Lax",
        "REMEMBER_COOKIE_HTTPONLY": True,
        "REMEMBER_COOKIE_SAMESITE": "Lax",
    }

    if env == "development":
        config["SECRET_KEY"] = config["SECRET_KEY"] or "dev-only-not-secret"
        config["EMAIL_BACKEND"] = config["EMAIL_BACKEND"] or (
            "mailjet" if config["MAILJET_API_KEY"] else "console"
        )
    elif env == "testing":
        config.update(
            TESTING=True,
            SECRET_KEY="testing-secret",
            SQLALCHEMY_DATABASE_URI="sqlite://",
            EMAIL_BACKEND="memory",
            APP_BASE_URL="http://testserver.local",
            RATELIMIT_ENABLED=False,
        )
    else:  # production
        config.update(
            SESSION_COOKIE_SECURE=True,
            REMEMBER_COOKIE_SECURE=True,
            EMAIL_BACKEND=config["EMAIL_BACKEND"] or "mailjet",
        )

    if overrides:
        config.update(overrides)

    if config["APP_ENV"] == "production":
        _check_production(config)
    return config


def _check_production(config):
    missing = []
    if not config.get("SECRET_KEY") or len(config["SECRET_KEY"]) < 32:
        missing.append("SECRET_KEY (at least 32 characters)")
    if not config.get("APP_BASE_URL"):
        missing.append("APP_BASE_URL")
    if config.get("EMAIL_BACKEND") == "mailjet":
        for key in ("MAILJET_API_KEY", "MAILJET_SECRET_KEY"):
            if not config.get(key):
                missing.append(key)
        if config.get("MAIL_FROM_EMAIL", "").endswith("@example.com"):
            missing.append("MAIL_FROM_EMAIL")
    if missing:
        raise ConfigError("Missing production settings: " + ", ".join(missing))
