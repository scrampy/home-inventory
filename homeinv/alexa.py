"""Alexa: voice commands for the family's inventory.

"Alexa, ask Home Inventory how many coffees are in the cold room."
"Alexa, tell Home Inventory to add blueberries to the list."

Amazon turns what's said into an intent ("HowManyIntent", item "coffees",
place "cold room") and posts it to /alexa. The reply is the sentence Alexa
says. What can be said is in alexa_model.py; docs/ALEXA.md covers setting up
the skill in Amazon's developer console.

Every request is checked to come from Amazon (alexa_verify.py) for our skill.
Amazon sends an ID for the speaker's Amazon account. That account works only
once it's linked to a family: on the Alexa page (More › Alexa) someone gets a
6-digit code and says "Alexa, tell Home Inventory my code is ...". Unlinking
there stops it working, like unpairing a tablet.
"""

import difflib
import json
import logging
import re
from datetime import timedelta

from flask import (Blueprint, abort, current_app, flash, g, jsonify, redirect, render_template, request, session,
                   url_for)
from flask_login import current_user
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from . import alexa_model, alexa_verify
from .extensions import csrf, db, limiter
from .forms import ActionForm
from .inventory import MAX_QUANTITY, find_or_create_item, get_or_create_stock, take_off_list_if_restocked, total_stock
from .models import AlexaLink, Family, Item, ListEntry, Location, Stock, format_quantity, utcnow
from .places import descendants_and_self, family_places
from .security import current_family_id, family_required, get_for_family_or_404
from .shopping import entry_for, put_on_list

bp = Blueprint("alexa", __name__)
log = logging.getLogger(__name__)

SEEN_EVERY = timedelta(minutes=10)  # how often "last used" is written
MAX_COUNT = 1000                    # "we used 5000 eggs" is a mishearing
LIST_READ_MAX = 15                  # items read out from the shopping list
NO_THE = {"upstairs", "downstairs", "home", "outside", "inside"}  # "in the upstairs" sounds wrong
LEADING_WORDS = ("a ", "an ", "the ", "some ", "any ", "my ", "our ", "more ")


# --- Replies ---------------------------------------------------------------

def _say(text, end=True, reprompt=None, attributes=None):
    response = {
        "outputSpeech": {"type": "PlainText", "text": text},
        "card": {"type": "Simple", "title": "Home Inventory", "content": text},  # shows in the Alexa app
        "shouldEndSession": end,
    }
    if reprompt:
        response["reprompt"] = {"outputSpeech": {"type": "PlainText", "text": reprompt}}
    body = {"version": "1.0", "response": response}
    if attributes:
        body["sessionAttributes"] = attributes
    return body


def _invocation():
    return current_app.config["ALEXA_INVOCATION_NAME"]


def _help():
    return ("You can say things like: add milk to the list. How many coffees are in the cold room. "
            "We used two coffees from the cold room. Or: what's on the list.")


CODE_PROMPT = "Say: my code is, followed by the six numbers."


def _not_linked():
    """Stays listening, so the code can be said next without naming the skill again."""
    return _say("This Alexa isn't linked to a family yet. To get a code, open Home Inventory, then More, "
                "then Alexa, and tap Get a code. When you have it, " + CODE_PROMPT[0].lower() + CODE_PROMPT[1:],
                end=False, reprompt=CODE_PROMPT)


def _join(parts, word="and"):
    parts = list(parts)
    if len(parts) <= 1:
        return "".join(parts)
    return ", ".join(parts[:-1]) + f" {word} " + parts[-1]


def _in_all(places):
    """ "in the Cold Room, the Pantry and the Top Shelf" """
    return "in " + _join(_the(p) for p in sorted(places, key=_place_label))


def _amount(quantity, item):
    text = format_quantity(quantity)
    return f"{text} {item.default_unit}" if item.default_unit else text


def _place_label(place):
    """The place's name, with its parent's if another place shares the name: "Basement Freezer"."""
    same = [p for p in family_places() if p.name_key == place.name_key]
    if len(same) > 1 and place.parent is not None:
        return f"{place.parent.name} {place.name}"
    return place.name


def _the(place):
    """ "the Cold Room", but just "Upstairs"."""
    label = _place_label(place)
    if label.casefold() in NO_THE or label.casefold().startswith(("the ", "my ", "our ")):
        return label
    return f"the {label}"


def _in(place):
    return f"in {_the(place)}"


