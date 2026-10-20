from datetime import datetime, timedelta, timezone
import hashlib
import secrets

from flask_login import UserMixin
from sqlalchemy import Column, ForeignKey, String, Table, Text, UniqueConstraint, select
from sqlalchemy.orm import Mapped, declared_attr, mapped_column, relationship
from werkzeug.security import check_password_hash, generate_password_hash

from .extensions import db

ROLE_ADMIN = "admin"
ROLE_MEMBER = "member"
ROLES = (ROLE_ADMIN, ROLE_MEMBER)


def utcnow():
    """Naive UTC timestamp. All times in the database are stored this way."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


def normalize_email(email):
    return (email or "").strip().lower()


def hash_token(token):
    return hashlib.sha256(token.encode()).hexdigest()


class User(UserMixin, db.Model):
    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(254), unique=True)
    name: Mapped[str] = mapped_column(String(100), default="")
    password_hash: Mapped[str] = mapped_column(String(255))
    # Part of the login cookie. Changing it signs the user out everywhere.
    session_token: Mapped[str] = mapped_column(String(32), default=lambda: secrets.token_hex(16))
    is_verified: Mapped[bool] = mapped_column(default=False)
    created_at: Mapped[datetime] = mapped_column(default=utcnow)
    # The family whose data the user is currently looking at.
    active_family_id: Mapped[int | None] = mapped_column(
        ForeignKey("family.id", ondelete="SET NULL")
    )

    memberships: Mapped[list["Membership"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)
        self.session_token = secrets.token_hex(16)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def get_id(self):
        return f"{self.id}:{self.session_token}"

    @classmethod
    def from_session_id(cls, session_id):
        user_id, _, token = (session_id or "").partition(":")
        if not user_id.isdigit() or not token:
            return None
        user = db.session.get(cls, int(user_id))
        if user and secrets.compare_digest(user.session_token, token):
            return user
        return None

    @property
    def display_name(self):
        return self.name or self.email

    def membership_in(self, family_id):
        return db.session.scalar(
            select(Membership).filter_by(user_id=self.id, family_id=family_id)
        )

    @property
    def current_membership(self):
        """Membership for the active family, falling back to any family the user is in."""
        if self.active_family_id:
            membership = self.membership_in(self.active_family_id)
            if membership:
                return membership
        return db.session.scalar(
            select(Membership).filter_by(user_id=self.id).order_by(Membership.joined_at, Membership.id)
        )


class Family(db.Model):
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100))
    created_at: Mapped[datetime] = mapped_column(default=utcnow)

    memberships: Mapped[list["Membership"]] = relationship(
        back_populates="family", cascade="all, delete-orphan", order_by="Membership.joined_at"
    )
    invitations: Mapped[list["Invitation"]] = relationship(
        back_populates="family", cascade="all, delete-orphan"
    )

    def admin_count(self):
        return sum(1 for m in self.memberships if m.role == ROLE_ADMIN)


class Membership(db.Model):
    __table_args__ = (UniqueConstraint("user_id", "family_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("user.id", ondelete="CASCADE"), index=True)
    family_id: Mapped[int] = mapped_column(ForeignKey("family.id", ondelete="CASCADE"), index=True)
    role: Mapped[str] = mapped_column(String(16), default=ROLE_MEMBER)
    joined_at: Mapped[datetime] = mapped_column(default=utcnow)

    user: Mapped[User] = relationship(back_populates="memberships")
    family: Mapped[Family] = relationship(back_populates="memberships")

    @property
    def is_admin(self):
        return self.role == ROLE_ADMIN


class Invitation(db.Model):
    """An emailed, single-use link that adds the recipient to a family.

    Only a hash of the token is stored, so a copy of the database can't be used
    to accept invitations.
    """

    id: Mapped[int] = mapped_column(primary_key=True)
    family_id: Mapped[int] = mapped_column(ForeignKey("family.id", ondelete="CASCADE"), index=True)
    email: Mapped[str] = mapped_column(String(254))
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    invited_by_id: Mapped[int | None] = mapped_column(ForeignKey("user.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = mapped_column(default=utcnow)
    expires_at: Mapped[datetime]
    accepted_at: Mapped[datetime | None]
    revoked_at: Mapped[datetime | None]

    family: Mapped[Family] = relationship(back_populates="invitations")
    invited_by: Mapped[User | None] = relationship()

    @classmethod
    def create(cls, family, email, invited_by, max_age_days):
        token = secrets.token_urlsafe(32)
        invitation = cls(
            family=family,
            email=normalize_email(email),
            token_hash=hash_token(token),
            invited_by=invited_by,
            expires_at=utcnow() + timedelta(days=max_age_days),
        )
        return invitation, token

    @classmethod
    def find_by_token(cls, token):
        if not token:
            return None
        return db.session.scalar(select(cls).filter_by(token_hash=hash_token(token)))

    @property
    def is_pending(self):
        return self.accepted_at is None and self.revoked_at is None and self.expires_at > utcnow()


# --- Catalog: everything below belongs to one family -----------------------

NAME_MAX = 80


def clean_name(name):
    """Trim and collapse inner whitespace; keep the user's capitalisation."""
    return " ".join((name or "").split())


