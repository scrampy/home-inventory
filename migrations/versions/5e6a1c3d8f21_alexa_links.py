"""alexa links: an Amazon account allowed to use a family's inventory by voice

Revision ID: 5e6a1c3d8f21
Revises: 7b1f0c2e9a44
Create Date: 2026-11-01 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '5e6a1c3d8f21'
down_revision = '7b1f0c2e9a44'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('alexa_link',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('family_id', sa.Integer(), nullable=False),
    sa.Column('code_hash', sa.String(length=64), nullable=True),
    sa.Column('code_expires_at', sa.DateTime(), nullable=True),
    sa.Column('alexa_user_hash', sa.String(length=64), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.Column('created_by_id', sa.Integer(), nullable=True),
    sa.Column('linked_at', sa.DateTime(), nullable=True),
    sa.Column('last_used_at', sa.DateTime(), nullable=True),
    sa.ForeignKeyConstraint(['created_by_id'], ['user.id'], name=op.f('fk_alexa_link_created_by_id_user'), ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['family_id'], ['family.id'], name=op.f('fk_alexa_link_family_id_family'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_alexa_link')),
    sa.UniqueConstraint('alexa_user_hash', name=op.f('uq_alexa_link_alexa_user_hash'))
    )
    with op.batch_alter_table('alexa_link', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_alexa_link_code_hash'), ['code_hash'], unique=False)
        batch_op.create_index(batch_op.f('ix_alexa_link_family_id'), ['family_id'], unique=False)


def downgrade():
    with op.batch_alter_table('alexa_link', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_alexa_link_family_id'))
        batch_op.drop_index(batch_op.f('ix_alexa_link_code_hash'))

    op.drop_table('alexa_link')