# --- Understanding names ---------------------------------------------------

def _norm(text):
    """ "The Coffees " -> "coffees". Lower case, no punctuation or leading article."""
    text = alexa_model.spoken(text or "")
    for word in LEADING_WORDS:
        if text.startswith(word):
            text = text[len(word):]
    return text


def _forms(text):
    """A name and its likely singular, so "coffees" finds Coffee and "berry" finds Berries."""
    key = _norm(text)
    if not key:
        return set()
    words = key.split()
    singular = " ".join(words[:-1] + [alexa_model._singular(words[-1])])
    return {key, singular}


def _slot(intent, name):
    """What was said for a slot, preferring the family name Alexa matched it to."""
    slot = (intent.get("slots") or {}).get(name) or {}
    for authority in ((slot.get("resolutions") or {}).get("resolutionsPerAuthority") or []):
        if (authority.get("status") or {}).get("code") == "ER_SUCCESS_MATCH":
            values = authority.get("values") or []
            if values:
                return values[0]["value"]["name"]
    value = slot.get("value")
    return value.strip() if isinstance(value, str) and value.strip() and value != "?" else None


def _family_items():
    return db.session.scalars(
        select(Item).where(Item.family_id == current_family_id()).order_by(Item.name_key)
        .options(selectinload(Item.stock).selectinload(Stock.location), selectinload(Item.list_entry))).all()


def find_items(said):
    """(items, exact). One item when the name matches; otherwise close or partial matches, best first."""
    items = _family_items()
    want = _forms(said)
    if not want:
        return [], False
    exact = [i for i in items if want & _forms(i.name)]
    if exact:
        exact.sort(key=lambda i: _norm(i.name) != _norm(said))  # "Apples" before "Apple" when "apples" is said
        return exact[:1], True
    padded = [f" {w} " for w in want]
    partial = [i for i in items if any(p in f" {_norm(i.name)} " for p in padded)]
    if not partial:
        names = {_norm(i.name): i for i in items}
        partial = [names[n] for n in difflib.get_close_matches(_norm(said), list(names), n=3, cutoff=0.8)]
    partial.sort(key=lambda i: (-total_stock(i), len(i.name)))
    return partial, False


def find_places(said):
    """Places the spoken name could mean: "freezer" can be two; "basement freezer" is one."""
    want = _forms(said)
    if not want:
        return []
    found = []
    for place in family_places():
        names = {_norm(place.name)}
        if place.parent is not None:
            names.add(_norm(f"{place.parent.name} {place.name}"))
        if any(want & _forms(n) for n in names):
            found.append(place)
    return sorted(found, key=_place_label)


def _item_name(said):
    """A new item's name from speech: "blueberries" -> "Blueberries"."""
    return " ".join(w[:1].upper() + w[1:] for w in _norm(said).split())[:80]


def _count(intent):
    value = _slot(intent, "count")
    if value is None:
        return 1
    try:
        return int(float(value))
    except ValueError:
        return None


def _stock_in(item, places):
    """item's stock rows in these places and the places inside them."""
    ids = set()
    for place in places:
        ids.update(descendants_and_self(place))
    return [s for s in item.stock if s.location_id in ids]


# --- What each request does ------------------------------------------------

def _how_many(intent, attributes):
    said, place_said = _slot(intent, "item"), _slot(intent, "place")
    if not said:
        return _say("What should I look for? Say, for example: how many coffees do we have.")
    items, exact = find_items(said)
    if not items:
        return _say(f"I couldn't find anything called {said}.")
    if not exact and len(items) > 1:
        return _say(f"I found {len(items)} things like that. " + " ".join(_where(i) for i in items[:3]))
    item = items[0]

    if place_said:
        places = find_places(place_said)
        if not places:
            return _say(f"I couldn't find a place called {place_said}. " + _where(item))
        here = sum(s.quantity for s in _stock_in(item, places))
        where = _in_all(places) if len(places) <= 3 else f"in those {len(places)} places"
        if here > 0:
            return _say(f"{item.name}: {_amount(here, item)} {where}.")
        elsewhere = [s for s in item.stock if s.quantity > 0 and s not in _stock_in(item, places)]
        text = f"There's no {item.name} {where}."
        if elsewhere:
            text += " There's " + _join(f"{_amount(s.quantity, item)} {_in(s.location)}" for s in elsewhere) + "."
        return _say(text + _list_note(item))
    return _say(_where(item) + _list_note(item))


