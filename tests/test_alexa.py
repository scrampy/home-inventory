"""Alexa: linking an Amazon account, the voice commands, and checking requests come from Amazon (alexa.py)."""

import base64
from datetime import datetime, timedelta, timezone
import json
import re

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from cryptography.x509.oid import ExtendedKeyUsageOID, NameOID
import pytest
from sqlalchemy import select

from helpers import FreshContextClient, signup
from homeinv import alexa_verify, create_app
from homeinv.config import ConfigError, load_config
from homeinv.extensions import db
from homeinv.models import AlexaLink, Item, ListEntry, Location, Stock

SKILL = "amzn1.ask.skill.test-skill"
ANN = "amzn1.ask.account.ann"
CERT_URL = "https://s3.amazonaws.com/echo.api/echo-api-cert-test.pem"


def make_app(**config):
    app = create_app({"APP_ENV": "testing", "WTF_CSRF_ENABLED": False, "ALEXA_SKILL_ID": SKILL,
                      "ALEXA_VERIFY_REQUESTS": False, **config})
    app.test_client_class = FreshContextClient
    return app


@pytest.fixture
def app():
    app = make_app()
    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()


def envelope(intent=None, user=ANN, attributes=None, request_type=None, skill=SKILL, **slots):
    request = {"type": request_type or ("IntentRequest" if intent else "LaunchRequest"),
               "requestId": "req-1", "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
               "locale": "en-CA"}
    if intent:
        request["intent"] = {"name": intent, "confirmationStatus": "NONE",
                             "slots": {k: {"name": k, "value": v} for k, v in slots.items()}}
    return {"version": "1.0",
            "session": {"new": True, "sessionId": "s-1", "attributes": attributes or {},
                        "application": {"applicationId": skill}, "user": {"userId": user}},
            "context": {"System": {"application": {"applicationId": skill}, "user": {"userId": user}}},
            "request": request}


def ask(client, intent=None, **kwargs):
    """What Alexa would say back, and the whole reply."""
    resp = client.post("/alexa", json=envelope(intent, **kwargs))
    assert resp.status_code == 200, resp.data
    body = resp.get_json()
    return body["response"].get("outputSpeech", {}).get("text", ""), body


def places():
    return {p.name: p.id for p in db.session.scalars(select(Location))}


def stock(name, place_id):
    return db.session.scalar(select(Stock).join(Stock.item).where(Item.name == name, Stock.location_id == place_id))


def put(client, place_id, name, quantity):
    client.post("/inventory/add", data={"location_id": place_id, "name": name})
    client.post(f"/inventory/{stock(name, place_id).id}/set", data={"quantity": str(quantity)})


def link(client, user=ANN):
    """Get a code on the Alexa page and say it."""
    client.post("/more/alexa/code")
    page = client.get("/more/alexa").data.decode()
    code = re.search(r'letter-spacing: \.15em">(\d{6})<', page).group(1)
    return ask(client, "LinkIntent", user=user, code=code)[0]


@pytest.fixture
def home(client):
    """Ann's family, linked to her Alexa: Cold Room (with a Top Shelf), Pantry, two Freezers."""
    signup(client, "ann@example.com", name="Ann", family_name="Ann's family")
    for name in ("Kitchen", "Basement", "Pantry"):
        client.post("/places/add", data={"name": name})
    ids = places()
    client.post("/places/add", data={"name": "Cold Room", "parent_id": ids["Basement"]})
    client.post("/places/add", data={"name": "Freezer", "parent_id": ids["Basement"]})
    client.post("/places/add", data={"name": "Freezer", "parent_id": ids["Kitchen"]})
    ids = places()
    client.post("/places/add", data={"name": "Top Shelf", "parent_id": ids["Cold Room"]})
    ids = places()
    kitchen_freezer = db.session.scalar(select(Location.id).filter_by(name="Freezer", parent_id=ids["Kitchen"]))
    basement_freezer = db.session.scalar(select(Location.id).filter_by(name="Freezer", parent_id=ids["Basement"]))
    ids["Kitchen Freezer"], ids["Basement Freezer"] = kitchen_freezer, basement_freezer
    put(client, ids["Cold Room"], "Coffee", 3)
    put(client, ids["Top Shelf"], "Coffee", 1)
    put(client, ids["Pantry"], "Coffee", 2)
    put(client, ids["Kitchen Freezer"], "Peas", 1)
    put(client, ids["Basement Freezer"], "Peas", 2)
    put(client, ids["Pantry"], "Rice", 1)
    assert "now linked to Ann's family" in link(client)
    return ids


