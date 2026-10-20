from helpers import PASSWORD, login, logout, signup, user


def test_signup_creates_family_with_user_as_admin(client):
    resp = signup(client, "Ann@Example.com", name="Ann Smith")
    assert resp.status_code == 200
    assert b"Ann&#39;s family" in resp.data

    ann = user("ann@example.com")  # stored lowercased
    assert ann.name == "Ann Smith"
    [membership] = ann.memberships
    assert membership.role == "admin"
    assert ann.active_family_id == membership.family_id


def test_signup_uses_given_family_name(client):
    resp = signup(client, "ann@example.com", family_name="The Smiths")
    assert b"The Smiths" in resp.data


def test_signup_rejects_duplicate_email_regardless_of_case(client, new_client):
    signup(client, "ann@example.com")
    resp = signup(new_client(), "ANN@example.com")
    assert b"already has an account" in resp.data


def test_signup_rejects_short_password_and_mismatch(client):
    resp = client.post("/signup", data={"email": "a@example.com", "password": "short", "confirm": "short"})
    assert b"at least 8 characters" in resp.data
    resp = client.post("/signup", data={"email": "a@example.com", "password": "longenough1", "confirm": "different1"})
    assert b"Passwords don&#39;t match" in resp.data
    assert user("a@example.com") is None


def test_login_and_logout(client):
    signup(client, "ann@example.com")
    logout(client)
    assert client.get("/family").status_code == 302

    resp = login(client, "ann@example.com")
    assert resp.status_code == 200 and resp.request.path == "/inventory"
    logout(client)
    assert client.get("/family").status_code == 302


def test_login_wrong_password_and_unknown_email_get_same_message(client):
    signup(client, "ann@example.com")
    logout(client)
    wrong = login(client, "ann@example.com", "wrong-password")
    unknown = login(client, "nobody@example.com", PASSWORD)
    assert b"Email or password is incorrect." in wrong.data
    assert b"Email or password is incorrect." in unknown.data


def test_logout_requires_post(client):
    signup(client, "ann@example.com")
    assert client.get("/logout").status_code == 405


def test_pages_require_login(client):
    for path in ("/family", "/family/new"):
        resp = client.get(path)
        assert resp.status_code == 302
        assert "/login" in resp.headers["Location"]


def test_login_next_only_redirects_within_site(client):
    signup(client, "ann@example.com")
    logout(client)
    resp = client.post("/login?next=https://evil.example/", data={"email": "ann@example.com", "password": PASSWORD})
    assert resp.headers["Location"] == "/"
    logout(client)
    resp = client.post("/login?next=//evil.example/", data={"email": "ann@example.com", "password": PASSWORD})
    assert resp.headers["Location"] == "/"
    logout(client)
    resp = client.post("/login?next=/family/new", data={"email": "ann@example.com", "password": PASSWORD})
    assert resp.headers["Location"] == "/family/new"