def _where(item):
    """ "Coffee: 5 in all. 4 in the Cold Room and 1 in the Pantry." """
    have = sorted((s for s in item.stock if s.quantity > 0), key=lambda s: -s.quantity)
    if not have:
        return f"You're out of {item.name}." if item.stock else f"{item.name} isn't kept anywhere yet."
    places = _join(f"{_amount(s.quantity, item)} {_in(s.location)}" for s in have)
    if len(have) == 1:
        return f"{item.name}: {places}."
    return f"{item.name}: {_amount(sum(s.quantity for s in have), item)} in all. {places}."


def _list_note(item):
    entry = item.list_entry
    return " It's on the shopping list." if entry is not None and not entry.in_cart else ""


def _add_to_list(intent, attributes, said=None):
    said = said or _slot(intent, "item")
    if not said:
        return _say("What should I add? Say, for example: add milk to the list.")
    items, exact = find_items(said)
    if exact or len(items) == 1:
        item, created = items[0], False
    else:
        name = _item_name(said)
        if not name:
            return _say("What should I add? Say, for example: add milk to the list.")
        item, created = find_or_create_item(name)
    entry, already = put_on_list(item)
    db.session.commit()
    if already:
        return _say(f"{item.name} is already on the shopping list.")
    return _say(f"Added {item.name} to the shopping list." + (" It's a new item." if created else ""))


def _one_item(intent):
    """(item, None) for the item said, or (None, reply) explaining why not."""
    said = _slot(intent, "item")
    if not said:
        return None, _say("Which item? Say, for example: we used a coffee from the cold room.")
    items, exact = find_items(said)
    if exact or len(items) == 1:
        return items[0], None
    if not items:
        return None, _say(f"I couldn't find anything called {said}.")
    return None, _say(f"Did you mean {_join(i.name for i in items[:3])}? Say the full name.")


def _used(intent, attributes):
    count = _count(intent)
    if count is None or not 0 < count <= MAX_COUNT:
        return _say("Sorry, I didn't catch how many.")
    item, reply = _one_item(intent)
    if reply:
        return reply
    place_said = _slot(intent, "place")
    if place_said:
        places = find_places(place_said)
        if not places:
            return _say(f"I couldn't find a place called {place_said}.")
        rows = [s for s in _stock_in(item, places) if s.quantity > 0]
        if not rows:
            return _say(f"There's no {item.name} {_in_all(places)}. " + _where(item))
        # "from the cold room" means the Cold Room itself before a shelf inside it.
        rows = [s for s in rows if s.location in places] or rows
    else:
        rows = [s for s in item.stock if s.quantity > 0]
        if not rows:
            return _say(f"There's no {item.name} recorded anywhere.")
    if len(rows) > 1:
        places = sorted((s.location for s in rows), key=_place_label)
        return _say(f"{item.name} is {_in_all(places)}. Say which, for example: "
                    f"we used a {item.name} from {_the(places[0])}.")
    stock = rows[0]
    short = count > stock.quantity
    stock.quantity = max(stock.quantity - count, 0)
    db.session.commit()
    left = total_stock(item)
    if short:
        text = f"That's more than was recorded {_in(stock.location)}, so I've set it to none."
    elif stock.quantity > 0:
        text = f"OK. {item.name}: {_amount(stock.quantity, item)} left {_in(stock.location)}."
    else:
        text = f"OK. That was the last {item.name} {_in(stock.location)}."
    entry = entry_for(item)
    if left <= 0 and (entry is None or entry.in_cart):
        return _say(text + " You're out now. Should I add it to the shopping list?", end=False,
                    reprompt=f"Should I add {item.name} to the shopping list?",
                    attributes={"offer_list_item_id": item.id})
    return _say(text)