# --- Linking ---------------------------------------------------------------

def test_an_unlinked_alexa_is_told_how_to_link(client):
    signup(client, "ann@example.com", name="Ann")
    text, _ = ask(client, "HowManyIntent", item="coffee")
    assert "isn't linked to a family yet" in text and "my code is" in text
    assert "Get a code" in client.get("/more/alexa").data.decode()


def test_a_code_links_once_and_unlinking_stops_it(client, home):
    assert db.session.scalar(select(AlexaLink)).linked_at is not None
    assert "Coffee" in ask(client, "HowManyIntent", item="coffee")[0]
    page = client.get("/more/alexa").data.decode()
    assert 'data-testid="alexa-linked"' in page and "Linked today by Ann" in page

    # Another Amazon account can't reuse the code.
    assert "didn't work" in ask(client, "LinkIntent", user="amzn1.ask.account.bob", code="123456")[0]

    link_id = db.session.scalar(select(AlexaLink.id))
    client.post(f"/more/alexa/{link_id}/unlink")
    assert "isn't linked" in ask(client, "HowManyIntent", item="coffee")[0]


def test_codes_expire_and_a_new_one_replaces_the_old(client):
    signup(client, "ann@example.com", name="Ann")
    client.post("/more/alexa/code")
    first = db.session.scalar(select(AlexaLink))
    first.code_expires_at = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(seconds=1)
    db.session.commit()
    page = client.get("/more/alexa").data.decode()
    assert 'data-testid="alexa-code"' not in page  # an expired code isn't shown

    client.post("/more/alexa/code")
    assert db.session.query(AlexaLink).count() == 1  # the old one is gone
    assert "now linked" in link(client)


def test_alexa_only_sees_its_own_family(client, home, new_client):
    eve = new_client()
    signup(eve, "eve@example.com", name="Eve")
    eve.post("/places/add", data={"name": "Shed"})
    put(eve, places()["Shed"], "Secret Jam", 4)
    assert "couldn't find anything called secret jam" in ask(client, "HowManyIntent", item="secret jam")[0]
    assert "couldn't find a place called shed" in ask(client, "HowManyIntent", item="coffee", place="shed")[0]


# --- How many / where ------------------------------------------------------

def test_how_many_everywhere_matches_plurals(client, home):
    text, body = ask(client, "HowManyIntent", item="coffees")
    assert text == ("Coffee: 6 in all. 3 in the Cold Room, 2 in the Pantry "
                    "and 1 in the Top Shelf.")
    assert body["response"]["shouldEndSession"] is True


def test_how_many_in_a_place_includes_the_places_inside_it(client, home):
    assert ask(client, "HowManyIntent", item="coffees", place="cold room")[0] == "Coffee: 4 in the Cold Room."
    assert ask(client, "HowManyIntent", item="coffee", place="the pantry")[0] == "Coffee: 2 in the Pantry."


def test_two_places_with_one_name(client, home):
    text = ask(client, "HowManyIntent", item="peas", place="freezer")[0]
    assert text == "Peas: 3 in the Basement Freezer and the Kitchen Freezer."
    assert ask(client, "HowManyIntent", item="peas", place="basement freezer")[0] == \
        "Peas: 2 in the Basement Freezer."


def test_none_in_that_place_says_where_there_is_some(client, home):
    text = ask(client, "HowManyIntent", item="rice", place="cold room")[0]
    assert text == "There's no Rice in the Cold Room. There's 1 in the Pantry."


def test_out_and_unknown(client, home):
    client.post(f"/inventory/{stock('Rice', home['Pantry']).id}/set", data={"quantity": "0"})
    assert ask(client, "HowManyIntent", item="rice")[0] == "You're out of Rice."
    assert ask(client, "HowManyIntent", item="blueberries")[0] == "I couldn't find anything called blueberries."


def test_units_are_spoken(client, home):
    item = db.session.scalar(select(Item).filter_by(name="Rice"))
    item.default_unit = "bags"
    db.session.commit()
    assert ask(client, "HowManyIntent", item="rice")[0] == "Rice: 1 bags in the Pantry."


# --- The shopping list -----------------------------------------------------

def test_add_to_the_list(client, home):
    assert ask(client, "AddToListIntent", item="coffees")[0] == "Added Coffee to the shopping list."
    assert ask(client, "AddToListIntent", item="coffee")[0] == "Coffee is already on the shopping list."
    text = ask(client, "AddToListIntent", item="blueberries")[0]
    assert text == "Added Blueberries to the shopping list. It's a new item."
    names = {e.item.name for e in db.session.scalars(select(ListEntry))}
    assert names == {"Coffee", "Blueberries"}
    assert "Blueberries" in client.get("/list").data.decode()