def name_key(name):
    """What makes two names "the same" within a family: "  milk " == "Milk"."""
    return clean_name(name).casefold()


class FamilyOwned:
    """A row that belongs to exactly one family and has a name unique within it.

    Look these up through security.get_for_family_or_404 / family_select so other
    families' rows are never reachable.
    """

    @declared_attr
    def family_id(cls) -> Mapped[int]:
        return mapped_column(ForeignKey("family.id", ondelete="CASCADE"), index=True)

    @declared_attr
    def __table_args__(cls):
        return (UniqueConstraint("family_id", "name_key"),)

    name: Mapped[str] = mapped_column(String(NAME_MAX))
    name_key: Mapped[str] = mapped_column(String(NAME_MAX))
    created_at: Mapped[datetime] = mapped_column(default=utcnow)

    def set_name(self, name):
        self.name = clean_name(name)
        self.name_key = name_key(name)


class Location(FamilyOwned, db.Model):
    """Where things are kept: Pantry, Garage freezer, ..."""

    id: Mapped[int] = mapped_column(primary_key=True)


class Aisle(FamilyOwned, db.Model):
    """A section of a store (Produce, Dairy, ...), used to order the shopping list."""

    id: Mapped[int] = mapped_column(primary_key=True)
    items: Mapped[list["Item"]] = relationship(back_populates="aisle", passive_deletes=True)


item_store = Table(
    "item_store",
    db.metadata,
    Column("item_id", ForeignKey("item.id", ondelete="CASCADE"), primary_key=True),
    Column("store_id", ForeignKey("store.id", ondelete="CASCADE"), primary_key=True),
)


class Store(FamilyOwned, db.Model):
    id: Mapped[int] = mapped_column(primary_key=True)
    items: Mapped[list["Item"]] = relationship(secondary=item_store, back_populates="stores")


class Item(FamilyOwned, db.Model):
    """Something the family buys and keeps, e.g. "Milk"."""

    id: Mapped[int] = mapped_column(primary_key=True)
    aisle_id: Mapped[int | None] = mapped_column(ForeignKey("aisle.id", ondelete="SET NULL"), index=True)
    default_unit: Mapped[str | None] = mapped_column(String(32))
    notes: Mapped[str | None] = mapped_column(Text)
    # Shows up as "running low" when the total across locations falls to this or below.
    low_stock_threshold: Mapped[float | None]

    aisle: Mapped[Aisle | None] = relationship(back_populates="items")
    stores: Mapped[list[Store]] = relationship(
        secondary=item_store, back_populates="items", order_by="Store.name_key"
    )
