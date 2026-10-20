from datetime import timedelta

from helpers import invite, link_path, login, logout, signup, user
from homeinv.extensions import db
from homeinv.models import Invitation, utcnow


def token_of(message):
    return link_path(message).split("/")[-1]


def test_invite_emails_a_link_and_shows_it_once(client, outbox):
    signup(client, "ann@example.com", name="Ann", family_name="The Smiths")
    resp = invite(client, "Bob@Example.com")
    assert b"Invitation sent to bob@example.com" in resp.data

    [message] = outbox
    assert message.to == "bob@example.com"
    assert "Ann invited you to The Smiths" == message.subject
    assert link_path(message).encode() in resp.data  # copyable link for the admin
    assert link_path(message).encode() not in client.get("/family").data  # only once

    stored = db.session.query(Invitation).one()
    assert stored.token_hash != token_of(message)  # only a hash is stored


def test_new_user_joins_through_invite(client, new_client, outbox):
    signup(client, "ann@example.com", family_name="The Smiths")
    invite(client, "bob@example.com")
    bob = new_client()

    landing = bob.get(link_path(outbox[0]))
    assert b"Create an account to join" in landing.data
    resp = signup(bob, "bob@example.com", invite=token_of(outbox[0]))
    assert b"You&#39;re in The Smiths" in resp.data

    bob_user = user("bob@example.com")
    [m] = bob_user.memberships
    assert m.family.name == "The Smiths" and m.role == "member"
    assert bob_user.is_verified
    # Joining doesn't create a family of Bob's own.
    assert len(bob_user.memberships) == 1


def test_invite_signup_must_use_invited_email(client, new_client, outbox):
    signup(client, "ann@example.com")
    invite(client, "bob@example.com")
    resp = signup(new_client(), "mallory@example.com", invite=token_of(outbox[0]))
    assert b"sent to a different email address" in resp.data
    assert user("mallory@example.com") is None


def test_invite_link_works_only_once(client, new_client, outbox):
    signup(client, "ann@example.com")
    invite(client, "bob@example.com")
    signup(new_client(), "bob@example.com", invite=token_of(outbox[0]))
    assert new_client().get(link_path(outbox[0])).status_code == 404


def test_expired_invite_rejected(client, new_client, outbox):
    signup(client, "ann@example.com")
    invite(client, "bob@example.com")
    stored = db.session.query(Invitation).one()
    stored.expires_at = utcnow() - timedelta(minutes=1)
    db.session.commit()

    bob = new_client()
    assert bob.get(link_path(outbox[0])).status_code == 404
    resp = signup(bob, "bob@example.com", invite=token_of(outbox[0]))
    assert b"invalid or has expired" in resp.data
    assert user("bob@example.com") is None


def test_cancelled_invite_rejected(client, new_client, outbox):
    signup(client, "ann@example.com")
    invite(client, "bob@example.com")
    stored = db.session.query(Invitation).one()
    client.post(f"/family/invitations/{stored.id}/revoke")
    assert new_client().get(link_path(outbox[0])).status_code == 404


def test_reinviting_replaces_earlier_link(client, new_client, outbox):
    signup(client, "ann@example.com")
    invite(client, "bob@example.com")
    invite(client, "bob@example.com")
    assert new_client().get(link_path(outbox[0])).status_code == 404
    assert new_client().get(link_path(outbox[1])).status_code == 200


def test_cannot_invite_existing_member(client, outbox):
    signup(client, "ann@example.com")
    resp = invite(client, "ann@example.com")
    assert b"already in" in resp.data
    assert outbox == []


def test_existing_user_accepts_after_logging_in(client, new_client, outbox):
    signup(client, "ann@example.com", family_name="The Smiths")
    bob = new_client()
    signup(bob, "bob@example.com", family_name="Bob's place")
    logout(bob)
    invite(client, "bob@example.com")
    path = link_path(outbox[0])

    assert b"Log in to join" in bob.get(path).data
    login(bob, "bob@example.com", next_url=path)
    resp = bob.post(f"{path}/accept", follow_redirects=True)
    assert b"You joined The Smiths" in resp.data

    names = sorted(m.family.name for m in user("bob@example.com").memberships)
    assert names == ["Bob's place", "The Smiths"]
    assert user("bob@example.com").current_membership.family.name == "The Smiths"


def test_logged_in_as_wrong_account(client, new_client, outbox):
    signup(client, "ann@example.com")
    invite(client, "bob@example.com")
    eve = new_client()
    signup(eve, "eve@example.com")
    path = link_path(outbox[0])
    assert b"this invitation is for" in eve.get(path).data
    eve.post(f"{path}/accept")
    assert len(user("eve@example.com").memberships) == 1


def test_cannot_revoke_other_familys_invitation(client, new_client, outbox):
    signup(client, "ann@example.com")
    invite(client, "bob@example.com")
    stored = db.session.query(Invitation).one()
    eve = new_client()
    signup(eve, "eve@example.com")
    assert eve.post(f"/family/invitations/{stored.id}/revoke").status_code == 404
    db.session.refresh(stored)
    assert stored.revoked_at is None


def test_mail_failure_still_creates_invite_with_link(client, outbox, app):
    from unittest import mock
    signup(client, "ann@example.com")
    with mock.patch.object(app.extensions["email_backend"], "send", side_effect=RuntimeError("down")):
        resp = invite(client, "bob@example.com")
    assert b"couldn&#39;t be sent" in resp.data
    assert b"/invite/" in resp.data
