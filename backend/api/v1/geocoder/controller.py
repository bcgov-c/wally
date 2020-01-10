import re
import pyproj
from fastapi import HTTPException
from sqlalchemy.orm import Session
from sqlalchemy.sql import select
from sqlalchemy import func, text
from geojson import Feature, FeatureCollection, Point
from logging import getLogger
from shapely import wkt
from shapely.geometry import shape, mapping
from shapely.ops import transform

import api.v1.aggregator.controller as agr_repo
from api.v1.aggregator.controller import fetch_geojson_features
from api.v1.aggregator.schema import WMSGetMapQuery, WMSGetFeatureQuery, ExternalAPIRequest
from api.v1.aggregator.routes import EXTERNAL_API_REQUESTS
from api.v1.geocoder.db_models import geocode

logger = getLogger("geocoder")
search_symbols = re.compile(r'[^\w ]', re.UNICODE)
search_spaces = re.compile(r'[ ]+')

# Search strings will match against any of the fields provided in SEARCH_FIELDS.
WFS_SEARCH_FIELDS = {
    "cadastral": ["PARCEL_NAME"],
    "water_rights_licences": ["LICENCE_NUMBER", "FILE_NUMBER"],
    "aquifers": ["AQNAME", "AQUIFER_NAME"],
    "ecocat_water_related_reports": ["REPORT_ID", "TITLE"]
}

# WFS_LAYER_IDS maps layer names to DataBC API Catalogue layers.
# This information can also be kept on the database table metadata.wms_catalogue,
# and the lookup_feature function will also check there. However, there are issues
# with having a wms_catalogue record for layers we intend to use as vector layers.
# WFS_LAYER_IDS provides an alternative for the purpose of DataBC WFS lookups in
# this file.
WFS_LAYER_IDS = {
    "cadastral": "WHSE_CADASTRE.PMBC_PARCEL_FABRIC_POLY_SVW",
    "aquifers": "WHSE_WATER_MANAGEMENT.GW_AQUIFERS_CLASSIFICATION_SVW",
    "water_rights_licences": "WHSE_WATER_MANAGEMENT.WLS_WATER_RIGHTS_LICENCES_SV",
}

# searches will make a request to these external URLs, if available for the layer type
EXTERNAL_API_SEARCH_URLS = {
    "groundwater_wells": "https://apps.nrs.gov.bc.ca/gwells/api/v2/wells/locations?limit=5&search="
}


def external_search(query, feature_type, url):
    """ Makes an external search request to a specified URL.  The url will have the search
        text appended to it.
    """
    req = ExternalAPIRequest(
        url=url + query,
        layer=feature_type,
        q={},
        paginate=False
    )
    # Fetch features.
    feature_collection = fetch_geojson_features([req])

    features = feature_collection[0].geojson['features']
    geocoder_features = []

    for feature in features:
        feature['layer'] = feature_type
        feature['center'] = (feature.geometry.coordinates[0], feature.geometry.coordinates[1])
        feature['place_name'] = str(feature.properties['well_tag_number'])
        logger.info(feature)
        geocoder_features.append(feature)

    return geocoder_features


