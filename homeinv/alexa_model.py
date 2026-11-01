"""The Alexa skill's interaction model: what people can say, as JSON for the developer console.

Built per family, so Alexa's ITEM and PLACE lists hold the family's own item
and place names. The names help Alexa hear them right; words not in the list
still come through. Download it again from the Alexa page after adding lots of
new items, and paste it into the console's JSON Editor.
"""

import re

from sqlalchemy import select

from .extensions import db
from .models import Item, Location

# Used when the family has nothing yet: Alexa won't build a list type with no values.
STARTER_ITEMS = ("milk", "eggs", "bread", "coffee", "butter")
STARTER_PLACES = ("pantry", "fridge", "freezer", "cold room")

INTENTS = {
    "AddToListIntent": {
        "slots": {"item": "ITEM"},
        "samples": [
            "add {item} to the list", "add {item} to the shopping list", "add {item} to my list",
            "add {item} to our list", "add {item} to my shopping list", "add {item}",
            "put {item} on the list", "put {item} on the shopping list", "we need {item}",
            "we need more {item}", "we're out of {item}", "we are out of {item}", "we ran out of {item}",
            "I need {item}", "buy {item}", "get {item}",
        ],
    },
    "HowManyIntent": {
        "slots": {"item": "ITEM", "place": "PLACE"},
        "samples": [
            "how many {item} do we have", "how many {item} are there", "how many {item} have we got",
            "how many {item} are left", "how many {item} are in the {place}", "how many {item} are in {place}",
            "how many {item} in the {place}", "how many {item} do we have in the {place}",
            "how many {item} are there in the {place}", "how many {item} are left in the {place}",
            "how much {item} do we have", "how much {item} is there", "how much {item} is in the {place}",
            "how much {item} is left", "do we have any {item}", "do we have {item}",
            "do we have any {item} in the {place}", "are there any {item} in the {place}",
            "is there any {item} in the {place}", "is there any {item}", "are there any {item}",
            "where is the {item}", "where are the {item}", "where's the {item}", "where do we keep {item}",
            "where do we keep the {item}", "where is {item}", "where are {item}",
        ],
    },
    "UsedIntent": {
        "slots": {"count": "AMAZON.NUMBER", "item": "ITEM", "place": "PLACE"},
        "samples": [
            "we used {count} {item}", "we used a {item}", "we used an {item}", "we used one {item}",
            "we used {item}", "I used {count} {item}", "I used a {item}", "I used an {item}",
            "I took {count} {item}", "I took a {item}", "I took an {item}", "we took {count} {item}",
            "we used {count} {item} from the {place}", "we used a {item} from the {place}",
            "I used a {item} from the {place}", "I used {count} {item} from the {place}",
            "I took a {item} from the {place}", "I took {count} {item} from the {place}",
            "I took {count} {item} out of the {place}", "I took a {item} out of the {place}",
            "remove {count} {item} from the {place}", "remove a {item} from the {place}",
            "take {count} {item} out of the {place}", "take a {item} out of the {place}",
        ],
    },
    "PutIntent": {
        "slots": {"count": "AMAZON.NUMBER", "item": "ITEM", "place": "PLACE"},
        "samples": [
            "I put {count} {item} in the {place}", "I put a {item} in the {place}", "I put an {item} in the {place}",
            "we put {count} {item} in the {place}", "put {count} {item} in the {place}",
            "put a {item} in the {place}", "add {count} {item} to the {place}", "add a {item} to the {place}",
            "we added {count} {item} to the {place}", "I added {count} {item} to the {place}",
            "we added {count} {item}", "I added {count} {item}", "we bought {count} {item}",
            "I bought {count} {item}", "we have {count} more {item}", "there are {count} more {item}",
        ],
    },
    "WhatsOnListIntent": {
        "slots": {},
        "samples": [
            "what's on the list", "what's on the shopping list", "what is on the list",
            "what is on the shopping list", "what's on my list", "what's on our list", "read the list",
            "read me the list", "read the shopping list", "what do we need", "what do I need to buy",
            "what do we need to buy", "what's on the grocery list",
        ],
    },
    "LinkIntent": {
        "slots": {"code": "AMAZON.NUMBER"},
        "samples": [
            "my code is {code}", "the code is {code}", "link code {code}", "link with code {code}",
            "link with {code}", "use code {code}", "code {code}",
        ],
    },
}

BUILT_IN = ("AMAZON.CancelIntent", "AMAZON.HelpIntent", "AMAZON.StopIntent", "AMAZON.NavigateHomeIntent",
            "AMAZON.FallbackIntent", "AMAZON.YesIntent", "AMAZON.NoIntent")


def spoken(name):
    """A name as Alexa would hear it: lower case, letters, digits and spaces only."""
    text = name.casefold().replace("&", " and ").replace("'", "")
    return " ".join(re.sub(r"[^\w\s]", " ", text).split())


def _plural(word):
    if word.endswith("y") and len(word) > 2 and word[-2] not in "aeiou":
        return word[:-1] + "ies"
    if word.endswith(("s", "x", "z", "ch", "sh")):
        return word + "es"
    return word + "s"


def _singular(word):
    if word.endswith("ies") and len(word) > 4:
        return word[:-3] + "y"
    if word.endswith(("ches", "shes", "xes", "zes", "sses")):
        return word[:-2]
    if word.endswith("s") and not word.endswith("ss") and len(word) > 3:
        return word[:-1]
    return word


def _slot_type(name, entries):
    """entries: [(value, [synonyms])]. Alexa rejects a word listed twice, so each is used once."""
    seen, values = set(), []
    for value, synonyms in entries:
        if not value or value in seen:
            continue
        seen.add(value)
        unique = []
        for s in synonyms:
            if s and s not in seen:
                seen.add(s)
                unique.append(s)
        values.append({"name": {"value": value, **({"synonyms": unique} if unique else {})}})
    return {"name": name, "values": values}


def build(family_id, invocation_name):
    items = db.session.scalars(select(Item.name).where(Item.family_id == family_id).order_by(Item.name_key)).all()
    places = db.session.scalars(select(Location).where(Location.family_id == family_id)).all()
    by_id = {p.id: p for p in places}

    item_entries = []
    for name in items or STARTER_ITEMS:
        value = spoken(name)
        words = value.split()
        if not words:
            continue
        other = _singular(words[-1]) if _singular(words[-1]) != words[-1] else _plural(words[-1])
        item_entries.append((value, [" ".join(words[:-1] + [other])]))

    # "freezer", plus "basement freezer" and "kitchen freezer" for telling two Freezers apart.
    place_entries = []
    for place in places:
        value = spoken(place.name)
        place_entries.append((value, []))
        parent = by_id.get(place.parent_id)
        if parent is not None:
            place_entries.append((f"{spoken(parent.name)} {value}", []))
    if not place_entries:
        place_entries = [(p, []) for p in STARTER_PLACES]

    intents = [{"name": name, "samples": []} for name in BUILT_IN]
    for name, spec in INTENTS.items():
        intents.append({"name": name,
                        "slots": [{"name": slot, "type": kind} for slot, kind in spec["slots"].items()],
                        "samples": spec["samples"]})

    return {"interactionModel": {"languageModel": {
        "invocationName": invocation_name,
        "intents": intents,
        "types": [_slot_type("ITEM", item_entries), _slot_type("PLACE", place_entries)],
    }}}
