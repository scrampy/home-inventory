"""Tokens, safe redirects, links for emails, and family access checks."""

from functools import wraps
import hashlib
import hmac
from urllib.parse import urlsplit

from flask import abort, current_app, flash, g, redirect, request, url_for
from flask_login import current_user, login_required
from itsdangerous import BadSignature, URLSafeTimedSerializer
from sqlalchemy import select

from .extensions import db
from .models import User, name_key

RESET_SALT = "password-reset"


# --- Password reset tokens -------------------------------------------------

def _password_fingerprint(user):
    # Part of the token, so the link stops working once the password changes.
    return hashlib.sha256(user.password_hash.encode()).hexdigest()[:16]


def _serializer():
    return URLSafeTimedSerializer(current_app.config["SECRET_KEY"], salt=RESET_SALT)


def make_reset_token(user):
    return _serializer().dumps({"uid": user.id, "fp": _password_fingerprint(user)})


def user_from_reset_token(token):
    """The user a reset token belongs to, or None if it's invalid, expired or already used."""
    try:
        data = _serializer().loads(token, max_age=current_app.config["PASSWORD_RESET_MAX_AGE"])
    except BadSignature:  # also covers SignatureExpired
        return None
    if not isinstance(data, dict):
        return None
    user = db.session.get(User, data.get("uid"))
    if not user or not hmac.compare_digest(str(data.get("fp", "")), _password_fingerprint(user)):
        return None
    return user


# --- URLs ------------------------------------------------------------------

def external_url(endpoint, **values):
    """Absolute URL for emails, built from APP_BASE_URL rather than the request's Host header."""
    base = current_app.config.get("APP_BASE_URL")
    if base:
        return base + url_for(endpoint, **values)
    return url_for(endpoint, _external=True, **values)


def safe_next_url(target, fallback):
    """Only follow `next` to a path on this site."""
    if target and target.startswith("/") and not target.startswith("//") and "\\" not in target:
        parts = urlsplit(target)
        if not parts.scheme and not parts.netloc:
            return target
    return fallback


# --- Family access ---------------------------------------------------------

def current_membership():
    """The signed-in user's membership in the family they're working in (cached per request)."""
    if not current_user.is_authenticated:
        return None
    if "membership" not in g:
        g.membership = current_user.current_membership
    return g.membership


def family_required(view):
    """Signed in and a member of a family; otherwise send them to create one."""

    @wraps(view)
    @login_required
    def wrapped(*args, **kwargs):
        if current_membership() is None:
            flash("Create a family to get started, or ask a family admin to invite you.", "info")
            return redirect(url_for("family.new", next=request.path))
        return view(*args, **kwargs)

    return wrapped


def admin_required(view):
    """Signed in and an admin of the current family."""

    @wraps(view)
    @family_required
    def wrapped(*args, **kwargs):
        if not current_membership().is_admin:
            abort(403)
        return view(*args, **kwargs)

    return wrapped


# --- Family-owned rows -----------------------------------------------------
# Every query for family data goes through these, so one family can never
# read or change another's rows, even by guessing IDs.

def current_family_id():
    return current_membership().family_id


def family_select(model):
    """SELECT of the current family's rows of `model`, ordered by name."""
    return select(model).where(model.family_id == current_family_id()).order_by(model.name_key)


def family_rows(model):
    return db.session.scalars(family_select(model)).all()


def get_for_family_or_404(model, row_id):
    """The current family's row with this ID; another family's row looks like it doesn't exist."""
    row = db.session.get(model, row_id)
    if row is None or row.family_id != current_family_id():
        abort(404)
    return row


def name_in_use(model, name, exclude_id=None):
    """The current family's row of `model` already using this name (ignoring case and spacing)."""
    query = select(model).where(model.family_id == current_family_id(), model.name_key == name_key(name))
    if exclude_id is not None:
        query = query.where(model.id != exclude_id)
    return db.session.scalar(query)
