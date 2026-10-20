"""The Power Apps / SharePoint import, on small made-up exports with the same quirks as the real ones."""

import pytest
from sqlalchemy import select

from helpers import signup, user
from homeinv.extensions import db
from homeinv.importers.sharepoint import SharePointImportError, import_sharepoint
from homeinv.models import Item, Location, Stock, Store

BOM = "﻿"
FILES = {
    "Stores.csv": '"ID","Title"\n"1","Low Stock"\n"2","Costco"\n"3","NoFrills"\n',
    "Locations.csv": '"ID","Title"\n"1","Low Stock"\n"2","Cold Room"\n"4","Basement Freezer "\n',
    "Items.csv": ('"ID","Title","StoreID"\n"1","Blueberries ",\n"2","Coffee (Dark)",\n"3","Pecans ",\n'
                  '"4","Peacans",\n"5","Burrekas ",\n"6","Strawberries",\n'),
    "ItemStores.csv": ('"ID","ItemID","StoreID","Get","Got"\n"1","1","2","True","False"\n'
                       '"2","2","3","True","True"\n"3","4","2","False","False"\n"4","3","1","False","False"\n'),
    "Inventory.csv": ('"TItle","Location","Store","InStock","Quantity"\n'
                      '"Dark Roast","Cold Room","Nofrills","True","4.0"\n'
                      '"Strawberries","Basement Freezer","Costco","True","1.0"\n'
                      '"Strawberries","Basement Freezer","Costco","True","1.0"\n'
                      '"Spinach beurekas","Basement Freezer","Nofrills","True","0.5"\n'
                      '"Hash Browns","Basement Freezer","Costco","False","0.0"\n'
                      '"Mystery","Low Stock","Costco","True","1.0"\n'),
}


@pytest.fixture
def exports(tmp_path):
    for name, text in FILES.items():
        (tmp_path / name).write_text(BOM + text, encoding="utf-8")
    return tmp_path


@pytest.fixture
def family_id(client):
    signup(client, "ann@example.com", family_name="Niramwalla")
    return user("ann@example.com").memberships[0].family_id


def names(model, fid):
    return sorted(r.name for r in db.session.scalars(select(model).filter_by(family_id=fid)))


def stock_of(fid):
    return sorted((s.item.name, s.location.name, s.quantity)
                  for s in db.session.scalars(select(Stock).filter_by(family_id=fid)))


def test_dry_run_changes_nothing(exports, family_id):
    report = import_sharepoint(exports, family_id)
    assert report.created["items"]  # it worked out what to do...
    assert names(Item, family_id) == [] and names(Store, family_id) == []  # ...but saved nothing


def test_import(exports, family_id):
    report = import_sharepoint(exports, family_id, commit=True)

    assert names(Store, family_id) == ["Costco", "NoFrills"]  # no "Low Stock"
    assert names(Location, family_id) == ["Basement Freezer", "Cold Room"]  # trimmed, no "Low Stock"
    assert names(Item, family_id) == ["Blueberries", "Burrekas", "Coffee (Dark)", "Hash Browns",
                                      "Pecans", "Strawberries"]  # Peacans merged; Hash Browns from inventory
    assert stock_of(family_id) == [
        ("Burrekas", "Basement Freezer", 0.5),       # "Spinach beurekas"
        ("Coffee (Dark)", "Cold Room", 4.0),         # "Dark Roast"
        ("Hash Browns", "Basement Freezer", 0.0),    # out of stock, still tracked
        ("Strawberries", "Basement Freezer", 2.0),   # two rows added up
    ]  # "Mystery" was in the fake Low Stock location: skipped

    stores = {i.name: [s.name for s in i.stores] for i in db.session.scalars(select(Item))}
    assert stores["Blueberries"] == ["Costco"]
    assert stores["Pecans"] == ["Costco"]  # link came from the merged "Peacans"
    assert stores["Coffee (Dark)"] == ["NoFrills"]  # "Nofrills" in inventory matched "NoFrills"
    assert stores["Burrekas"] == ["NoFrills"]  # from the inventory list

    notes = "\n".join(report.notes)
    assert 'Merged "Peacans" into "Pecans"' in notes
    assert "Blueberries (Costco)" in notes  # was on the old shopping list (Get but not Got)
    assert "Coffee (Dark) (NoFrills)" not in notes  # Got = already bought
    assert '"Hash Browns" is only in the inventory list' in notes
    assert 'unknown location "Low Stock"' in notes


def test_running_twice_gives_the_same_result(exports, family_id):
    import_sharepoint(exports, family_id, commit=True)
    before = (names(Item, family_id), names(Store, family_id), stock_of(family_id))
    report = import_sharepoint(exports, family_id, commit=True)
    assert (names(Item, family_id), names(Store, family_id), stock_of(family_id)) == before
    assert report.created == {"stores": [], "locations": [], "items": []}
    assert report.links_added == []


def test_existing_rows_are_reused_not_duplicated(client, exports, family_id):
    client.post("/stores", data={"name": "costco"})
    client.post("/items", data={"name": "BLUEBERRIES"})
    import_sharepoint(exports, family_id, commit=True)
    assert names(Store, family_id) == ["NoFrills", "costco"]
    assert "BLUEBERRIES" in names(Item, family_id) and "Blueberries" not in names(Item, family_id)


def test_other_families_untouched(client, new_client, exports, family_id):
    eve = new_client()
    signup(eve, "eve@example.com")
    eve_family = user("eve@example.com").memberships[0].family_id
    import_sharepoint(exports, family_id, commit=True)
    assert names(Item, eve_family) == [] and stock_of(eve_family) == []


def test_missing_file_is_reported(exports, family_id):
    (exports / "Inventory.csv").unlink()
    with pytest.raises(SharePointImportError, match="Inventory.csv"):
        import_sharepoint(exports, family_id)


def test_cli_dry_run_then_commit(app, exports, family_id):
    runner = app.test_cli_runner()
    result = runner.invoke(args=["import-sharepoint", str(exports), "--family", "Niramwalla"])
    assert result.exit_code == 0, result.output
    assert "DRY RUN" in result.output and "Run again with --commit" in result.output
    assert names(Item, family_id) == []

    result = runner.invoke(args=["import-sharepoint", str(exports), "--family", str(family_id), "--commit"])
    assert result.exit_code == 0, result.output
    assert "IMPORTED into" in result.output
    assert len(names(Item, family_id)) == 6

    result = runner.invoke(args=["import-sharepoint", str(exports), "--family", "Nobody"])
    assert result.exit_code != 0 and "No family" in result.output
