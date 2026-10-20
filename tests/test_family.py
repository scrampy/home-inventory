from conftest import invite, link_path, signup, user
from homeinv.extensions import db
from homeinv.models import Membership


def join(app_client_factory, outbox, admin_client, email, name=""):
    """Admin invites `email`; a new browser signs up through the emailed link. Returns that client."""
    invite(admin_client, email)
    token = link_path(outbox[-1]).split("/")[-1]
    member = app_client_factory()
    signup(member, email, name=name, invite=token)
    return member


def membership(email):
    return user(email).memberships[0]


def test_admin_can_rename_family(client):
    signup(client, "ann@example.com")
    resp = client.post("/family/rename", data={"name": "The Smiths"}, follow_redirects=True)
    assert b"The Smiths" in resp.data


def test_member_cannot_use_admin_actions(client, new_client, outbox):
    signup(client, "ann@example.com")
    bob = join(new_client, outbox, client, "bob@example.com")
    ann_id = membership("ann@example.com").id

    assert bob.post("/family/rename", data={"name": "Bob's now"}).status_code == 403
    assert bob.post("/family/invite", data={"email": "eve@example.com"}).status_code == 403
    assert bob.post(f"/family/members/{ann_id}/role", data={"role": "member"}).status_code == 403
    assert bob.post(f"/family/members/{ann_id}/remove").status_code == 403


def test_promote_and_demote(client, new_client, outbox):
    signup(client, "ann@example.com")
    join(new_client, outbox, client, "bob@example.com")
    bob_id = membership("bob@example.com").id

    client.post(f"/family/members/{bob_id}/role", data={"role": "admin"})
    assert db.session.get(Membership, bob_id).role == "admin"
    client.post(f"/family/members/{bob_id}/role", data={"role": "member"})
    assert db.session.get(Membership, bob_id).role == "member"


def test_family_always_keeps_one_admin(client, new_client, outbox):
    signup(client, "ann@example.com")
    bob = join(new_client, outbox, client, "bob@example.com")
    bob_id = membership("bob@example.com").id
    ann_id = membership("ann@example.com").id
    client.post(f"/family/members/{bob_id}/role", data={"role": "admin"})

    # Two admins: Bob can demote Ann, then Bob is the only admin and can't leave.
    bob.post(f"/family/members/{ann_id}/role", data={"role": "member"})
    assert db.session.get(Membership, ann_id).role == "member"
    resp = bob.post("/family/leave", follow_redirects=True)
    assert b"only admin" in resp.data
    assert db.session.get(Membership, bob_id) is not None


def test_only_member_cannot_leave(client):
    signup(client, "ann@example.com")
    resp = client.post("/family/leave", follow_redirects=True)
    assert b"only member" in resp.data


def test_admin_removes_member(client, new_client, outbox):
    signup(client, "ann@example.com")
    bob = join(new_client, outbox, client, "bob@example.com")
    bob_id = membership("bob@example.com").id

    client.post(f"/family/members/{bob_id}/remove")
    assert db.session.get(Membership, bob_id) is None
    assert user("bob@example.com").active_family_id is None
    # Bob has no family now, so he's sent to create one.
    resp = bob.get("/family")
    assert resp.status_code == 302 and "/family/new" in resp.headers["Location"]


def test_member_leaves(client, new_client, outbox):
    signup(client, "ann@example.com")
    bob = join(new_client, outbox, client, "bob@example.com")
    bob.post("/family/leave")
    assert user("bob@example.com").memberships == []


def test_create_and_switch_families(client):
    signup(client, "ann@example.com", family_name="Home")
    resp = client.post("/family/new", data={"name": "Cottage"}, follow_redirects=True)
    assert b"Cottage" in resp.data and b"Switch to Home" in resp.data

    home_id = next(m.family_id for m in user("ann@example.com").memberships if m.family.name == "Home")
    resp = client.post(f"/family/switch/{home_id}", follow_redirects=True)
    assert b"Switched to Home" in resp.data and b"Switch to Cottage" in resp.data


def test_cannot_switch_to_someone_elses_family(client, new_client):
    signup(client, "ann@example.com")
    eve = new_client()
    signup(eve, "eve@example.com")
    ann_family = membership("ann@example.com").family_id
    assert eve.post(f"/family/switch/{ann_family}").status_code == 404
    assert user("eve@example.com").active_family_id != ann_family


def test_admin_cannot_touch_other_familys_members(client, new_client):
    """Membership IDs from another family behave as if they don't exist."""
    signup(client, "ann@example.com")
    eve = new_client()
    signup(eve, "eve@example.com")
    ann_id = membership("ann@example.com").id

    assert eve.post(f"/family/members/{ann_id}/role", data={"role": "member"}).status_code == 404
    assert eve.post(f"/family/members/{ann_id}/remove").status_code == 404
    assert db.session.get(Membership, ann_id).role == "admin"


def test_dashboard_lists_only_own_family(client, new_client):
    signup(client, "ann@example.com", name="Ann")
    eve = new_client()
    signup(eve, "eve@example.com", name="Eve")
    page = client.get("/family").data
    assert b"Ann" in page and b"Eve" not in page