def test_the_name_alexa_matched_is_used(client, home):
    env = envelope("AddToListIntent", item="cofee")
    env["request"]["intent"]["slots"]["item"]["resolutions"] = {"resolutionsPerAuthority": [
        {"authority": "amzn1.er-authority.echo-sdk.x.ITEM", "status": {"code": "ER_SUCCESS_MATCH"},
         "values": [{"value": {"name": "coffee", "id": "x"}}]}]}
    assert client.post("/alexa", json=env).get_json()["response"]["outputSpeech"]["text"] == \
        "Added Coffee to the shopping list."


def test_whats_on_the_list(client, home):
    assert ask(client, "WhatsOnListIntent")[0] == "The shopping list is empty."
    for name in ("milk", "eggs", "bread"):
        ask(client, "AddToListIntent", item=name)
    assert ask(client, "WhatsOnListIntent")[0] == "The shopping list has 3 things: Bread, Eggs and Milk."


def test_put_heard_as_add_to_the_list(client, home):
    # "add milk to the list" can come through as "put milk in the place called list".
    assert ask(client, "PutIntent", item="milk", place="list")[0] == \
        "Added Milk to the shopping list. It's a new item."


# --- Changing stock --------------------------------------------------------

def test_used_from_a_place(client, home):
    assert ask(client, "UsedIntent", item="coffees", count="2", place="pantry")[0] == \
        "OK. That was the last Coffee in the Pantry."
    assert stock("Coffee", home["Pantry"]).quantity == 0
    # The Cold Room itself before the Top Shelf inside it.
    assert ask(client, "UsedIntent", item="coffee", place="cold room")[0] == "OK. Coffee: 2 left in the Cold Room."
    assert ask(client, "UsedIntent", item="coffee", place="top shelf")[0] == \
        "OK. That was the last Coffee in the Top Shelf."
    assert ask(client, "UsedIntent", item="coffee", count="2")[0] == \
        "OK. That was the last Coffee in the Cold Room. You're out now. Should I add it to the shopping list?"


def test_used_asks_where_when_kept_in_several_places(client, home):
    text = ask(client, "UsedIntent", item="coffee")[0]
    assert text.startswith("Coffee is in the Cold Room, the Pantry and the Top Shelf. Say which")
    assert stock("Coffee", home["Cold Room"]).quantity == 3


def test_using_the_last_one_offers_the_list(client, home):
    text, body = ask(client, "UsedIntent", item="rice")
    assert text == ("OK. That was the last Rice in the Pantry. You're out now. "
                    "Should I add it to the shopping list?")
    assert body["response"]["shouldEndSession"] is False
    attributes = body["sessionAttributes"]
    assert ask(client, "AMAZON.YesIntent", attributes=attributes)[0] == "Added Rice to the shopping list."
    assert db.session.scalar(select(ListEntry)).item.name == "Rice"


def test_using_more_than_recorded(client, home):
    text = ask(client, "UsedIntent", item="rice", count="5")[0]
    assert text.startswith("That's more than was recorded in the Pantry, so I've set it to none. You're out now.")
    assert stock("Rice", home["Pantry"]).quantity == 0


def test_put_in_a_place_and_take_off_the_list(client, home):
    client.post(f"/inventory/{stock('Rice', home['Pantry']).id}/set", data={"quantity": "0"})
    ask(client, "AddToListIntent", item="rice")
    text = ask(client, "PutIntent", item="rice", count="2", place="pantry")[0]
    assert text == "OK. Rice: 2 in the Pantry. I took it off the shopping list."
    assert db.session.scalar(select(ListEntry)) is None


def test_put_without_a_place(client, home):
    assert ask(client, "PutIntent", item="rice", count="3")[0] == "OK. Rice: 4 in the Pantry."
    assert ask(client, "PutIntent", item="coffee", count="1")[0].startswith("Where did you put it?")
    assert ask(client, "PutIntent", item="peas", count="1", place="freezer")[0] == \
        "Which one: the Basement Freezer or the Kitchen Freezer?"
    text = ask(client, "PutIntent", item="soup", count="2", place="cold room")[0]
    assert text == "OK. Soup: 2 in the Cold Room."


def test_bad_counts(client, home):
    assert ask(client, "UsedIntent", item="rice", count="?")[0] == "OK. That was the last Rice in the Pantry. " \
        "You're out now. Should I add it to the shopping list?"  # "?" means not heard: one
    assert ask(client, "PutIntent", item="rice", count="0", place="pantry")[0] == "Sorry, I didn't catch how many."
    assert ask(client, "PutIntent", item="rice", count="5000", place="pantry")[0] == "Sorry, I didn't catch how many."