def _put(intent, attributes):
    count = _count(intent)
    if count is None or not 0 < count <= MAX_COUNT:
        return _say("Sorry, I didn't catch how many.")
    place_said = _slot(intent, "place")
    if place_said and "list" in _norm(place_said).split():  # "add milk to the list" heard as a place
        return _add_to_list(intent, attributes)
    said = _slot(intent, "item")
    if not said:
        return _say("Which item? Say, for example: I put two coffees in the cold room.")
    items, exact = find_items(said)
    if not exact and len(items) > 1:
        return _say(f"Did you mean {_join(i.name for i in items[:3])}? Say the full name.")

    if place_said:
        places = find_places(place_said)
        if not places:
            return _say(f"I couldn't find a place called {place_said}.")
        if len(places) > 1:
            return _say(f"Which one: {_join((_the(p) for p in places), 'or')}?")
        place = places[0]
    else:
        kept = items[0].stock if items else []
        if len(kept) != 1:
            name = items[0].name if items else _item_name(said)
            return _say(f"Where did you put it? Say, for example: I put {count} {name} in the pantry.")
        place = kept[0].location

    item = items[0] if items else find_or_create_item(_item_name(said))[0]
    before = total_stock(item)
    stock = get_or_create_stock(item, place)
    stock.quantity = min(stock.quantity + count, MAX_QUANTITY)
    db.session.flush()
    removed = take_off_list_if_restocked(item, before)
    db.session.commit()
    text = f"OK. {item.name}: {_amount(stock.quantity, item)} {_in(place)}."
    if removed:
        text += " I took it off the shopping list."
    return _say(text)


def _whats_on_list(intent, attributes):
    names = db.session.scalars(
        select(Item.name).join(ListEntry, ListEntry.item_id == Item.id)
        .where(ListEntry.family_id == current_family_id(), ListEntry.in_cart.is_(False))
        .order_by(Item.name_key)).all()
    if not names:
        return _say("The shopping list is empty.")
    if len(names) == 1:
        return _say(f"The shopping list has one thing: {names[0]}.")
    shown = names[:LIST_READ_MAX]
    more = len(names) - len(shown)
    text = f"The shopping list has {len(names)} things: " + (", ".join(shown) + f", and {more} more"
                                                            if more else _join(shown))
    return _say(text + ".")


def _yes(intent, attributes):
    item_id = attributes.get("offer_list_item_id")
    if not isinstance(item_id, int):
        return _say("OK.")
    item = db.session.get(Item, item_id)
    if item is None or item.family_id != current_family_id():
        return _say("OK.")
    put_on_list(item)
    db.session.commit()
    return _say(f"Added {item.name} to the shopping list.")


INTENTS = {
    "HowManyIntent": _how_many,
    "AddToListIntent": _add_to_list,
    "UsedIntent": _used,
    "PutIntent": _put,
    "WhatsOnListIntent": _whats_on_list,
    "AMAZON.YesIntent": _yes,
}


def _link(user_id, intent, link):
    code = re.sub(r"\D", "", _slot(intent, "code") or "")
    waiting = AlexaLink.waiting_for(code) if len(code) == 6 else None
    if waiting is None or not user_id:
        text = "That code didn't work. Codes last 10 minutes. Get a new one in Home Inventory, under More, then Alexa."
        if link is None:  # not linked yet: listen for another try
            return _say(text + " Then " + CODE_PROMPT[0].lower() + CODE_PROMPT[1:], end=False, reprompt=CODE_PROMPT)
        return _say(text)
    if link is not None:
        db.session.delete(link)  # linked to a family before: this replaces it
        db.session.flush()
    waiting.complete(user_id)
    db.session.commit()
    family = db.session.get(Family, waiting.family_id)
    return _say(f"Done. This Alexa is now linked to {family.name}. What would you like? Try: what's on the list.",
                end=False, reprompt="Try: what's on the list.")


def _user_id(envelope):
    system = (envelope.get("context") or {}).get("System") or {}
    return (((system.get("user") or {}).get("userId"))
            or (((envelope.get("session") or {}).get("user") or {}).get("userId")))


def _application_id(envelope):
    system = (envelope.get("context") or {}).get("System") or {}
    return (((system.get("application") or {}).get("applicationId"))
            or (((envelope.get("session") or {}).get("application") or {}).get("applicationId")))


def handle(envelope):
    """The reply to one request from Alexa, as a dict."""
    req = envelope.get("request") or {}
    kind = req.get("type")
    if kind == "SessionEndedRequest":
        return {"version": "1.0", "response": {}}
    intent = (req.get("intent") or {}) if kind == "IntentRequest" else {}
    name = intent.get("name")
    user_id = _user_id(envelope)
    link = AlexaLink.for_alexa_user(user_id)

    if name == "LinkIntent":
        return _link(user_id, intent, link)
    if name in ("AMAZON.StopIntent", "AMAZON.CancelIntent", "AMAZON.NoIntent"):
        return _say("OK.")
    if link is None:
        return _not_linked()

    g.alexa_link = link
    if link.last_used_at is None or utcnow() - link.last_used_at > SEEN_EVERY:
        link.last_used_at = utcnow()
        db.session.commit()

    if kind == "LaunchRequest":
        return _say(f"{_invocation().title().rstrip('.')}. What would you like? " + _help(), end=False,
                    reprompt="Try: what's on the list.")
    handler = INTENTS.get(name)
    if handler is None:  # Help, Fallback, NavigateHome, or something new
        return _say(_help(), end=False, reprompt="Try: what's on the list.")
    attributes = (envelope.get("session") or {}).get("attributes") or {}
    return handler(intent, attributes)


