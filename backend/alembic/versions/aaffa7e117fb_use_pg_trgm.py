"""use_pg_trgm

Revision ID: aaffa7e117fb
Revises: f2b445f6650c
Create Date: 2020-03-09 22:56:13.127122

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'aaffa7e117fb'
down_revision = 'f2b445f6650c'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.execute("""
    create extension pg_trgm;
    create index if not exists idx_freshwater_atlas_watersheds_fwa_watershed_code
        on freshwater_atlas_watersheds
        using gin ("FWA_WATERSHED_CODE", gin_trgm_ops);
    """)
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    return
    # ### end Alembic commands ###
