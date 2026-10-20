from flask import Blueprint, abort, current_app, flash, redirect, render_template, request, session, url_for
from flask_login import current_user, login_required
from sqlalchemy import select

from .email import send_email
from .extensions import db, limiter
from .forms import ActionForm, FamilyNameForm, InviteForm, RoleForm
from .models import (ROLE_ADMIN, ROLE_MEMBER, Family, Invitation, Membership, User,
                     normalize_email, utcnow)
from .security import admin_required, current_membership, external_url, family_required, safe_next_url

bp = Blueprint("family", __name__)


def _family_membership_or_404(membership_id):
    """A membership in the current family. Other families' IDs look like they don't exist."""
    membership = db.session.get(Membership, membership_id)
    if membership is None or membership.family_id != current_membership().family_id:
        abort(404)
    return membership


def _require_post_form():
    if not ActionForm().validate_on_submit():
        abort(400)


@bp.route("/family")
@family_required
def dashboard():
    me = current_membership()
    family = me.family
    pending = []
    if me.is_admin:
        pending = [i for i in family.invitations if i.is_pending]
        pending.sort(key=lambda i: i.created_at, reverse=True)
    other_families = [m for m in current_user.memberships if m.family_id != family.id]
    return render_template(
        "family/dashboard.html",
        family=family,
        me=me,
        members=family.memberships,
        pending=pending,
        other_families=other_families,
        rename_form=FamilyNameForm(name=family.name),
        invite_form=InviteForm(),
        action_form=ActionForm(),
        invite_link=session.pop("invite_link", None),
    )


@bp.route("/family/new", methods=["GET", "POST"])
@login_required
def new():
    form = FamilyNameForm()
    if form.validate_on_submit():
        family = Family(name=form.name.data.strip())
        db.session.add(family)
        db.session.add(Membership(user=current_user, family=family, role=ROLE_ADMIN))
        db.session.flush()
        current_user.active_family_id = family.id
        db.session.commit()
        flash(f"Created {family.name}. You're its admin.", "success")
        return redirect(safe_next_url(request.args.get("next"), url_for("family.dashboard")))
    return render_template("family/new.html", form=form, has_family=current_membership() is not None)


@bp.route("/family/rename", methods=["POST"])
@admin_required
def rename():
    form = FamilyNameForm()
    if form.validate_on_submit():
        current_membership().family.name = form.name.data.strip()
        db.session.commit()
        flash("Family renamed.", "success")
    else:
        flash("Give the family a name.", "danger")
    return redirect(url_for("family.dashboard"))


@bp.route("/family/invite", methods=["POST"])
@limiter.limit("30 per hour")
@admin_required
def invite():
    family = current_membership().family
    form = InviteForm()
    if not form.validate_on_submit():
        for error in form.email.errors:
            flash(error, "danger")
        return redirect(url_for("family.dashboard"))

    email = normalize_email(form.email.data)
    existing_user = db.session.scalar(select(User).filter_by(email=email))
    if existing_user and existing_user.membership_in(family.id):
        flash(f"{email} is already in {family.name}.", "warning")
        return redirect(url_for("family.dashboard"))

    # A new invite replaces any earlier one to the same address.
    for old in family.invitations:
        if old.email == email and old.is_pending:
            old.revoked_at = utcnow()

    invitation, token = Invitation.create(
        family, email, current_user, current_app.config["INVITE_MAX_AGE_DAYS"]
    )
    db.session.add(invitation)
    db.session.commit()

    link = external_url("family.invite_landing", token=token)
    sent = send_email(
        email, f"{current_user.display_name} invited you to {family.name}", "invite",
        inviter=current_user, family=family, link=link, days=current_app.config["INVITE_MAX_AGE_DAYS"],
    )
    if sent:
        flash(f"Invitation sent to {email}.", "success")
    else:
        flash(f"The invitation email to {email} couldn't be sent. Share the link below instead.", "warning")
    # Shown once so the admin can also send it by text message.
    session["invite_link"] = {"email": email, "link": link}
    return redirect(url_for("family.dashboard"))


