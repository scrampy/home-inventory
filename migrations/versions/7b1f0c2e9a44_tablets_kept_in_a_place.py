"""tablets kept in a place

Revision ID: 7b1f0c2e9a44
Revises: d4e32a830a0b
Create Date: 2026-10-31 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '7b1f0c2e9a44'
down_revision = 'd4e32a830a0b'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('tablet',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('family_id', sa.Integer(), nullable=False),
    sa.Column('location_id', sa.Integer(), nullable=False),
    sa.Column('token_hash', sa.String(length=64), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.Column('created_by_id', sa.Integer(), nullable=True),
    sa.Column('last_seen_at', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['created_by_id'], ['user.id'], name=op.f('fk_tablet_created_by_id_user'), ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['family_id'], ['family.id'], name=op.f('fk_tablet_family_id_family'), ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['location_id'], ['location.id'], name=op.f('fk_tablet_location_id_location'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_tablet')),
    sa.UniqueConstraint('token_hash', name=op.f('uq_tablet_token_hash'))
    )
    with op.batch_alter_table('tablet', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_tablet_family_id'), ['family_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_tablet_location_id'), ['location_id'], unique=False)


def downgrade():
    with op.batch_alter_table('tablet', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_tablet_location_id'))
        batch_op.drop_index(batch_op.f('ix_tablet_family_id'))

    op.drop_table('tablet')
