"""update_search_view_pks

Revision ID: 854b87855859
Revises: 23a3899db882
Create Date: 2019-10-18 17:53:38.643996

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '854b87855859'
down_revision = '23a3899db882'
branch_labels = None
depends_on = None


def upgrade():
    op.execute("DROP MATERIALIZED VIEW IF EXISTS geocode_lookup")
    op.execute("""
        CREATE MATERIALIZED VIEW geocode_lookup AS

        SELECT
        ST_AsText(stn.geom) AS center,
        stn.station_number AS primary_id,
        stn.station_name AS name,
        'Stream station' AS kind,
        'hydrometric_stream_flow' AS layer,
        to_tsvector(concat_ws(' ',stn.station_number, stn.station_name)) AS tsv
        FROM hydat.stations AS stn
        WHERE stn.prov_terr_state_loc = 'BC'

        UNION
        SELECT
        ST_AsText(ST_Centroid(cadastral."SHAPE")) AS center,
        cadastral."PID"::text AS primary_id,
        NULL AS name,
        'Parcel' AS kind,
        'cadastral' AS layer,
        to_tsvector(coalesce(cadastral."PID"::text, cadastral."PARCEL_NAME"::text)) AS tsv
        FROM cadastral

        UNION
        SELECT
        ST_AsText(ST_Centroid(wrl."SHAPE")) AS center,
        wrl."LICENCE_NUMBER"::text AS primary_id,
        wrl."SOURCE_NAME" AS name,
        'Water rights licence' AS kind,
        'water_rights_licences' AS layer,
        to_tsvector(concat_ws(' ', wrl."POD_NUMBER"::text, wrl."LICENCE_NUMBER"::text, wrl."SOURCE_NAME")) AS tsv
        FROM water_rights_licenses AS wrl

        UNION
        SELECT
        ST_AsText(gww."GEOMETRY") AS center,
        LTRIM(gww."WELL_TAG_NO"::text, '0') AS primary_id,
        gww."WELL_LOCATION" AS name,
        'Ground water well' AS kind,
        'ground_water_wells' AS layer,
        to_tsvector(concat_ws(' ', LTRIM(gww."WELL_TAG_NO"::text, '0'), gww."WELL_LOCATION")) AS tsv
        FROM ground_water_wells AS gww

        UNION SELECT
        ST_AsText(ST_Centroid(aq."GEOMETRY")) AS center,
        LTRIM(aq."AQ_TAG"::text, '0') AS primary_id,
        aq."AQNAME" AS name,
        'Aquifer' AS kind,
        'ground_water_aquifers' AS layer,
        to_tsvector(concat_ws(' ', LTRIM(aq."AQ_TAG"::text, '0'), aq."AQNAME", aq."AQUIFER_NAME", aq."DESCRIPTIVE_LOCATION")) AS tsv
        FROM ground_water_aquifers AS aq

        UNION SELECT
        ST_AsText(ecocat."GEOMETRY") AS center,
        ecocat."REPORT_ID"::text AS primary_id,
        ecocat."TITLE" AS name,
        'Report' AS kind,
        'ecocat_water_related_reports' AS layer,
        to_tsvector(concat_ws(' ', ecocat."REPORT_ID"::text, ecocat."TITLE", ecocat."SHORT_DESCRIPTION", ecocat."AUTHOR")) AS tsv
        FROM ecocat_water_related_reports as ecocat
    """)

    op.execute("""
        create index idx_geocode_tsv ON geocode_lookup USING GIN(tsv)
    """)


def downgrade():
    pass