@bp.route("/family/invitations/<int:invitation_id>/revoke", methods=["POST"])
@admin_required
def revoke_invitation(invitation_id):
    _require_post_form()
    invitation = db.session.get(Invitation, invitation_id)
    if invitation is None or invitation.family_id != current_membership().family_id:
        abort(404)
    if invitation.is_pending:
        invitation.revoked_at = utcnow()
        db.session.commit()
        flash(f"Invitation to {invitation.email} cancelled.", "info")
    return redirect(url_for("family.dashboard"))


@bp.route("/family/members/<int:membership_id>/role", methods=["POST"])
@admin_required
def change_role(membership_id):
    target = _family_membership_or_404(membership_id)
    form = RoleForm()
    if not form.validate_on_submit():
        abort(400)
    new_role = form.role.data
    if target.role == ROLE_ADMIN and new_role == ROLE_MEMBER and target.family.admin_count() <= 1:
        flash("A family needs at least one admin. Make someone else an admin first.", "danger")
        return redirect(url_for("family.dashboard"))
    target.role = new_role
    db.session.commit()
    flash(f"{target.user.display_name} is now {'an admin' if new_role == ROLE_ADMIN else 'a member'}.", "success")
    return redirect(url_for("family.dashboard"))


@bp.route("/family/members/<int:membership_id>/remove", methods=["POST"])
@admin_required
def remove_member(membership_id):
    _require_post_form()
    target = _family_membership_or_404(membership_id)
    if target.user_id == current_user.id:
        flash("To leave the family yourself, use Leave family.", "warning")
        return redirect(url_for("family.dashboard"))
    name = target.user.display_name
    _delete_membership(target)
    flash(f"Removed {name} from the family.", "success")
    return redirect(url_for("family.dashboard"))


@bp.route("/family/leave", methods=["POST"])
@family_required
def leave():
    _require_post_form()
    me = current_membership()
    family = me.family
    if me.is_admin and family.admin_count() <= 1:
        if len(family.memberships) == 1:
            flash("You're the only member of this family, so you can't leave it.", "danger")
        else:
            flash("You're the only admin. Make someone else an admin before leaving.", "danger")
        return redirect(url_for("family.dashboard"))
    _delete_membership(me)
    flash(f"You left {family.name}.", "info")
    return redirect(url_for("find.index"))


def _delete_membership(membership):
    user = membership.user
    if user.active_family_id == membership.family_id:
        user.active_family_id = None
    db.session.delete(membership)
    db.session.commit()


@bp.route("/family/switch/<int:family_id>", methods=["POST"])
@login_required
def switch(family_id):
    _require_post_form()
    membership = current_user.membership_in(family_id)
    if membership is None:
        abort(404)
    current_user.active_family_id = family_id
    db.session.commit()
    flash(f"Switched to {membership.family.name}.", "info")
    return redirect(url_for("family.dashboard"))


@bp.route("/invite/<token>")
def invite_landing(token):
    invitation = Invitation.find_by_token(token)
    if invitation is None or not invitation.is_pending:
        return render_template("family/invite.html", state="invalid"), 404

    if not current_user.is_authenticated:
        has_account = db.session.scalar(select(User.id).filter_by(email=invitation.email)) is not None
        state = "login" if has_account else "signup"
    elif current_user.email != invitation.email:
        state = "wrong_account"
    elif current_user.membership_in(invitation.family_id):
        state = "already_member"
    else:
        state = "accept"
    return render_template("family/invite.html", state=state, invitation=invitation, token=token,
                           form=ActionForm())


@bp.route("/invite/<token>/accept", methods=["POST"])
@login_required
def accept_invite(token):
    _require_post_form()
    invitation = Invitation.find_by_token(token)
    if invitation is None or not invitation.is_pending or current_user.email != invitation.email:
        return redirect(url_for("family.invite_landing", token=token))
    if not current_user.membership_in(invitation.family_id):
        db.session.add(Membership(user=current_user, family_id=invitation.family_id, role=ROLE_MEMBER))
    invitation.accepted_at = utcnow()
    current_user.is_verified = True
    current_user.active_family_id = invitation.family_id
    db.session.commit()
    flash(f"You joined {invitation.family.name}.", "success")
    return redirect(url_for("family.dashboard"))
