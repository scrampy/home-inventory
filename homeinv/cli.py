"""Command-line tasks: flask --app wsgi <command>."""

import click
from flask import Flask
from sqlalchemy import select

from .extensions import db
from .models import Family


def register(app: Flask):
    app.cli.add_command(import_sharepoint_command)


def _find_family(value):
    if value.isdigit():
        family = db.session.get(Family, int(value))
        if family:
            return family
    matches = db.session.scalars(select(Family).filter_by(name=value)).all()
    if len(matches) == 1:
        return matches[0]
    if matches:
        raise click.ClickException(f'{len(matches)} families are called "{value}". Use the family ID.')
    raise click.ClickException(f'No family "{value}". Families: ' + ", ".join(
        f"{f.id}: {f.name}" for f in db.session.scalars(select(Family))))


@click.command("import-sharepoint")
@click.argument("folder", type=click.Path(exists=True, file_okay=False))
@click.option("--family", "family_ref", required=True, help="Family ID or exact name.")
@click.option("--commit", is_flag=True, help="Save the changes. Without it, only shows what would happen.")
def import_sharepoint_command(folder, family_ref, commit):
    """Import the old Power Apps SharePoint exports into a family."""
    from .importers.sharepoint import SharePointImportError, import_sharepoint

    family = _find_family(family_ref)
    try:
        report = import_sharepoint(folder, family.id, commit=commit)
    except SharePointImportError as error:
        raise click.ClickException(str(error))
    click.echo(f"{'IMPORTED into' if commit else 'DRY RUN (nothing saved) for'} family {family.id}: {family.name}")
    for line in report.lines():
        click.echo(line)
    if not commit:
        click.echo("\nRun again with --commit to save.")