@bp.route("/alexa", methods=["POST"])
@csrf.exempt
@limiter.limit("60 per minute")
def endpoint():
    """Where Amazon sends what was said. Not for browsers."""
    skill_id = current_app.config["ALEXA_SKILL_ID"]
    if not skill_id:
        abort(404)
    body = request.get_data(cache=True)
    try:
        envelope = json.loads(body)
    except ValueError:
        abort(400)
    if not isinstance(envelope, dict):
        abort(400)
    if current_app.config["ALEXA_VERIFY_REQUESTS"]:
        try:
            alexa_verify.verify(request.headers, body, (envelope.get("request") or {}).get("timestamp"))
        except alexa_verify.NotFromAlexa as e:
            log.warning("Refused an Alexa request: %s", e)
            abort(400)
    if _application_id(envelope) != skill_id:
        log.warning("Refused an Alexa request for another skill: %s", _application_id(envelope))
        abort(400)
    try:
        return jsonify(handle(envelope))
    except Exception:
        log.exception("Alexa request failed")
        db.session.rollback()
        return jsonify(_say("Sorry, something went wrong in Home Inventory. Try again in a moment."))


# --- The Alexa page (More › Alexa, signed in) ------------------------------

SESSION_CODE = "alexa_code"


def _require_post_form():
    if not ActionForm().validate_on_submit():
        abort(400)


@bp.route("/more/alexa")
@family_required
def setup():
    links = db.session.scalars(select(AlexaLink).where(AlexaLink.family_id == current_family_id(),
                                                       AlexaLink.alexa_user_hash.is_not(None))
                               .order_by(AlexaLink.linked_at)).all()
    code = None
    shown = session.get(SESSION_CODE)
    if isinstance(shown, dict):
        waiting = db.session.get(AlexaLink, shown.get("id"))
        if (waiting is not None and waiting.family_id == current_family_id() and not waiting.is_linked
                and waiting.code_expires_at > utcnow()):
            code = {"digits": shown.get("code"), "expires_at": waiting.code_expires_at}
        else:
            session.pop(SESSION_CODE, None)
    return render_template("alexa/setup.html", links=links, code=code, invocation=_invocation(),
                           enabled=bool(current_app.config["ALEXA_SKILL_ID"]),
                           endpoint_url=(current_app.config.get("APP_BASE_URL") or request.host_url.rstrip("/"))
                           + url_for(".endpoint"))


@bp.route("/more/alexa/code", methods=["POST"])
@family_required
def new_code():
    """A code to say to Alexa. Any earlier code from this family stops working."""
    _require_post_form()
    for old in db.session.scalars(select(AlexaLink).where(AlexaLink.family_id == current_family_id(),
                                                          AlexaLink.alexa_user_hash.is_(None))):
        db.session.delete(old)
    link, code = AlexaLink.start(current_family_id(), current_user._get_current_object())
    db.session.add(link)
    db.session.commit()
    session[SESSION_CODE] = {"id": link.id, "code": code}
    return redirect(url_for(".setup"))


@bp.route("/more/alexa/<int:link_id>/unlink", methods=["POST"])
@family_required
def unlink(link_id):
    _require_post_form()
    link = get_for_family_or_404(AlexaLink, link_id)
    db.session.delete(link)
    db.session.commit()
    flash("Unlinked. That Alexa can't use your inventory now.", "info")
    return redirect(url_for(".setup"))


@bp.route("/more/alexa/interaction-model.json")
@family_required
def interaction_model():
    """The skill's interaction model, with this family's item and place names, for the developer console."""
    model = alexa_model.build(current_family_id(), _invocation())
    response = current_app.response_class(json.dumps(model, indent=2), mimetype="application/json")
    response.headers["Content-Disposition"] = "attachment; filename=home-inventory-alexa.json"
    return response
