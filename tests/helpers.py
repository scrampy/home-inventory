"""Helpers for tests: act like a user in a browser. Fixtures live in conftest.py."""

import re

from sqlalchemy import select

from homeinv.extensions import db
from homeinv.models import User

PASSWORD = "correct-horse-1"


def signup(client, email, password=PASSWORD, name="", family_name="", invite=None):
    data = {"email": email, "password": password, "confirm": password, "name": name,
            "family_name": family_name}
    url = "/signup"
    if invite:
        data["invite"] = invite
        url += f"?invite={invite}"
    return client.post(url, data=data, follow_redirects=True)


def login(client, email, password=PASSWORD, next_url=None):
    url = "/login" + (f"?next={next_url}" if next_url else "")
    return client.post(url, data={"email": email, "password": password}, follow_redirects=True)


def logout(client):
    return client.post("/logout", follow_redirects=True)


def user(email):
    return db.session.scalar(select(User).filter_by(email=email))


def link_path(message):
    """The path of the first app link in an email (the test base URL is stripped)."""
    match = re.search(r"http://testserver\.local(/\S+)", message.text)
    assert match, f"no link in email: {message.text}"
    return match.group(1)


def invite(client, email):
    return client.post("/family/invite", data={"email": email}, follow_redirects=True)
