"""Import the old Power Apps data (SharePoint list exports) into one family.

Expects these CSV exports in one folder:

    Stores.csv      ID, Title
    Locations.csv   ID, Title
    Items.csv       ID, Title, StoreID (StoreID unused)
    ItemStores.csv  ID, ItemID, StoreID, Get, Got   (which store sells which item;
                    Get/Got were the old shopping list)
    Inventory.csv   TItle, Location, Store, InStock, Quantity   (matched by item name)

Safe to run more than once: rows are matched by name (ignoring case and spaces),
and stock quantities are set to what the files say rather than added to.
"""

import csv
from dataclasses import dataclass, field
from pathlib import Path

from sqlalchemy import select

from ..extensions import db
from ..models import Item, Location, Stock, Store, clean_name, name_key

# "Low Stock" was a fake store and location used as a workaround in Power Apps.
SKIP_NAMES = {"low stock"}

# Near-duplicates in the old item list, merged into one item (name_key -> name to keep).
ITEM_MERGES = {
    "peacans": "Pecans",
    "paper towel": "Paper Towels",
    "edamame beans": "Edamame",
    "frozen pizza": "Pizza",
}

# Inventory rows were typed by hand, so some names differ from the item list.
INVENTORY_ALIASES = {
    "dark roast": "Coffee (Dark)",
    "spinach beurekas": "Burrekas",
}

FILES = ("Stores.csv", "Locations.csv", "Items.csv", "ItemStores.csv", "Inventory.csv")


class SharePointImportError(Exception):
    pass


@dataclass
class Report:
    created: dict = field(default_factory=lambda: {"stores": [], "locations": [], "items": []})
    existing: dict = field(default_factory=lambda: {"stores": 0, "locations": 0, "items": 0})
    links_added: list = field(default_factory=list)
    stock_set: list = field(default_factory=list)
    notes: list = field(default_factory=list)

    def lines(self):
        out = []
        for kind in ("stores", "locations", "items"):
            names = self.created[kind]
            out.append(f"{kind.title()}: {len(names)} new, {self.existing[kind]} already there")
            if names:
                out.append("  " + ", ".join(names))
        out.append(f"Item-store links: {len(self.links_added)} new")
        out.append(f"Stock: {len(self.stock_set)} location quantities set")
        for item, location, qty in self.stock_set:
            out.append(f"  {item} @ {location}: {qty:g}")
        if self.notes:
            out.append("Notes:")
            out.extend(f"  - {n}" for n in self.notes)
        return out


def _read(folder, filename):
    path = Path(folder) / filename
    if not path.exists():
        raise SharePointImportError(f"Missing {path}")
    with path.open(newline="", encoding="utf-8-sig") as handle:
        rows = list(csv.DictReader(handle))
    # Header names vary in case ("TItle"); normalise them.
    return [{(k or "").strip().lower(): (v or "").strip() for k, v in row.items()} for row in rows]


def _flag(value):
    return value.strip().lower() == "true"


class _Importer:
    def __init__(self, family_id, report):
        self.family_id = family_id
        self.report = report
        self.cache = {}

    def get_or_create(self, model, kind, name):
        """The family's row of `model` with this name, created if missing."""
        name = clean_name(name)
        key = (model, name_key(name))
        if key in self.cache:
            return self.cache[key]
        row = db.session.scalar(select(model).filter_by(family_id=self.family_id, name_key=key[1]))
        if row is None:
            row = model(family_id=self.family_id)
            row.set_name(name)
            db.session.add(row)
            db.session.flush()
            self.report.created[kind].append(name)
        else:
            self.report.existing[kind] += 1
        self.cache[key] = row
        return row

    def link(self, item, store, why=None):
        if store not in item.stores:
            item.stores.append(store)
            self.report.links_added.append((item.name, store.name))
            if why:
                self.report.notes.append(why)


def import_sharepoint(folder, family_id, commit=False):
    """Import the exports in `folder` into the family. Rolls back unless commit=True."""
    tables = {name: _read(folder, name) for name in FILES}
    report = Report()
    imp = _Importer(family_id, report)

    stores_by_id, stores_by_key = {}, {}
    for row in tables["Stores.csv"]:
        if name_key(row["title"]) in SKIP_NAMES:
            continue
        store = imp.get_or_create(Store, "stores", row["title"])
        stores_by_id[row["id"]] = store
        stores_by_key[store.name_key] = store

    locations_by_key = {}
    for row in tables["Locations.csv"]:
        if name_key(row["title"]) in SKIP_NAMES:
            continue
        location = imp.get_or_create(Location, "locations", row["title"])
        locations_by_key[location.name_key] = location
    report.notes.append('Skipped the "Low Stock" store and location (an old workaround).')

    items_by_id = {}
    for row in tables["Items.csv"]:
        name = clean_name(row["title"])
        if not name:
            continue
        keep = ITEM_MERGES.get(name_key(name))
        if keep:
            report.notes.append(f'Merged "{name}" into "{keep}".')
        items_by_id[row["id"]] = imp.get_or_create(Item, "items", keep or name)

    on_old_list = []
    for row in tables["ItemStores.csv"]:
        item, store = items_by_id.get(row["itemid"]), stores_by_id.get(row["storeid"])
        if item is None or store is None:
            continue
        imp.link(item, store)
        if _flag(row.get("get", "")) and not _flag(row.get("got", "")):
            on_old_list.append(f"{item.name} ({store.name})")
    if on_old_list:
        report.notes.append("Were on the old shopping list (not imported; the shopping list "
                            "comes in phase 4): " + ", ".join(on_old_list) + ".")

    # Inventory: add up repeated rows first, then set each quantity.
    wanted = {}
    for row in tables["Inventory.csv"]:
        raw = clean_name(row["title"])
        key = name_key(raw)
        name = INVENTORY_ALIASES.get(key) or ITEM_MERGES.get(key) or raw
        if name != raw:
            report.notes.append(f'Inventory row "{raw}" matched to item "{name}".')
        location = locations_by_key.get(name_key(row["location"]))
        if location is None:
            report.notes.append(f'Inventory row "{raw}": unknown location "{row["location"]}", skipped.')
            continue
        known = (Item, name_key(name)) in imp.cache
        item = imp.get_or_create(Item, "items", name)
        if not known and item.name in report.created["items"]:
            report.notes.append(f'"{item.name}" is only in the inventory list, so it was added as a new item.')
        store = stores_by_key.get(name_key(row["store"]))
        if store is not None:
            imp.link(item, store, f'Linked "{item.name}" to {store.name} (from the inventory list).')
        try:
            quantity = max(float(row["quantity"] or 0), 0)
        except ValueError:
            report.notes.append(f'Inventory row "{raw}": quantity "{row["quantity"]}" isn\'t a number, used 0.')
            quantity = 0
        slot = (item, location)
        if slot in wanted:
            report.notes.append(f'"{item.name}" in {location.name} was listed twice; quantities added up.')
        wanted[slot] = wanted.get(slot, 0) + quantity

    for (item, location), quantity in wanted.items():
        stock = db.session.scalar(select(Stock).filter_by(item_id=item.id, location_id=location.id))
        if stock is None:
            stock = Stock(family_id=family_id, item=item, location=location)
            db.session.add(stock)
        stock.quantity = round(quantity, 2)
        report.stock_set.append((item.name, location.name, stock.quantity))

    if commit:
        db.session.commit()
    else:
        db.session.rollback()
    return report
