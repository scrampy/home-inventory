from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required, login_user, logout_user
from sqlalchemy import select
from werkzeug.security import check_password_hash, generate_password_hash

from .email import send_email
from .extensions import db, limiter
from .forms import ActionForm, LoginForm, ResetPasswordForm, ResetRequestForm, SignupForm
from .models import (ROLE_ADMIN, ROLE_MEMBER, Family, Invitation, Membership, User,
                     normalize_email, utcnow)
from .security import external_url, make_reset_token, safe_next_url, user_from_reset_token

bp = Blueprint("auth", __name__)

# Compared against when the email isn't registered, so a failed login takes the
# same time whether or not the account exists.
_DUMMY_HASH = generate_password_hash("not-a-real-password")


def find_user(email):
    return db.session.scalar(select(User).filter_by(email=normalize_email(email)))


def default_family_name(user):
    first = (user.name or "").split()[0] if user.name else user.email.split("@")[0]
    return f"{first}'s family"


@bp.route("/signup", methods=["GET", "POST"])
@limiter.limit("10 per hour", methods=["POST"])
def signup():
    if current_user.is_authenticated:
        return redirect(url_for("find.index"))

    form = SignupForm()
    token = request.args.get("invite") or form.invite.data
    invitation = Invitation.find_by_token(token) if token else None
    if invitation and not invitation.is_pending:
        invitation = None
    if token and not invitation:
        flash("That invitation link is invalid or has expired. You can still create your own family.", "warning")
        return redirect(url_for("auth.signup"))
    if invitation and request.method == "GET":
        form.email.data = invitation.email
        form.invite.data = token

    if form.validate_on_submit():
        email = normalize_email(form.email.data)
        if invitation and email != invitation.email:
            form.email.errors.append("This invitation was sent to a different email address.")
        elif find_user(email):
            form.email.errors.append("That email already has an account. Log in instead.")
        else:
            user = User(email=email, name=(form.name.data or "").strip())
            user.set_password(form.password.data)
            db.session.add(user)
            if invitation:
                family = invitation.family
                role = ROLE_MEMBER
                invitation.accepted_at = utcnow()
                user.is_verified = True  # they clicked a link sent to this address
            else:
                family = Family(name=(form.family_name.data or "").strip() or default_family_name(user))
                db.session.add(family)
                role = ROLE_ADMIN
            db.session.add(Membership(user=user, family=family, role=role))
            db.session.flush()
            user.active_family_id = family.id
            db.session.commit()
            login_user(user)
            flash(f"Welcome! You're in {family.name}.", "success")
            return redirect(url_for("family.dashboard"))

    return render_template("auth/signup.html", form=form, invitation=invitation)


@bp.route("/login", methods=["GET", "POST"])
@limiter.limit("10 per minute;50 per hour", methods=["POST"])
def login():
    next_url = safe_next_url(request.args.get("next"), url_for("find.index"))
    if current_user.is_authenticated:
        return redirect(next_url)

    form = LoginForm()
    if form.validate_on_submit():
        user = find_user(form.email.data)
        if user is None:
            check_password_hash(_DUMMY_HASH, form.password.data)
        elif user.check_password(form.password.data):
            login_user(user, remember=form.remember.data)
            return redirect(next_url)
        form.password.errors.append("Email or password is incorrect.")
    return render_template("auth/login.html", form=form)


@bp.route("/logout", methods=["POST"])
@login_required
def logout():
    if ActionForm().validate_on_submit():
        logout_user()
        flash("You've logged out.", "info")
    return redirect(url_for("auth.login"))


@bp.route("/reset-password", methods=["GET", "POST"])
@limiter.limit("5 per hour", methods=["POST"])
def reset_request():
    form = ResetRequestForm()
    if form.validate_on_submit():
        user = find_user(form.email.data)
        if user:
            link = external_url("auth.reset_password", token=make_reset_token(user))
            send_email(user.email, "Reset your Home Inventory password", "reset_password",
                       user=user, link=link)
        # Same answer either way, so this page can't be used to find out who has an account.
        return render_template("auth/reset_sent.html", email=normalize_email(form.email.data))
    return render_template("auth/reset_request.html", form=form)


@bp.route("/reset-password/<token>", methods=["GET", "POST"])
def reset_password(token):
    user = user_from_reset_token(token)
    if user is None:
        flash("That reset link is invalid, expired or already used. Request a new one.", "warning")
        return redirect(url_for("auth.reset_request"))

    form = ResetPasswordForm()
    if form.validate_on_submit():
        user.set_password(form.password.data)  # also signs out every existing session
        db.session.commit()
        logout_user()
        flash("Your password has been changed. Log in with the new one.", "success")
        return redirect(url_for("auth.login"))
    return render_template("auth/reset_password.html", form=form)
