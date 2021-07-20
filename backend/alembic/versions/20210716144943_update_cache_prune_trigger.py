"""update cache prune trigger

Revision ID: e10c8d94b5ec
Revises: bc8bc4bb72cb
Create Date: 2021-07-16 14:49:43.562497

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'e10c8d94b5ec'
down_revision = 'bc8bc4bb72cb'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.execute("""
    CREATE OR REPLACE FUNCTION prune_watershed_cache() RETURNS trigger
        LANGUAGE plpgsql
        AS $$
    BEGIN
    DELETE FROM watershed_cache WHERE generated_watershed_id in (
        SELECT  generated_watershed_id
        FROM    watershed_cache
        WHERE   last_accessed_date < NOW() - INTERVAL '1 hour'
        FOR UPDATE SKIP LOCKED
    );
    RETURN NULL;
    END;
    $$;
    """)