def wfs_search(query, feature_type):
    # look up the DataBC layer ID.
    # first check in the WFS_LAYER_IDS constant defined above
    layer = WFS_LAYER_IDS.get(feature_type, None)

    # fall back on WMS metadata, if available
    if not layer:
        catalogue = agr_repo.get_display_catalogue(db, [feature_type])
        if not catalogue and not catalogue[0].wms_catalogue_id:
            raise HTTPException(status_code=400, detail="Feature type invalid")
        layer = catalogue[0].wms_catalogue.wms_name

    search_fields = WFS_SEARCH_FIELDS.get(feature_type, None)
    if not search_fields or not layer:
        raise HTTPException(status_code=400, detail="Feature type invalid")

    # form CQL filter.
    # note: this is not SQL, and this string will be sent over HTTP to a public server.
    # this doesn't automatically carry the same risks as forming a SQL string.
    cql_filter = f"{search_fields[0]} ILIKE '%{query}%'"

    # append additional filter statements if multiple search fields available.
    if len(search_fields) > 1:
        cql_filter = cql_filter + ' '.join([
            f"OR {field} ILIKE '%{query}%'" for field in search_fields[1:]
        ])

    query = WMSGetFeatureQuery(
        typeNames=layer,
        count=5,
        # this is CQL, not SQL, and this string will be sent over HTTP.
        cql_filter=cql_filter
    )
    req = ExternalAPIRequest(
        url=f"https://openmaps.gov.bc.ca/geo/pub/wfs?",
        layer=feature_type,
        q=query
    )

    # Fetch features.
    feature_collection = fetch_geojson_features([req])
    features = feature_collection[0].geojson['features']

    # create a collection to add processed features to.
    # this list will eventually be returned as geocoder results.
    geocoder_features = []

    # Some datasets in the DataBC API only output BC Albers (3005). Configure projection
    # to SRID 4326 so we can get a representative point in lat/long degrees.
    project = pyproj.Transformer.from_proj(
        pyproj.Proj(init='epsg:3005'),
        pyproj.Proj(init='epsg:4326'))

    for feature in features:
        geom = transform(project.transform, shape(feature.geometry))
        new_feature = Feature(geometry=mapping(geom.centroid))

        # add metadata to the feature. This info is required
        # for displaying and zooming to search results.
        new_feature['layer'] = feature_type
        new_feature['center'] = [geom.centroid.x, geom.centroid.y]
        new_feature['place_name'] = ' '.join(
            [str(feature.properties.get(field, '')) for field in WFS_SEARCH_FIELDS[feature_type]])
        new_feature['id'] = feature['id']
        geocoder_features.append(new_feature)

    return geocoder_features


def lookup_feature(db: Session, query: str, feature_type: str) -> FeatureCollection:
    """ searches for feature locations using external APIs or internal data.
        will make use of DataBC, using layer names from the Wally metadata catalogue,
        unless another provider function is specified (e.g. for searching on GWELLS)
    """

    geocoder_features = []

    if feature_type in EXTERNAL_API_SEARCH_URLS:
        geocoder_features = external_search(query, feature_type, EXTERNAL_API_SEARCH_URLS.get(feature_type))
    else:
        geocoder_features = wfs_search(query, feature_type)

    logger.info(geocoder_features)

    return FeatureCollection(geocoder_features)


def lookup_by_text(db: Session, query: str, feature_type: str):
    """ look up features by text (e.g. name, an ID number), returning geojson """

    # query the geocode materialized view, using the tsv column (generated by to_tsvector i.e.
    # text search vector).
    #
    # notes: - adding :* (e.g. `query:*`) indicates prefix matching (partial matches for
    # beginning of word) - plainto_tsquery is similar to to_tsquery but allows spaces, but does
    # NOT support :* prefix matching (exact match to at least 1 word only)

    features = []

    # remove symbols and then convert spaces to the "followed by" operator <->
    # which is similar to `&` but will retain word order when searching.
    query = search_symbols.sub('', query)

    # check if the simplified query contains anything. If not,
    # stop the search here.
    if not search_spaces.sub('', query):
        return FeatureCollection(features)

    query = search_spaces.sub('&', query.strip())
    query_prefix = query + ":*"

    q = select([geocode]) \
        .where(text("tsv @@ to_tsquery(:query_prefix)"))

    if feature_type:
        q = q.where(text("layer=:feature_type"))

    q = q.order_by(
        text("(CASE WHEN geocode_lookup.primary_id = :query THEN 1 ELSE 2 END)"),
        func.ts_rank('tsv', func.to_tsquery(query_prefix))
    ) \
        .limit(5)

    for row in db.execute(q, {"query": query, "query_prefix": query_prefix, "feature_type": feature_type}):
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

    return FeatureCollection(features)