def test_launch_help_stop_and_session_end(client, home):
    text, body = ask(client)
    assert text.startswith("Home Inventory. What would you like?") and body["response"]["shouldEndSession"] is False
    assert "add milk to the list" in ask(client, "AMAZON.HelpIntent")[0]
    assert ask(client, "AMAZON.StopIntent")[0] == "OK."
    resp = client.post("/alexa", json=envelope(request_type="SessionEndedRequest"))
    assert resp.status_code == 200 and resp.get_json()["response"] == {}


# --- The endpoint itself ---------------------------------------------------

def test_other_skills_and_junk_are_refused(client, home):
    assert client.post("/alexa", json=envelope("HowManyIntent", skill="amzn1.ask.skill.other", item="x")).status_code == 400
    assert client.post("/alexa", data="not json", content_type="application/json").status_code == 400
    assert client.get("/alexa").status_code == 405


def test_off_until_the_skill_id_is_set():
    app = make_app(ALEXA_SKILL_ID=None)
    with app.app_context():
        db.create_all()
        assert app.test_client().post("/alexa", json=envelope("HowManyIntent", item="x")).status_code == 404
        db.drop_all()


def test_production_refuses_to_skip_the_check(monkeypatch):
    monkeypatch.setenv("SECRET_KEY", "x" * 40)
    monkeypatch.setenv("APP_BASE_URL", "https://example.test")
    monkeypatch.setenv("EMAIL_BACKEND", "console")
    with pytest.raises(ConfigError, match="ALEXA_VERIFY_REQUESTS"):
        load_config("instance", {"APP_ENV": "production", "ALEXA_VERIFY_REQUESTS": False})


def test_interaction_model_has_the_familys_names(client, home):
    resp = client.get("/more/alexa/interaction-model.json")
    assert resp.status_code == 200 and "attachment" in resp.headers["Content-Disposition"]
    model = json.loads(resp.data)["interactionModel"]["languageModel"]
    assert model["invocationName"] == "home inventory"
    types = {t["name"]: t["values"] for t in model["types"]}
    items = {v["name"]["value"]: v["name"].get("synonyms", []) for v in types["ITEM"]}
    assert items["coffee"] == ["coffees"] and items["peas"] == ["pea"]
    place_values = [v["name"]["value"] for v in types["PLACE"]]
    assert "freezer" in place_values and "basement freezer" in place_values and "kitchen freezer" in place_values
    assert len(place_values) == len(set(place_values))
    every_word = [w for values in types.values() for v in values
                  for w in [v["name"]["value"], *v["name"].get("synonyms", [])]]
    assert len(every_word) == len(set(every_word))  # Alexa rejects repeats
    samples = [s for i in model["intents"] for s in i["samples"]]
    assert len(samples) == len(set(samples))
    assert {"AMAZON.StopIntent", "AMAZON.YesIntent", "HowManyIntent", "LinkIntent"} <= {i["name"] for i in model["intents"]}


# --- Checking requests come from Amazon ------------------------------------

def _cert(subject_cn, key, issuer_cert=None, issuer_key=None, ca=False, dns=None, days=30):
    now = datetime.now(timezone.utc)
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, subject_cn)])
    builder = (x509.CertificateBuilder().subject_name(name)
               .issuer_name(issuer_cert.subject if issuer_cert else name)
               .public_key(key.public_key()).serial_number(x509.random_serial_number())
               .not_valid_before(now - timedelta(days=1)).not_valid_after(now + timedelta(days=days))
               .add_extension(x509.BasicConstraints(ca=ca, path_length=None), critical=True)
               .add_extension(x509.SubjectKeyIdentifier.from_public_key(key.public_key()), critical=False))
    if ca:
        builder = builder.add_extension(x509.KeyUsage(False, False, False, False, False, True, True, False, False),
                                        critical=True)
    else:
        builder = (builder.add_extension(x509.KeyUsage(True, False, True, False, False, False, False, False, False),
                                         critical=True)
                   .add_extension(x509.ExtendedKeyUsage([ExtendedKeyUsageOID.SERVER_AUTH]), critical=False)
                   .add_extension(x509.SubjectAlternativeName([x509.DNSName(dns)]), critical=False))
    if issuer_cert is not None:
        builder = builder.add_extension(
            x509.AuthorityKeyIdentifier.from_issuer_public_key(issuer_key.public_key()), critical=False)
    return builder.sign(issuer_key or key, hashes.SHA256())


