from datetime import datetime, timedelta, timezone
from unittest import mock

from helpers import PASSWORD, link_path, login, logout, signup, user

NEW_PASSWORD = "brand-new-pass-2"


def request_reset(client, email):
    return client.post("/reset-password", data={"email": email}, follow_redirects=True)


def test_reset_flow_changes_password(client, outbox):
    signup(client, "ann@example.com")
    logout(client)

    resp = request_reset(client, "ann@example.com")
    assert b"Check your email" in resp.data
    [message] = outbox
    assert message.to == "ann@example.com"
    path = link_path(message)
    # The token must never appear on the page, only in the email.
    assert path.split("/")[-1].encode() not in resp.data

    resp = client.post(path, data={"password": NEW_PASSWORD, "confirm": NEW_PASSWORD}, follow_redirects=True)
    assert b"Your password has been changed" in resp.data
    assert b"incorrect" in login(client, "ann@example.com", PASSWORD).data
    assert login(client, "ann@example.com", NEW_PASSWORD).request.path == "/items"


def test_unknown_email_gets_same_page_and_no_email(client, outbox):
    resp = request_reset(client, "nobody@example.com")
    assert b"Check your email" in resp.data
    assert outbox == []


def test_reset_link_works_only_once(client, outbox):
    signup(client, "ann@example.com")
    logout(client)
    request_reset(client, "ann@example.com")
    path = link_path(outbox[0])
    client.post(path, data={"password": NEW_PASSWORD, "confirm": NEW_PASSWORD})

    resp = client.get(path, follow_redirects=True)
    assert b"invalid, expired or already used" in resp.data


def test_reset_link_expires(client, outbox, app):
    signup(client, "ann@example.com")
    logout(client)
    request_reset(client, "ann@example.com")
    path = link_path(outbox[0])

    later = datetime.now(timezone.utc) + timedelta(seconds=app.config["PASSWORD_RESET_MAX_AGE"] + 5)
    with mock.patch("itsdangerous.timed.time.time", return_value=later.timestamp()):
        resp = client.get(path, follow_redirects=True)
    assert b"invalid, expired or already used" in resp.data


def test_tampered_token_rejected(client):
    resp = client.get("/reset-password/not-a-real-token", follow_redirects=True)
    assert b"invalid, expired or already used" in resp.data


def test_reset_signs_out_other_sessions(client, new_client, outbox):
    signup(client, "ann@example.com")  # stays logged in on this "device"
    other = new_client()
    request_reset(other, "ann@example.com")
    other.post(link_path(outbox[0]), data={"password": NEW_PASSWORD, "confirm": NEW_PASSWORD})

    resp = client.get("/family")
    assert resp.status_code == 302 and "/login" in resp.headers["Location"]


def test_reset_link_uses_configured_base_url_not_host_header(client, outbox):
    signup(client, "ann@example.com")
    logout(client)
    client.post("/reset-password", data={"email": "ann@example.com"},
                headers={"Host": "attacker.example"})
    assert "attacker.example" not in outbox[0].text
    assert "http://testserver.local/reset-password/" in outbox[0].text


def test_no_debug_mode_on_reset_page(client, outbox):
    signup(client, "ann@example.com")
    logout(client)
    resp = client.post("/reset-password?debug=1", data={"email": "ann@example.com"})
    token = link_path(outbox[0]).split("/")[-1]
    assert token.encode() not in resp.data
    assert b"Debug" not in resp.data


def test_mail_failure_still_shows_same_page(client, app):
    signup(client, "ann@example.com")
    logout(client)
    with mock.patch.object(app.extensions["email_backend"], "send", side_effect=RuntimeError("down")):
        resp = request_reset(client, "ann@example.com")
    assert resp.status_code == 200 and b"Check your email" in resp.data
    assert user("ann@example.com") is not None
