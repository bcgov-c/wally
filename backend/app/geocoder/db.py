"""
Database tables and data access functions for Wally Data Layer Meta Information
"""
from sqlalchemy.orm import Session, load_only
from sqlalchemy.sql import select
from sqlalchemy import func, text
from geojson import Feature, Point, FeatureCollection
from logging import getLogger
from app.geocoder.db_models import geocode
from shapely.geometry import Point
from shapely import wkt
from geoalchemy2.elements import WKTElement

logger = getLogger("geocoder")


def lookup_by_text(db: Session, query: str):
    """ look up features by text (e.g. name, an ID number), returning geojson """

    # query the geocode materialized view, using the tsv column (generated by to_tsvector i.e. text search vector).
    #
    # notes:
    # - adding :* (e.g. `query:*`) indicates prefix matching (partial matches for beginning of word)
    # - plainto_tsquery is similar to to_tsquery but allows spaces, but does NOT support :* prefix matching
    #   (exact match to at least 1 word only)
    # q = select([geocode]) \
    #     .where(text("tsv @@ plainto_tsquery(:query)")) \
    #     .order_by(func.ts_rank('tsv', func.plainto_tsquery(query))) \
    #     .limit(5)

    query = query.replace(" ", "<->")
    q = select([geocode]) \
        .where(text("tsv @@ to_tsquery(:query)")) \
        .order_by(func.ts_rank('tsv', func.to_tsquery(query))) \
        .limit(5)

    features = []

    for row in db.execute(q, {"query": f"{query}:*"}):
        # parse center point coordinate, which comes in a ST_AsText (wkt) column.
        point = wkt.loads(row.center)

        # add the Point to make a valid geojson Feature, but also add a "center" property
        # in [lat, lng] format for the web geocoder.
        feat = Feature(geometry=point)
        feat['center'] = [point.x, point.y]

        formatted_name = ""
        if row.name:
            formatted_name = f" - {row.name}"
        feat['place_name'] = f"{row.kind}: {row.primary_id}{formatted_name}"
        feat['place_type'] = row.kind
        feat['primary_id'] = row.primary_id
        feat['layer'] = row.layer
        features.append(feat)

    fc = FeatureCollection(features)
    return fc