@pytest.fixture
def amazon(monkeypatch):
    """A pretend Amazon: a root the app trusts, and a signing certificate for echo-api.amazon.com."""
    root_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    root = _cert("Test Root", root_key, ca=True)
    keys = {"key": rsa.generate_private_key(public_exponent=65537, key_size=2048)}
    certs = {}

    def issue(dns="echo-api.amazon.com"):
        leaf = _cert(dns, keys["key"], issuer_cert=root, issuer_key=root_key, dns=dns)
        certs["pem"] = leaf.public_bytes(serialization.Encoding.PEM)
        alexa_verify.clear_cache()

    issue()
    monkeypatch.setattr(alexa_verify, "trust_store", lambda: x509.verification.Store([root]))
    monkeypatch.setattr(alexa_verify, "fetch_chain", lambda url: certs["pem"])

    def sign(body):
        return base64.b64encode(keys["key"].sign(body, padding.PKCS1v15(), hashes.SHA256())).decode()

    yield type("Amazon", (), {"sign": staticmethod(sign), "issue": staticmethod(issue)})
    alexa_verify.clear_cache()


@pytest.fixture
def checked_client():
    app = make_app(ALEXA_VERIFY_REQUESTS=True)
    with app.app_context():
        db.create_all()
        yield app.test_client()
        db.session.remove()
        db.drop_all()


def _post(client, body, signature, url=CERT_URL):
    headers = {"SignatureCertChainUrl": url} if url else {}
    if signature:
        headers["Signature-256"] = signature
    return client.post("/alexa", data=body, content_type="application/json", headers=headers)


def test_a_signed_request_is_accepted(checked_client, amazon):
    body = json.dumps(envelope("HowManyIntent", item="coffee")).encode()
    resp = _post(checked_client, body, amazon.sign(body))
    assert resp.status_code == 200 and "isn't linked" in resp.get_json()["response"]["outputSpeech"]["text"]


def test_unsigned_tampered_and_forged_requests_are_refused(checked_client, amazon):
    body = json.dumps(envelope("HowManyIntent", item="coffee")).encode()
    good = amazon.sign(body)
    assert _post(checked_client, body, None).status_code == 400
    assert _post(checked_client, body, good, url=None).status_code == 400
    assert _post(checked_client, body.replace(b"coffee", b"tea"), good).status_code == 400
    assert _post(checked_client, body, "bm90IGEgc2lnbmF0dXJl").status_code == 400
    assert _post(checked_client, body, good, url="https://evil.example.com/echo.api/cert.pem").status_code == 400
    amazon.issue(dns="someone-else.example.com")  # a valid certificate, but not Amazon's
    assert _post(checked_client, body, amazon.sign(body)).status_code == 400


def test_an_old_request_is_refused(checked_client, amazon):
    env = envelope("HowManyIntent", item="coffee")
    env["request"]["timestamp"] = (datetime.now(timezone.utc) - timedelta(minutes=5)).strftime("%Y-%m-%dT%H:%M:%SZ")
    body = json.dumps(env).encode()
    assert _post(checked_client, body, amazon.sign(body)).status_code == 400


@pytest.mark.parametrize("url, ok", [
    ("https://s3.amazonaws.com/echo.api/echo-api-cert.pem", True),
    ("https://s3.amazonaws.com:443/echo.api/echo-api-cert.pem", True),
    ("https://s3.amazonaws.com/echo.api/../echo.api/echo-api-cert.pem", True),
    ("https://S3.AMAZONAWS.COM/echo.api/echo-api-cert.pem", True),
    ("http://s3.amazonaws.com/echo.api/echo-api-cert.pem", False),
    ("https://notamazon.com/echo.api/echo-api-cert.pem", False),
    ("https://s3.amazonaws.com/EcHo.aPi/echo-api-cert.pem", False),
    ("https://s3.amazonaws.com/invalid.path/echo-api-cert.pem", False),
    ("https://s3.amazonaws.com:563/echo.api/echo-api-cert.pem", False),
    ("https://s3.amazonaws.com/echo.api/../evil/cert.pem", False),
    ("https://s3.amazonaws.com:notaport/echo.api/cert.pem", False),
])
def test_cert_url_rules(url, ok):
    # Amazon's documented examples, plus a path that climbs out of /echo.api/.
    if ok:
        alexa_verify.check_cert_url(url)
    else:
        with pytest.raises(alexa_verify.NotFromAlexa):
            alexa_verify.check_cert_url(url)
