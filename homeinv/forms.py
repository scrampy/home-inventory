from flask_wtf import FlaskForm
from wtforms import (BooleanField, EmailField, FloatField, HiddenField, PasswordField, SelectField,
                     SelectMultipleField, StringField, TextAreaField)
from wtforms.validators import DataRequired, Email, EqualTo, Length, NumberRange, Optional

from .models import NAME_MAX, ROLES

MIN_PASSWORD = 8


def _email_field(label="Email"):
    return EmailField(label, validators=[DataRequired(), Email(), Length(max=254)])


def _new_password_fields():
    password = PasswordField(
        "Password",
        validators=[DataRequired(), Length(min=MIN_PASSWORD, max=128,
                                           message=f"Use at least {MIN_PASSWORD} characters.")],
    )
    confirm = PasswordField(
        "Confirm password",
        validators=[DataRequired(), EqualTo("password", message="Passwords don't match.")],
    )
    return password, confirm


class SignupForm(FlaskForm):
    name = StringField("Your name", validators=[Optional(), Length(max=100)])
    email = _email_field()
    password, confirm = _new_password_fields()
    family_name = StringField("Family name", validators=[Optional(), Length(max=100)])
    invite = HiddenField()


class LoginForm(FlaskForm):
    email = _email_field()
    password = PasswordField("Password", validators=[DataRequired()])
    remember = BooleanField("Keep me logged in")


class ResetRequestForm(FlaskForm):
    email = _email_field()


class ResetPasswordForm(FlaskForm):
    password, confirm = _new_password_fields()


class FamilyNameForm(FlaskForm):
    name = StringField("Family name", validators=[DataRequired(), Length(max=100)])


class InviteForm(FlaskForm):
    email = _email_field("Email to invite")


class RoleForm(FlaskForm):
    role = SelectField("Role", choices=[(r, r.title()) for r in ROLES])


class ActionForm(FlaskForm):
    """A button-only form: carries the CSRF token for POST actions."""


class NameForm(FlaskForm):
    """Add or rename a location, store, aisle or item."""
    name = StringField("Name", validators=[DataRequired(message="Enter a name."), Length(max=NAME_MAX)])


class ItemForm(FlaskForm):
    name = StringField("Name", validators=[DataRequired(message="Enter a name."), Length(max=NAME_MAX)])
    # 0 means "no aisle". Choices are the current family's aisles only, so an
    # aisle ID from another family fails validation.
    aisle_id = SelectField("Aisle", coerce=int)
    store_ids = SelectMultipleField("Where to buy it", coerce=int)
    default_unit = StringField("Unit", validators=[Optional(), Length(max=32)])
    low_stock_threshold = FloatField(
        "Running low at",
        validators=[Optional(), NumberRange(min=0, message="Use 0 or more.")],
    )
    notes = TextAreaField("Notes", validators=[Optional(), Length(max=1000)])
