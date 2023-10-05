"""
Functions for aggregating data from web requests and database records
"""
import pprint
import base64
import datetime
import io
import logging
import requests
import json
import fiona
import math
import re
import time
import os
import zipfile
import sqlalchemy as sa
from tempfile import TemporaryDirectory
from geoalchemy2.elements import WKTElement
from shapely import wkb
from typing import Tuple, List, Optional
from urllib.parse import urlencode
from geojson import FeatureCollection, Feature
from operator import add
from shapely.geometry import Point, Polygon, MultiPolygon, shape, mapping
from shapely.ops import transform
from starlette.responses import Response
from sqlalchemy.orm import Session
from sqlalchemy import func, insert, select
from fastapi import HTTPException

from api.config import WATERSHED_DEBUG
from api.utils import normalize_quantity, normalize_quantity_seconds
from api.layers.freshwater_atlas_watersheds import FreshwaterAtlasWatersheds
from api.layers.freshwater_atlas_stream_networks import FreshwaterAtlasStreamNetworks
from api.v1.aggregator.helpers import transform_4326_3005, transform_3005_4326
from api.v1.hydat.controller import get_point_on_stream, get_station
from api.v1.models.scsb2016.controller import get_hydrological_zone
from api.v1.streams.controller import get_nearest_streams, get_nearest_hydat_stream_segments
from api.v1.watersheds.db_models import GeneratedWatershed, WatershedCache
from api.v1.watersheds.climate import get_mean_annual_precipitation, get_potential_evapotranspiration
from api.v1.watersheds.cdem import CDEM
from api.v1.watersheds.schema import (
    LicenceDetails,
    SurficialGeologyDetails,
    FishObservationsDetails,
    WaterApprovalDetails,
    WatershedDataWarning,
    GeneratedWatershedDetails
)
from api.v1.watersheds.delineate_watersheds import (
    get_full_stream_catchment_area,
    get_upstream_catchment_area,
    get_watershed_using_dem,
    watershed_touches_border
)


from api.v1.aggregator.controller import feature_search, databc_feature_search

from external.docgen.controller import docgen_export_to_xlsx

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger('WATERSHEDS')

SEC_IN_YEAR = 31536000


def calculate_glacial_area(db: Session, polygon: MultiPolygon) -> Tuple[float, float]:
    """
    Calculates percent glacial coverage using the area of `polygon` which intersects with features from
    the DataBC FWA Glaciers dataset.
    returns a tuple of floats with the form (glacial_area, coverage).
    """

    glaciers_layer = 'freshwater_atlas_glaciers'

    glacial_features = feature_search(db, [glaciers_layer], polygon.minimum_rotated_rectangle)[
        0].geojson.features

    glacial_area = 0

    polygon = transform(transform_4326_3005, polygon)

    for glacier in glacial_features:
        glacier_clipped = shape(glacier.geometry).intersection(polygon)

        if not glacier_clipped.area:
            continue

        glacial_area += glacier_clipped.area

    coverage = glacial_area / polygon.area

    return (glacial_area, coverage)


def pcic_data_request(
        polygon: Polygon,
        output_variable: str = 'pr',
        dataset=None):
    """ Returns an average precipitation from the pacificclimate.org climate explorer service """

    pcic_url = "https://services.pacificclimate.org/pcex/api/timeseries?"

    if not dataset:
        dataset = f"{output_variable}_mClim_BCCAQv2_CanESM2_historical-rcp85_r1i1p1_19810101-20101231_Canada"

    params = {
        "id_": dataset,
        "variable": output_variable,
        "area": polygon.minimum_rotated_rectangle.wkt
    }

    req_url = pcic_url + urlencode(params)

    if WATERSHED_DEBUG:
        logger.info('pcic request: %s', req_url)

    try:
        resp = requests.get(req_url)
        resp.raise_for_status()
    except requests.exceptions.HTTPError as e:
        raise HTTPException(status_code=e.response.status_code, detail=str(e))

    return resp.json()


def water_licences_summary(licences: List[Feature], polygon: Polygon) -> LicenceDetails:
    """ takes a list of licences and the search polygon, and returns a
        summary of the licences that fall within the search area.

    """

    total_licenced_qty_m3_yr = 0
    licenced_qty_by_use_type = {}
    active_licences_within_search_area = []
    inactive_licences_within_search_area = []

    # max_quantity_by_licence tracks quantities for licences
    # that have multiple points of diversion (PODs). The quantity
    # is treated differently based on the QUANTITY_FLAG attribute:
    #
    # M       - QUANTITY is the max quantity for the licence, shared across multiple
    #             points of diversion. QUANTITY should be the same for all
    #             records under a licence with this flag and will not be summed.
    # T, D, P - QUANTITY is the quantity per POD record and will be summed
    #             to determine the total quantity for the licence.
    #
    # note: the above is the explanation of how this is handled here in this function,
    # refer to https://catalogue.data.gov.bc.ca/dataset/5549cae0-c2b1-4b96-9777-529d9720803c
    # for the official quantity flag definitions.
    max_quantity_by_licence = {}

    for lic in licences:
        feature_shape = shape(lic.geometry)

        # skip licences outside search area
        if not feature_shape.within(polygon):
            continue

        # skip licence if not a surface water point of diversion (POD)
        # other pod_subtype codes are associated with groundwater.
        if lic.properties['POD_SUBTYPE'] != 'POD':
            continue

        licence_number = lic.properties['LICENCE_NUMBER']
        qty = lic.properties['QUANTITY']
        qty_unit = lic.properties['QUANTITY_UNITS'].strip()
        purpose = lic.properties['PURPOSE_USE']
        priority_date = datetime.datetime.strptime(lic.properties['PRIORITY_DATE'], '%Y-%m-%dZ').date() \
            if lic.properties.get('PRIORITY_DATE', None) else None

        # normalize the quantity units to m3/year. This function returns None
        # if the quantity cannot be normalized; for example, there is an invalid
        # unit (or the unit is "total flow"). In this case, the original quantity
        # will still be available for users to view, but the normalized m3/year
        # table column will be empty. The licence will also not be considered
        # in the sum total if the quantity cannot be converted due to invalid input.
        normalized_qty = normalize_quantity(qty, qty_unit)

        lic.properties['qty_m3_yr'] = normalized_qty
        lic.properties['qty_m3_second'] = normalize_quantity_seconds(qty, qty_unit)
        # List of statuses to watch for when deciding whether or not
        # to consider the licenced quantity for the total licenced usage.
        # It may be possible to only consider POD_STATUS but we should assume
        # there may be data discrepancies, so skip if either POD_STATUS or LICENCE_STATUS
        # is an inactive code.
        LICENCE_STATUSES_TO_SKIP = [
            'Abandoned', 'Canceled', 'Cancelled', 'Expired', 'Inactive'
        ]
        POD_STATUSES_TO_SKIP = [
            'Inactive'
        ]

        # by default, add licence quantities together
        licence_qty_action_function = add

        # licences with a QUANTITY_FLAG of "M" need to be handled separately (see above note
        # for `max_quantity_by_licence`). The `max` function is used.
        # Some QUANTITY_FLAG values are null, so check for that before we process the value as a string.
        if lic.properties.get("QUANTITY_FLAG", None) and lic.properties.get("QUANTITY_FLAG", "").strip() == "M":
            licence_qty_action_function = max

        if lic.properties["LICENCE_STATUS"] not in LICENCE_STATUSES_TO_SKIP and \
                lic.properties["POD_STATUS"] not in POD_STATUSES_TO_SKIP:
            # if the licence has a quantity that we can convert to m3/year,
            # use the action function (either `add` or `max`, as above).
            # some licences have a quantity of 0 and a unit of "total flow",
            # these will be skipped here.
            if normalized_qty is not None:
                max_quantity_by_licence[licence_number] = licence_qty_action_function(
                    max_quantity_by_licence.get(licence_number, 0),
                    normalized_qty
                )
            active_licences_within_search_area.append(lic)
        else:
            inactive_licences_within_search_area.append(lic)

        # organize the licence by purpose use.The WALLY web app will primary display
        # licences broken down by purpose use.
        if purpose is not None:
            # move id to back of purpose name
            try:
                code, name = purpose.split(' - ')
                purpose = f"{name} ({code})"
            except ValueError:
                logger.error(f"Error formatting {purpose}")

            # format licences for each purpose type
            purpose_data = licenced_qty_by_use_type.setdefault(purpose, {
                "qty": 0,
                "licences": [],
                "inactive_licences": []
            })

            licence = Feature(
                geometry=transform(transform_3005_4326,
                                   shape(lic.geometry)),
                id=lic.id,
                properties={
                    "fileNumber": lic.properties["FILE_NUMBER"],
                    "licenceNumber": lic.properties["LICENCE_NUMBER"],
                    "status": lic.properties["LICENCE_STATUS"],
                    "licensee": lic.properties["PRIMARY_LICENSEE_NAME"],
                    "priorityDate": priority_date,
                    "source": lic.properties["SOURCE_NAME"],
                    "quantityPerSec": normalized_qty / SEC_IN_YEAR if normalized_qty else None,
                    "quantityPerYear": normalized_qty,
                    "quantityFlag": lic.properties["QUANTITY_FLAG"],
                    "quantity": lic.properties["QUANTITY"],
                    "quantityUnits": lic.properties["QUANTITY_UNITS"]
                }
            )

            # add licenced quantity if the licence is not canceled.
            if lic.properties["LICENCE_STATUS"] not in LICENCE_STATUSES_TO_SKIP and \
                    lic.properties["POD_STATUS"] not in POD_STATUSES_TO_SKIP:
                if normalized_qty is not None:
                    purpose_data["qty"] = licence_qty_action_function(
                        purpose_data["qty"], normalized_qty)

                licenced_qty_by_use_type[purpose]["licences"].append(licence)

            else:
                licenced_qty_by_use_type[purpose]["inactive_licences"].append(
                    licence)

    # create the list of purpose types.
    licence_purpose_type_list = []
    for purpose, purpose_obj in licenced_qty_by_use_type.items():
        licence_purpose_type_list.append({
            "purpose": purpose,
            "qty": purpose_obj["qty"],
            "licences": purpose_obj["licences"],
            "inactive_licences": purpose_obj["inactive_licences"],
            "units": "m3/year"
        })

    # Create the LicenceDetails summary and populate it with the licences (separated by
    # active/inactive), and statistics for the WALLY web client to display.
    return LicenceDetails(
        licences=FeatureCollection([
            Feature(
                geometry=transform(transform_3005_4326, shape(feat.geometry)),
                id=feat.id,
                properties=feat.properties
            ) for feat in active_licences_within_search_area
        ]),
        inactive_licences=FeatureCollection([
            Feature(
                geometry=transform(transform_3005_4326, shape(feat.geometry)),
                id=feat.id,
                properties=feat.properties
            ) for feat in inactive_licences_within_search_area
        ]),
        total_qty=sum(max_quantity_by_licence.values()),
        total_qty_by_purpose=licence_purpose_type_list,
        projected_geometry_area=polygon.area,
    )


def surface_water_rights_licences(polygon: Polygon):
    """ returns surface water rights licences (filtered by POD subtype)"""
    water_rights_layer = 'water_rights_licences'

    # search with a simplified rectangle representing the polygon.
    # we will do an intersection on the more precise polygon after
    polygon_rect = polygon.minimum_rotated_rectangle
    licences = databc_feature_search(
        water_rights_layer, search_area=polygon_rect)

    polygon_3005 = transform(transform_4326_3005, polygon)

    licence_summary = water_licences_summary(licences.features, polygon_3005)
    licence_summary.projected_geometry_area_simplified = polygon_rect.area
    return licence_summary


def surface_water_approval_points(polygon: Polygon):
    """ returns surface water approval points (filtered by APPROVAL_STATUS)"""
    water_approvals_layer = 'water_approval_points'

    # search with a simplified rectangle representing the polygon.
    # we will do an intersection on the more precise polygon after
    polygon_rect = polygon.minimum_rotated_rectangle
    approvals = databc_feature_search(
        water_approvals_layer, search_area=polygon_rect)

    polygon_3005 = transform(transform_4326_3005, polygon)

    features_within_search_area = []
    total_qty_m3_yr = 0

    for apr in approvals.features:
        feature_shape = shape(apr.geometry)

        # skip approvals outside search area
        if not feature_shape.within(polygon_3005):
            continue

        # skip approval if its not an active licence
        # other approval status' are associated with inactive licences
        if apr.properties['APPROVAL_STATUS'] != 'Current':
            continue

        features_within_search_area.append(apr)

        # the rare water approval record has the units
        # as a suffix in the QUATITY property
        # these are considered bad data points
        # and will be skipped
        try:
            qty = float(apr.properties['QUANTITY'])
        except:
            continue

        qty_unit = apr.properties['QUANTITY_UNITS']

        # null if approval is a works project, most of them are
        if qty and qty_unit:
            qty = normalize_quantity(qty, qty_unit)
            total_qty_m3_yr += qty
            apr.properties['qty_m3_yr'] = qty
        else:
            apr.properties['qty_m3_yr'] = 0

    return WaterApprovalDetails(
        approvals=FeatureCollection([
            Feature(
                geometry=transform(transform_3005_4326, shape(feat.geometry)),
                id=feat.id,
                properties=feat.properties
            ) for feat in features_within_search_area
        ]),
        total_qty=total_qty_m3_yr,
        projected_geometry_area=polygon.area,
        projected_geometry_area_simplified=polygon_rect.area
    )


def get_nearest_stream_name_id(nearest_stream):
    """
    Given a row of FWA stream data, return a tuple containing the stream id, name, and the closest point.
    `nearest_stream` row should be output from the api.v1.streams.controller.get_nearest_streams function.
    """
    nearest_stream_point = nearest_stream.get('closest_stream_point')
    stream_name = nearest_stream.get('gnis_name', '')
    stream_feature_id = nearest_stream.get('linear_feature_id', None)
    point_on_stream = shape(nearest_stream_point)

    return (stream_feature_id, stream_name, point_on_stream)


def get_watershed_id_at_point(db: Session, point: Point):
    """
    given a point (degrees lng lat / EPSG:4326), return the ID
    of the watershed containing it.
    """
    q = db.query(FreshwaterAtlasWatersheds.WATERSHED_FEATURE_ID).filter(
        func.ST_Contains(
            FreshwaterAtlasWatersheds.GEOMETRY,
            func.ST_GeomFromText(
                point.wkt, 4326)
        )
    )

    watershed_id = q.first()
    if not watershed_id:
        if WATERSHED_DEBUG:
            logger.warning("No watershed found")
        return None
    watershed_id = watershed_id[0]

    if WATERSHED_DEBUG:
        logger.info("watershed id %s", watershed_id)

    return watershed_id


def get_upstream_watershed_polygon_count(db: Session, watershed_id: int) -> int:
    """Returns the number of polygons upstream from watershed_id.
    This helps if we want to determine if a group of watershed polygons
    originating from `watershed_id` will take too long to dissolve or will
    take too long to do GIS operations on the resulting area.

    The average polygon size is (very roughly) 0.2 to 0.3 square km, so if
    we want to approximately predict whether an upstream area might be more than
    1000 square km, we can check to ensure there are less than about 4000 polygons.

    This query can be expensive but is much faster than attempting a full watershed
    delineation and finding out too late that we're working in an unmanageable large area.
    """
    q = """
        with subwscode_ltree as (
            SELECT  "WATERSHED_FEATURE_ID" as origin_id,
                    wscode_ltree as origin_wscode,
                    localcode_ltree as origin_localcode,
                    ltree2text(subpath(localcode_ltree, -1))::integer as downstream_tributary,
                    nlevel(localcode_ltree) as downstream_tributary_code_pos
            FROM    freshwater_atlas_watersheds
            WHERE   "WATERSHED_FEATURE_ID" = :watershed_feature_id
        )
        SELECT  count(*)
        FROM    freshwater_atlas_watersheds
        WHERE   wscode_ltree <@ (select origin_wscode from subwscode_ltree)
        AND     ltree2text(subltree(
                    localcode_ltree || '000000'::ltree,
                    (select downstream_tributary_code_pos from subwscode_ltree) - 1,
                    (select downstream_tributary_code_pos from subwscode_ltree) - 0
                ))::integer >= (select downstream_tributary from subwscode_ltree)
        AND (NOT wscode_ltree <@ (select origin_localcode from subwscode_ltree) OR (select origin_wscode from subwscode_ltree) = (select origin_localcode from subwscode_ltree))

    """

    res = db.execute(q, {"watershed_feature_id": watershed_id})

    record = res.fetchone()

    if not record or not record[0]:
        logger.warning(
            'unable to calculate polygon count from watershed feature id %s', watershed_id)
        return None

    return record[0]


def calculate_watershed(
    db: Session,
    user,
    click_point: Point = None,
    watershed_id: int = None,
    hydat_station_number: str = None,
    upstream_method='DEM+FWA',
    dem_source='cdem'
) -> GeneratedWatershedDetails:
    """ estimates the watershed area upstream of a POI and returns a GeneratedWatershedDetails object.

        It uses one of several methods to estimate the upstream area, described below.

        Optional arguments:
        upstream_method: 'FWA+FULLSTREAM', 'FWA+UPSTREAM', 'DEM', or 'DEM+FWA'.
            FWA+FULLSTREAM: Use the Freshwater Atlas to return the catchment area of the entire
                        selected stream.
            FWA+UPSTREAM: Estimate the upstream catchment area using only the Freshwater Atlas.
                 This will be accurate to the FWA linework around the outer perimeter
                 but will over or under-estimate the area around the point of interest (because
                 the watershed polygons forming the catchment area will not be split, even if
                 the point of interest is in the middle of a polygon)

            DEM: Use the DEM (Digital Elevation Model) to delineate the catchment.
                 WhiteboxTools is used. See `get_watershed_using_dem` for more info.
                 This is more accurate around the point of interest but the outer reaches
                 are less smooth than the FWA linework and may slightly under or overestimate
                 around the outer perimeter of the watershed.

            DEM+FWA: Attempt to combine both the DEM and FWA methods by using the DEM close
                     to the point of interest, and the FWA around the outer perimeter. This
                     is the default.
    """
    start = time.perf_counter()
    warnings = []

    if click_point and watershed_id:
        raise ValueError(
            "Do not provide both point and watershed_id at the same time")

    if not click_point and not watershed_id and not hydat_station_number:
        raise ValueError(
            "Must provide either a starting point (lat, long), a starting watershed ID, or a HYDAT station number")

    if watershed_id and not upstream_method.startswith("FWA"):
        raise ValueError(
            f"Starting watershed ID incompatible with {upstream_method}. Use only FWA methods.")

    if WATERSHED_DEBUG:
        logger.info("calculating watershed")

    stream_name = ''
    point_on_stream = None
    stream_feature_id = None

    # if this watershed is based on a HYDAT station, look up the lat/long.
    # Since sometimes the lat/long can be incorrect or still in an ambigious location
    # (e.g. at a confluence where the station point may be closer to a tributary than
    # the centreline of the stream being monitored), correct the point onto the stream
    # in the Station name.
    if hydat_station_number:
        point_on_stream, stream_feature_id, click_point = get_point_on_stream(db, hydat_station_number)

    elif click_point:
        # move the click point to the nearest stream based on the FWA Stream Networks.
        # this will make it easier to snap the point to the Flow Accumulation raster
        # we will generate.
        nearest_stream = get_nearest_streams(db, click_point, limit=1)[0]
        stream_feature_id, stream_name, point_on_stream = get_nearest_stream_name_id(nearest_stream)

        stream_distance = transform(
            transform_4326_3005, point_on_stream
        ).distance(
            transform(transform_4326_3005, click_point))

        # create a warning if the distance between the stream and click point is
        # greater than stream_distance_warning_threshold
        stream_distance_warning_threshold = 500
        if stream_distance > stream_distance_warning_threshold:
            point_not_on_stream_warning = WatershedDataWarning(
                message=f"This point is more than {stream_distance_warning_threshold} m from the nearest stream" +
                " (based on Freshwater Atlas stream mapping)." +
                " WALLY's Surface Water Analysis is applicable to points of interest along streams." +
                " If you believe this is an error, please contact the WALLY team."
            )
            warnings.append(point_not_on_stream_warning)

    if point_on_stream:
        # get the ID of the watershed we are starting in.
        # this will be used later to help with queries against the fundamental watersheds.
        watershed_id = get_watershed_id_at_point(db, point_on_stream)

    watershed_point = None
    watershed = None

    # declare some variables that will be used for watershed metadata.
    dem_error = None
    is_near_border = bool(len(watershed_touches_border(db, watershed_id)))

    # the location of point after correcting/snapping to a stream.
    # This means either snapping to a vector FWA stream or using a SnapPourPoint
    # routine (SnapPourPoints or JensonSnapPourPoints).  If both, this value
    # will be from the SnapPourPoint routine since that will be done after
    # moving the point to a stream.
    snapped_point = point_on_stream or click_point

    # choose method based on function argument.
    if upstream_method.startswith('DEM'):
        # estimate the watershed using the DEM
        (watershed, snapped_point, dem_error) = get_watershed_using_dem(
            db, point_on_stream, stream_feature_id, watershed_id,
            dem_source=dem_source, use_fwa=upstream_method == 'DEM+FWA')
        watershed_source = "Estimated using CDEM and WhiteboxTools."
        generated_method = 'generated_dem'
        watershed_point = base64.urlsafe_b64encode(
            point_on_stream.wkb).decode('utf-8')

        if dem_error:
            dem_error_warning = WatershedDataWarning(
                message="Your watershed could not be refined to the dropped point. There may be significant" +
                " extra area downstream of your point of interest, or other errors. Please carefully verify the watershed" +
                " boundary."
            )
            warnings.append(dem_error_warning)

        # ensure that we stop here if the watershed touches a border.
        if upstream_method == 'DEM+FWA' and is_near_border:
            no_cross_border_fwa_warning = WatershedDataWarning(
                message=f"This watershed was delineated from a DEM without using the Freshwater Atlas" +
                " because it is close to or crosses a boundary with another jurisdiction where FWA data" +
                " is not available. Please verify estimated watershed boundary."
            )
            warnings.append(no_cross_border_fwa_warning)

        # if using DEM+FWA and not near a border, add the source info for CDEM/WBT/FWA.
        elif upstream_method == 'DEM+FWA':
            watershed_source = "Estimated by combining the result from CDEM/WhiteboxTools " + \
                               "with Freshwater Atlas fundamental watershed polygons."
            generated_method = 'generated_dem_fwa'

    elif upstream_method == 'FWA+UPSTREAM':
        watershed = get_upstream_catchment_area(db, watershed_id)
        watershed_source = "Estimated by combining Freshwater Atlas watershed polygons that are " + \
            "determined to be part of the selected stream based on FWA_WATERSHED_CODE and upstream " + \
            "of the selected point based on LOCAL_WATERSHED_CODE. Note: the watershed polygon " + \
            "containing the selected point is included."
        generated_method = 'generated'
        watershed_point = watershed_id

    elif upstream_method == 'FWA+FULLSTREAM':
        watershed = get_full_stream_catchment_area(db, watershed_id)
        watershed_source = "Estimated by combining Freshwater Atlas watershed polygons that are " + \
            "determined to be part of the selected stream based on FWA_WATERSHED_CODE."
        generated_method = 'generated_full_stream'
        watershed_point = watershed_id

    else:
        raise ValueError(
            f"Invalid method {upstream_method}. Valid methods are DEM, DEM+FWA, FWA+UPSTREAM, FWA+FULLSTREAM")

    feature = Feature(
        geometry=watershed,
        id=f"{generated_method}.{watershed_point}",
        properties={
            "name": f"Estimated catchment area {f'({stream_name})' if stream_name else ''}",
            "watershed_source": watershed_source,
            "stream_name": stream_name
        }
    )
    if not feature:
        # was not able to calculate a watershed with the provided params.
        # return None; the calling function will skip this calculated watershed
        # and return other pre-generated ones.
        logger.info(
            "skipping calculated watershed based on watershed feature id %s", watershed_id)
        return None

    feature.properties['FEATURE_AREA_SQM'] = transform(
        transform_4326_3005, shape(feature.geometry)).area

    elapsed = (time.perf_counter() - start)

    logger.info('Time to calculate watershed: %s', elapsed)

    watershed_resp = GeneratedWatershedDetails(
        warnings=warnings,
        watershed=feature,
        click_point=click_point.wkt,
        snapped_point=snapped_point.wkt,
        dem_source=dem_source,
        from_cache=False,
        fwa_watershed_id=watershed_id,
        wally_watershed_id=f"{generated_method}.{watershed_point}",
        upstream_method=generated_method,
        is_near_border=is_near_border,
        processing_time=elapsed,
        dem_error=dem_error)

    watershed_resp.generated_watershed_id = store_generated_watershed(
        db, user, watershed_resp)

    return watershed_resp


def get_databc_watershed(watershed_id: str):
    """ finds a watershed in DataBC watershed layers

    """
    watershed_layer = '.'.join(watershed_id.split('.')[:2])
    watershed_feature = watershed_id.split('.')[-1:]

    id_props = {
        'WHSE_BASEMAPPING.FWA_ASSESSMENT_WATERSHEDS_POLY': 'WATERSHED_FEATURE_ID',
        'WHSE_BASEMAPPING.FWA_WATERSHEDS_POLY': 'WATERSHED_FEATURE_ID',
        'WHSE_WATER_MANAGEMENT.HYDZ_HYD_WATERSHED_BND_POLY': 'HYD_WATERSHED_BND_POLY_ID'
    }

    source_urls = {
        'WHSE_BASEMAPPING.FWA_ASSESSMENT_WATERSHEDS_POLY': 'https://catalogue.data.gov.bc.ca/dataset/freshwater-atlas-assessment-watersheds',
        'WHSE_BASEMAPPING.FWA_WATERSHEDS_POLY': 'https://catalogue.data.gov.bc.ca/dataset/freshwater-atlas-watersheds',
        'WHSE_WATER_MANAGEMENT.HYDZ_HYD_WATERSHED_BND_POLY': 'https://catalogue.data.gov.bc.ca/dataset/hydrology-hydrometric-watershed-boundaries'
    }

    cql_filter = f"{id_props[watershed_layer]}={watershed_feature}"

    watershed = databc_feature_search(watershed_layer, cql_filter=cql_filter)
    if len(watershed.features) != 1:
        raise HTTPException(
            status_code=404, detail=f"Watershed with id {watershed_id} not found")

    ws = watershed.features[0]

    ws.properties['name'] = ws.properties.get(
        'GNIS_NAME_1', None) or ws.properties.get('SOURCE_NAME', None)
    ws.properties['watershed_source'] = source_urls.get(watershed_layer, None)

    return ws


def surficial_geology(polygon: Polygon):
    """ surficial geology information from DataBC
    https://catalogue.data.gov.bc.ca/dataset/terrain-inventory-mapping-tim-detailed-polygons-with-short-attribute-table-spatial-view

    """

    surf_geol_layer = "WHSE_TERRESTRIAL_ECOLOGY.STE_TER_INVENTORY_POLYS_SVW"

    polygon_rect = polygon.minimum_rotated_rectangle

    fc = databc_feature_search(surf_geol_layer, polygon_rect)

    polygon_3005 = transform(transform_4326_3005, polygon)

    surficial_geology_dominant_types = {}
    surficial_geology_features_by_type = {}

    coverage_area = 0

    for feature in fc.features:

        feature_shape = shape(feature.geometry)
        feature_shape_intersect = feature_shape.intersection(polygon_3005)

        # DOMINANT_SURFICIAL_MATERIAL is the property we are looking for.
        # it is a description of the surficial geology deposition method.
        dominant_type = feature.properties.get(
            'DOMINANT_SURFICIAL_MATERIAL', None)

        if not dominant_type or not feature_shape_intersect.area:
            continue

        # initialize area for new soil types
        if not surficial_geology_dominant_types.get(dominant_type, None):
            surficial_geology_dominant_types[dominant_type] = 0

        # initialize list of features for new soil types
        if not surficial_geology_features_by_type.get(dominant_type, None):
            surficial_geology_features_by_type[dominant_type] = []

        # add to total area for this soil type
        surficial_geology_dominant_types[dominant_type] += feature_shape_intersect.area

        # create a SRID 4326 feature
        # this feature will be returned in the JSON response and can
        # be displayed on the map.
        geom_4326 = transform(transform_3005_4326, feature_shape_intersect)
        feat_4326 = Feature(
            geometry=geom_4326,
            id=feature.id,
            properties=feature.properties
        )

        # adding the centroid makes it easier to add labels later
        feat_4326.properties['centre'] = geom_4326.centroid.coords

        surficial_geology_features_by_type[dominant_type].append(feat_4326)

        coverage_area += feature_shape_intersect.area

    surf_geol_list = []
    geol_type_features = []

    for soil_type, area in surficial_geology_dominant_types.items():

        soil_type_fc = FeatureCollection(
            surficial_geology_features_by_type.get(soil_type, []))

        surf_geol_list.append({
            "soil_type": soil_type,
            "area_within_watershed": area,
            "geojson": soil_type_fc

        })

    return SurficialGeologyDetails(
        summary_by_type=surf_geol_list,
        coverage_area=coverage_area,
    )


def get_cached_watershed(db: Session, generated_watershed_id):
    """
    Check for a cached watershed, returning a feature or None

    Watersheds are cached by `generated_watershed_id`. This ensures that the
    cached watershed is only for the watershed generated by the user during their
    current session.  If another user is looking in the same place, or if the same
    user starts over and places a point (in the same place or another location), they
    will have another, separate `generated_watershed_id`.  This way there are
    never conflicts or mixups between cached watersheds.

    The `last_accessed_date` will be updated when the cached watershed is retrieved
    so that the prune_watershed_cache trigger won't delete the record if it has been used
    recently.
    """

    q = """
    update      watershed_cache
    set         last_accessed_date = now()
    where       generated_watershed_id = (
        select      generated_watershed_id
        from        watershed_cache
        where       generated_watershed_id = :generated_watershed_id
        for update skip locked
    )
    returning   generated_watershed_id, watershed
    """
    res = db.execute(q, {"generated_watershed_id": generated_watershed_id})
    row = res.one_or_none()

    if not row:
        return None

    data = json.loads(row['watershed'])
    feat = data.pop('watershed')
    geom = shape(feat.pop('geometry'))

    # at the time we inserted the json representation of the cached watershed,
    # the json itself did not contain the generated watershed id. However, it was given
    # to the generated_watershed_id column on insert.
    # If this is confusing, we could alter to the `store_generated_watershed` SQL
    # to update the JSON field after we are assigned the ID.
    data['generated_watershed_id'] = row['generated_watershed_id']
    data['watershed'] = Feature(
        id=feat['id'], geometry=geom, properties=feat['properties'])

    ws = GeneratedWatershedDetails(**data)
    ws.from_cache = True
    return ws


def store_generated_watershed(db: Session, user, watershed: GeneratedWatershedDetails):
    """
    store generated watershed metadata, and put a copy in the temporary cache.
    The cache is cleared by the database trigger "prune_watershed_cache".
    Cached copies that haven't been accessed in over 1 hour are cleared on insert.
    """

    generated_watershed = insert(GeneratedWatershed) \
        .values(
        create_user=user.user_uuid,
        update_user=user.user_uuid,
        wally_watershed_id=watershed.wally_watershed_id,
        processing_time=watershed.processing_time,
        upstream_method=watershed.upstream_method,
        is_near_border=watershed.is_near_border,
        click_point=WKTElement(watershed.click_point, srid=4326),
        snapped_point=WKTElement(watershed.snapped_point, srid=4326),
        dem_source=watershed.dem_source,
        dem_error=watershed.dem_error,
        area_sqm=watershed.watershed.properties['FEATURE_AREA_SQM']
    ) \
        .returning(GeneratedWatershed.generated_watershed_id) \
        .cte('generated_metadata')

    q = insert(WatershedCache) \
        .values(
        generated_watershed_id=select(
            [sa.column('generated_watershed_id')]).scalar_subquery().select_from(generated_watershed),
        watershed=watershed.json()) \
        .returning(WatershedCache.generated_watershed_id)

    res = db.execute(q)
    generated_watershed_id = res.first()[0]
    db.commit()
    return generated_watershed_id


def get_watershed_at_inferred_hydat_location(
    db: Session,
    user,
    hydat_station_number: str,
    expected_drainage_area: float,
    upstream_method='DEM+FWA'
):

    stream_segments = get_nearest_hydat_stream_segments(db, hydat_station_number)

    closest_result = None
    closest_result_vs_expected = None

    if expected_drainage_area > 1000:
        upstream_method = 'FWA+UPSTREAM'

    for stream in stream_segments:
        logger.info("trying from stream at %s", stream.stream_point.wkt)
        watershed = calculate_watershed(
            db, user, click_point=stream.stream_point, upstream_method=upstream_method
        )

        # check if this stream's watershed result is close to the expected drainage area,
        # if so, stop now and return it.
        ws_area = watershed.watershed.properties['FEATURE_AREA_SQM'] / 1e6
        ws_area_vs_expected = abs(ws_area - expected_drainage_area) / expected_drainage_area
        logger.info("stream at %s was %s off from expected drainage area",
                    stream.stream_point.wkt, ws_area_vs_expected)
        if ws_area_vs_expected < 0.10:
            return watershed

        # first iteration - our first result is automatically the closest.
        if not closest_result:
            closest_result = watershed
            closest_result_vs_expected = ws_area_vs_expected

        # otherwise, check for a new closest result
        elif ws_area_vs_expected < closest_result_vs_expected:
            closest_result = watershed
            closest_result_vs_expected = ws_area_vs_expected

    # nothing was within the threshold, but we'll return the closest match.
    # it can be manually checked.
    logger.info("No result met threshold (10%%), best result was %s (%s)",
                closest_result_vs_expected, closest_result.watershed.properties['FEATURE_AREA_SQM'])
    return closest_result


def get_watershed_at_hydat_station(
    db: Session,
    user,
    hydat_station_number: str = None,
    upstream_method='DEM+FWA',
):
    """Calculate the watershed at a HYDAT station.

    HYDAT station coordinates are often incorrect (not on the stream) or are
    in an ambiguous location (marked at the confluence of two streams, while only
    monitoring one).

    We first try to see if we can get a result that matches the listed drainage area
    (from the hydat.stations table) using the HYDAT coordinates.
    If that doesn't work, we'll inspect the station name and see if we can correct
    the coordinates onto a stream with the same name as the station.
    """

    # default upstream method
    upstream_method = 'DEM+FWA'

    stn = get_station(db, hydat_station_number)

    # don't delineate watersheds expected to be more than 1000 km2.
    if stn.drainage_area_gross and stn.drainage_area_gross > 1000:
        logger.info(
            'Hydat station %s - %s watershed expected to be too large to refine by DEM. Falling back on FWA only.',
            stn.station_number, stn.station_name)
        upstream_method = 'FWA+UPSTREAM'

    # if we don't have an expected area to compare our result to, skip to the HYDAT "corrected"
    # method.  This will try to snap the point to a stream with the same name as the HYDAT
    # station name.
    # TODO: evaluate whether this method is better than trying raw coords 1st, then
    # corrected by stream name 2nd. We may want to default to this method first.
    if not stn.drainage_area_gross:
        logger.info(
            'Hydat station %s - no drainage area listed.  Counting watershed polygons and defaulting to correcting point coords to the stream in the station name.',
            stn.station_number, stn.station_name)
        watershed_id = get_watershed_id_at_point(db, stn.geom)

        # we don't have access to an upstream area estimate, but we
        # still need to limit when we use the DEM delineation.
        # use 4000 upstream polygons as our limit to approximate 1000 sq km (the
        # cutoff size is completely arbitrary, we just want to avoid delineating
        # huge watersheds).
        if get_upstream_watershed_polygon_count(db, watershed_id) > 4000:
            logger.info(
                'Hydat station %s - %s watershed expected to be too large to refine by DEM. Falling back on FWA only.',
                stn.station_number, stn.station_name)
            upstream_method = 'FWA+UPSTREAM'
        return calculate_watershed(
            db, user, hydat_station_number=stn.station_number, upstream_method=upstream_method
        )

    # if we do have a drainage area to compare to, start with the regular method of delineating
    # from coordinates. For most HYDAT stations, the coordinates are enough to draw the watershed.
    watershed = calculate_watershed(
        db, user, click_point=stn.geom, upstream_method=upstream_method
    )

    # If an area is listed on the HYDAT station, we'll use it to make sure the difference
    # between our delineated watershed and the listed area is within reason.  The most common
    # reason it wouldn't be is if the HYDAT coordinates don't line up with the stream that
    # the station is actually monitoring (or is at an ambiguous confluence where it's not
    # clear from the coordinates which tributary is being monitored).
    ws_area = watershed.watershed.properties['FEATURE_AREA_SQM'] / 1e6
    ws_area_vs_expected = abs(ws_area - stn.drainage_area_gross) / stn.drainage_area_gross

    if ws_area_vs_expected < 0.10:
        logger.info('Success: HYDAT watershed within 10%% of listed area. (%s vs %s: off by %s from listed area)',
                    round(ws_area, 1), round(stn.drainage_area_gross, 1), round(ws_area_vs_expected, 3))
        return watershed

    # if the result is more than +/- 10% of the listed area, try again using the HYDAT station
    # as input.  calculate_watershed with the HYDAT station parameter corrects the coordinates
    # to the stream nearest the HYDAT station, with an attempt to match the stream name from
    # the station name.
    logger.info("Drainage area %s doesn't agree with listed area %s (off by %s of listed area)",
                round(ws_area, 1), round(stn.drainage_area_gross, 1), round(ws_area_vs_expected, 3))
    hydat_corrected_watershed = calculate_watershed(
        db, user, hydat_station_number=stn.station_number, upstream_method=upstream_method
    )

    hy_area = hydat_corrected_watershed.watershed.properties['FEATURE_AREA_SQM'] / 1e6
    hy_area_vs_expected = abs(hy_area - stn.drainage_area_gross) / stn.drainage_area_gross

    # compare the result after trying to correct for the Hydat station name.
    # If we managed to get closer to the listed area, return the corrected result.
    if hy_area_vs_expected < 0.10:
        logger.info("Using corrected result for station %s - %s (new area %s km2 is off by %s from listed area)",
                    stn.station_number, stn.station_name, round(hy_area, 1), round(hy_area_vs_expected, 3))
        return hydat_corrected_watershed

    logger.warn(
        "Warning: Corrected result doesn't agree with listed area (off by %s from listed area).",
        round(hy_area_vs_expected, 3))

    logger.warn('Trying to infer the correct location by delineating from multiple nearby streams.')

    inferred_watershed = get_watershed_at_inferred_hydat_location(
        db, user, stn.station_number, stn.drainage_area_gross)

    if not inferred_watershed:
        inferred_area_vs_expected = 1
    else:
        inferred_watershed_area = inferred_watershed.watershed.properties['FEATURE_AREA_SQM'] / 1e6
        inferred_area_vs_expected = abs(inferred_watershed_area - stn.drainage_area_gross) / stn.drainage_area_gross

    if inferred_watershed and inferred_area_vs_expected < 0.10:
        logger.info('Found a suitable HYDAT watershed by inferring the most likely HYDAT location based on expected drainage area.')
        logger.info(
            'Original estimate was %s different from the expected area, inferred estimate is %s different',
            ws_area_vs_expected, inferred_area_vs_expected)
        return inferred_watershed

    # we couldn't get a good result.  Return the best one, it can be manually checked/QA'd.
    result_vs_expected = {
        "watershed": ws_area_vs_expected,
        "hydat_corrected_watershed": hy_area_vs_expected,
        "inferred_watershed": inferred_area_vs_expected
    }
    result_map = {
        "watershed": watershed,
        "hydat_corrected_watershed": hydat_corrected_watershed,
        "inferred_watershed": inferred_watershed
    }

    best_result = min(result_vs_expected, key=result_vs_expected.get)
    logger.info("best result for HYDAT station was %s. (%s)", best_result, result_vs_expected.get(best_result))
    return result_map.get(best_result)


def get_watershed(
        db: Session, user, watershed_feature: str, generated_watershed_id: Optional[int] = None) -> GeneratedWatershedDetails:
    """
    finds a watershed by either generating it or looking it up in cache.

    `watershed_feature` (also called `wally_watershed_id` in the GeneratedWatershed model)
    is of the format <watershed_type>.<watershed_id> where watershed type is
    a code indicated how the watershed was generated, and watershed_id is either
    the starting watershed_feature_id, or a base64 encoded WKT POINT feature.

    Watershed types `generated` and `generated_fullstream` are upstream catchment methods
    that use only the Freshwater Atlas. These methods need the ID of the fundamental watershed
    polygon containing the point of interest in order to calculate the catchment area.
    `generated_dem_fwa` and `generated_dem` involve a Digital Elevation Model (DEM) and estimate the
    catchment area from specified point coordinates (as a base64 encoded WKT POINT).

    `watershed_feature` format: <watershed_type>.<watershed_id>
    watershed_type        | watershed_id
    --------------        | ------------
    generated             | starting watershed_feature_id (from FreshwaterAtlasWatersheds database model)
    generated_fullstream  | starting watershed_feature_id
    generated_dem_fwa     | base64-encoded WKT POINT
    generated_dem         | base64-encoded WKT POINT
    hydat                 | station_number

    Note: this feature can also be used to look up watersheds from DataBC using the same format.
    It used to support this, but is no longer used. If this is a requirement in the future,
    support for it can be added to this function using by calling get_databc_watershed(watershed_feature),
    where `watershed_feature` is of the format <databc_layer_id>.<feature_id>.
    """
    watershed_layer = '.'.join(watershed_feature.split('.')[:-1])
    watershed_feature_id = watershed_feature.split('.')[-1:]
    watershed = None

    if WATERSHED_DEBUG:
        logger.debug("watershed_feature_id:  %s ;  generated_watershed_id:  %s",
                     watershed_feature_id, generated_watershed_id)

    # if we have this catchment's generated watershed ID, check to see if there's a cached
    # copy.
    # conservatively use generated_watershed_id instead of watershed_feature.
    # this ensures a user's watershed is cached during their Surface Water session
    # but prevents potential conflicts if the catchment functions were somehow called
    # with different settings.
    cached_watershed = None
    if generated_watershed_id:
        cached_watershed = get_cached_watershed(db, generated_watershed_id)

    if cached_watershed:
        logger.info('-- returning cached watershed from generated_watershed_id=%s',
                    cached_watershed.generated_watershed_id)
        return cached_watershed

    # if we generated this watershed, use the catchment area
    # generation function to get the shape.
    if watershed_layer == 'generated':
        watershed_id = int(watershed_feature_id[0])
        watershed = calculate_watershed(
            db, user, watershed_id=watershed_id, upstream_method='FWA+UPSTREAM')

    elif watershed_layer == 'generated_dem_fwa':
        logger.info(watershed_feature_id[0])
        point = wkb.loads(base64.urlsafe_b64decode(watershed_feature_id[0]))
        watershed = calculate_watershed(
            db, user, click_point=point, upstream_method='DEM+FWA')

    elif watershed_layer == 'generated_dem':
        point = wkb.loads(base64.urlsafe_b64decode(watershed_feature_id[0]))
        watershed = calculate_watershed(
            db, user, click_point=point, upstream_method='DEM')

    elif watershed_layer == 'generated_full_stream':
        watershed_id = watershed_feature_id[0]
        watershed = calculate_watershed(
            db, user, watershed_id=watershed_id, upstream_method='FWA+FULLSTREAM')

    elif watershed_layer == 'hydat':
        station_number = watershed_feature_id[0]
        watershed = get_watershed_at_hydat_station(
            db, user, hydat_station_number=station_number, upstream_method='DEM+FWA'
        )

    else:
        raise HTTPException(
            status_code=500, detail="Unable to determine type of watershed. Please contact the WALLY team.")

    return watershed


def calculate_daylight_hours_usgs(day: int, latitude_r: float):
    """ calculates daily radiation for a given day and latitude (latitude in radians)
        https://pubs.usgs.gov/sir/2012/5202/pdf/sir2012-5202.pdf
    """

    declination = 0.4093 * math.sin((2 * math.pi * day / 365) - 1.405)
    acos_input = -1 * math.tan(declination) * math.tan(latitude_r)
    sunset_angle = math.acos(acos_input)

    return (24 / math.pi) * sunset_angle


def get_hillshade(slope_rad: float, aspect_rad: float, azimuth: float = 180.0, altitude: float = 45.0):
    """
    Calculates the percentage hillshade (solar_exposure) value
    based on the average slope and aspect of a point
    """

    if slope_rad is None or aspect_rad is None:
        return None

    if slope_rad < 0 or slope_rad > 2 * math.pi:
        raise ValueError('slope_rad %s out of bounds. Ensure the value is in radians.', slope_rad)

    if aspect_rad < 0 or aspect_rad > 2 * math.pi:
        raise ValueError('aspect_rad %s out of bounds. Ensure the value is in radians.', aspect_rad)

    azimuth_rad = math.radians(azimuth)
    altitude_rad = math.radians(altitude)

    shade_value = math.sin(altitude_rad) * math.sin(slope_rad) \
        + math.cos(altitude_rad) * math.cos(slope_rad) \
        * math.cos((azimuth_rad - math.pi / 2.) - aspect_rad)

    return abs(shade_value)


def extract_poly_coords(geom):
    if geom.type == 'Polygon':
        exterior_coords = geom.exterior.coords[:]
        interior_coords = []
        for interior in geom.interiors:
            interior_coords += interior.coords[:]
    elif geom.type == 'MultiPolygon':
        exterior_coords = []
        interior_coords = []
        for part in geom:
            epc = extract_poly_coords(part)  # Recursive call
            exterior_coords += epc['exterior_coords']
            interior_coords += epc['interior_coords']
    else:
        raise ValueError('Unhandled geometry type: ' + repr(geom.type))
    return {'exterior_coords': exterior_coords,
            'interior_coords': interior_coords}


def export_summary_as_xlsx(data: dict):
    """ exports watershed summary data as an excel file
        using a template in the ./templates directory.
    """

    cur_date = datetime.datetime.now().strftime("%Y%m%d")

    ws_name = data.get("watershed_name", "Surface_Water")
    ws_name.replace(" ", "_")

    filename = f"{cur_date}_{ws_name}"

    dirname = os.path.dirname(__file__)
    xlsx_template = "/app/api/v1/watersheds/templates/SurfaceWater.xlsx"
    
    excel_file = docgen_export_to_xlsx(
        data, xlsx_template, filename)

    return Response(
        content=excel_file,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename={filename}.xlsx"}
    )


def export_summary_as_zipped_shp(geom: Polygon, data: dict):
    """ exports watershed summary data as a zipped Shapefile """

    zip_buffer = io.BytesIO()

    cur_date_compact = datetime.datetime.now().strftime("%Y%m%d")
    cur_date = datetime.datetime.now().strftime("%Y-%m-%d")

    ws_name = data.get("watershed_name", "Surface_Water")
    ws_name.replace(" ", "_")

    filename = f"{cur_date_compact}_{ws_name}"

    with TemporaryDirectory() as shpdir:
        tmp_shp_file = shpdir + f"/{filename}.shp"

        # Define a Polygon feature geometry with properties that include
        # some of the key attributes used for modeling.
        poly_schema = {
            'geometry': 'Polygon',
            'properties': {
                'id': 'str',
                'name': 'str',
                'created': 'str',
                'area_sqm': 'float:15.2',
                'med_elev': 'float:15.2',
                'hyd_zone': 'int',
                'glac_cov': 'float:15.2',
                'precip': 'float:15.2',
                'pet': 'float:15.2',
                'avg_slop': 'float:15.2',
                'sol_exp': 'float:15.2'
            },
        }

        # Write a new Shapefile with the area of interest
        with fiona.open(tmp_shp_file, 'w', 'ESRI Shapefile', poly_schema, crs=f"EPSG:4326") as c:
            c.write({
                'geometry': mapping(geom),
                'properties': {
                    'id': data.get("watershed_id"),
                    'name': ws_name,
                    'created': cur_date,
                    'area_sqm': data.get("watershed_area"),
                    'med_elev': data.get("median_elevation"),
                    'hyd_zone': data.get("hydrological_zone"),
                    'glac_cov': data.get("glacial_coverage"),
                    'precip': data.get("annual_precipitation"),
                    'pet': data.get("potential_evapotranspiration"),
                    'avg_slop': data.get("average_slope"),
                    'sol_exp': data.get("solar_exposure")
                },
            })

        with zipfile.ZipFile(zip_buffer, 'a', zipfile.ZIP_DEFLATED, False) as zip_file:
            for dirname, _, files in os.walk(shpdir):
                for f in files:
                    zip_file.write(os.path.join(dirname, f), arcname=f)

    return Response(
        content=zip_buffer.getvalue(),
        headers={"Content-Disposition": f"attachment; filename={filename}.zip"})


def find_50k_watershed_codes(db: Session, geom: Polygon):
    """ returns an array of 50k watershed codes (older watershed codes) within the watershed area """

    ws_wkt = geom.wkt

    q = db.query(
        func.distinct(FreshwaterAtlasStreamNetworks.WATERSHED_CODE_50K)) \
        .filter(
            func.st_intersects(
                FreshwaterAtlasStreamNetworks.GEOMETRY,
                func.ST_GeomFromText(ws_wkt, 4326)
            )
    ).filter(FreshwaterAtlasStreamNetworks.WATERSHED_CODE_50K.isnot(None))

    codes = [code for sublist in q.all() for code in sublist]

    # the Stream Networks layer returns codes as one long number, but the proper legacy
    # format is 119-111111-22222-22222 .... (number of digits per segment: 3-6-5-5-5...)
    # use regex to format the number groups.
    # the last digit was arbitrarily set to 6 until documentation on the correct format for
    # these legacy codes is found.
    re_pattern = r"(\d{3})(\d{6})(\d{5})(\d{5})(\d{5})(\d{5})(\d{5})(\d{5})(\d{6})"

    formatted_codes = []

    for code in codes:
        segments = re.findall(re_pattern, code)[0]
        # truncate all-zero codes at end (e.g. 119-118400-00000-00000-00000 ....)
        fwa_20k_code = '-'.join([s for s in segments if s != len(s) * '0'])
        formatted_codes.append(fwa_20k_code)

    return sorted(formatted_codes, key=len)


def known_fish_observations(polygon: Polygon):
    """ returns fish observation data from within a watershed polygon"""
    fish_observations_layer = 'fish_observations'

    # search with a simplified rectangle representing the polygon.
    # we will do an intersection on the more precise polygon after
    polygon_rect = polygon.minimum_rotated_rectangle
    fish_observations = databc_feature_search(
        fish_observations_layer, search_area=polygon_rect)

    polygon_3005 = transform(transform_4326_3005, polygon)

    features_within_search_area = []
    # observation_count_by_species = {}
    # life_stages_by_species = {}
    # observation_date_by_species = {}

    fish_species_data = {}

    for feature in fish_observations.features:
        feature_shape = shape(feature.geometry)

        # skip observations outside search area
        if not feature_shape.within(polygon_3005):
            continue

        # skip point if not a direct observation
        # summary points are consolidated observations.
        if feature.properties['POINT_TYPE_CODE'] != 'Observation':
            continue

        species_name = feature.properties['SPECIES_NAME']
        life_stage = feature.properties['LIFE_STAGE']
        observation_date = datetime.datetime.strptime(feature.properties['OBSERVATION_DATE'], '%Y-%m-%dZ').date() \
            if feature.properties['OBSERVATION_DATE'] is not None else None  # 1997-02-01Z

        if species_name is not None:
            if not fish_species_data.get(species_name, None):
                fish_species_data[species_name] = {
                    'count': 0,
                    'life_stages': [],
                    'observation_date_min': None,
                    'observation_date_max': None
                }

            # add to observation count for this species
            fish_species_data[species_name]['count'] += 1

            # add life stage observed uniquely
            if life_stage is not None:
                if life_stage not in fish_species_data[species_name]['life_stages']:
                    fish_species_data[species_name]['life_stages'].append(
                        life_stage)

            # add oldest and latest observation of species within watershed
            if observation_date is not None:
                if fish_species_data[species_name]['observation_date_min'] is None:
                    fish_species_data[species_name]['observation_date_min'] = observation_date
                if fish_species_data[species_name]['observation_date_max'] is None:
                    fish_species_data[species_name]['observation_date_max'] = observation_date

                if observation_date < fish_species_data[species_name]['observation_date_min']:
                    fish_species_data[species_name]['observation_date_min'] = observation_date
                if observation_date > fish_species_data[species_name]['observation_date_max']:
                    fish_species_data[species_name]['observation_date_max'] = observation_date

        features_within_search_area.append(feature)

    # transform multi-dict to flat list
    fish_species_data_list = []
    for key, val in fish_species_data.items():
        fish_species_data_list.append({
            'species': key,
            'count': val['count'],
            'life_stages': parse_fish_life_stages(val['life_stages']),
            'observation_date_min': val['observation_date_min'],
            'observation_date_max': val['observation_date_max']
        })

    return FishObservationsDetails(
        fish_observations=FeatureCollection([
            Feature(
                geometry=transform(transform_3005_4326, shape(feat.geometry)),
                id=feat.id,
                properties=feat.properties
            ) for feat in features_within_search_area
        ]),
        fish_species_data=fish_species_data_list
    )


def get_stream_inventory_report_link_for_region(point: Point):
    """ Returns Fish Inventory Data Query (FIDQ) links for streams within this
        watershed area.
    """
    point_3005 = transform(transform_4326_3005, point)

    # look up region that this point is in
    cql_filter = f"""INTERSECTS(SHAPE, {point_3005.wkt})"""
    region = databc_feature_search(
        'WHSE_ADMIN_BOUNDARIES.ADM_NR_REGIONS_SPG', cql_filter=cql_filter)

    # a point in BC should match with a region.
    # We also expect any given point to be within at most 1 region.
    if len(region['features']) != 1:
        return None

    region_code = region['features'][0]['properties'].get('ORG_UNIT', None)

    if not region_code:
        return None

    # if reports need to be added or updated, a database table might be required.
    # for now, we only have to keep track of these 7 report links.
    report_map = {
        "RNO":
            ("https://a100.gov.bc.ca/pub/acat/public/viewReport.do?reportId=48460",
             "Inventory of Streamflow in the Omineca and Northeast Regions"),
        "ROM":
            ("https://a100.gov.bc.ca/pub/acat/public/viewReport.do?reportId=48460",
             "Inventory of Streamflow in the Omineca and Northeast Regions"),
        "RSC":
            ("https://a100.gov.bc.ca/pub/acat/public/viewReport.do?reportId=53344",
             "Inventory of Streamflow in the South Coast and West Coast Regions"),
        "RWC":
            ("https://a100.gov.bc.ca/pub/acat/public/viewReport.do?reportId=53344",
             "Inventory of Streamflow in the South Coast and West Coast Regions"),
        "RCB":
            ("https://a100.gov.bc.ca/pub/acat/public/viewReport.do?reportId=52707",
             "Inventory of Streamflow in the Cariboo Region"),
        "RTO":
            ("https://a100.gov.bc.ca/pub/acat/public/viewReport.do?reportId=58628",
             "Inventory of Streamflow in the Thompson Okanagan Region"),
        "RSK":
            ("https://a100.gov.bc.ca/pub/acat/public/viewReport.do?reportId=40801",
             "Inventory of Streamflow in the Skeena Region"),
    }

    return report_map.get(region_code, None)


def parse_fish_life_stages(stages):
    """ cleans up life stage strings such as 'egg,juvenile'"""

    split_list = [item.split(',') for item in stages]
    flat_list = [item for sublist in split_list for item in sublist]

    return list(set(flat_list))


def get_scsb2016_input_stats(db: Session):
    q = """
    select * from modeling.scsb2016_model_input_stats;
    """
    result = db.execute(q)
    stats = [dict(row) for row in result]
    return stats


def get_watershed_details(db: Session, watershed: Feature, use_sea: bool = True):
    """ returns watershed inputs variables used in modelling """

    if WATERSHED_DEBUG:
        logger.info("getting watershed details")

    watershed_poly = shape(watershed.geometry)
    watershed_area = transform(transform_4326_3005, watershed_poly).area

    if WATERSHED_DEBUG:
        logger.info("watershed area %s", watershed_area)

    # watershed characteristics lookups
    drainage_area = watershed_area / 1e6  # needs to be in km²
    glacial_area_m, glacial_coverage = calculate_glacial_area(
        db, watershed_poly)

    if WATERSHED_DEBUG:
        logger.info("glacial coverage %s", glacial_coverage)

    # climate raster pixels (precip, evapotranspiration...) are 1 square km.
    # if our watershed is on the small size, we might not get a pixel if
    # we try to clip the raster to our watershed.  If that is the case,
    # we'll want to sample the pixel at the centroid of the watershed.
    # only enable this feature for very small watersheds.
    retry_min_size = None
    if watershed_area < 20e6:
        retry_min_size = max(2e6, watershed_area)

    # precipitation values from prism raster
    annual_precipitation = get_mean_annual_precipitation(watershed_poly, retry_min_size=retry_min_size)

    if WATERSHED_DEBUG:
        logger.info("annual precipitation %s", annual_precipitation)

    # temperature and potential evapotranspiration values

    potential_evapotranspiration = get_potential_evapotranspiration(
        watershed_poly, retry_min_size=retry_min_size)

    if WATERSHED_DEBUG:
        logger.info("potential evapotranspiration %s", potential_evapotranspiration)

    # hydro zone dictates which model values to use
    hydrological_zone = get_hydrological_zone(watershed_poly.centroid)

    area_cdem = CDEM(watershed_poly)

    elev_stats = area_cdem.get_raster_summary_stats()
    median_elev = area_cdem.get_median_elevation()
    slope_percent = area_cdem.get_average_slope()

    aspect = None

    # todo: retry at min size
    solar_exposure = area_cdem.get_mean_hillshade(retry_min_size=retry_min_size)

    if WATERSHED_DEBUG:
        logger.info("elevation stats %s", elev_stats)
        logger.info("median elevation %s", median_elev)
        logger.info("average slope %s", slope_percent)
        logger.info("solar exposure %s", solar_exposure)

    data = {
        "watershed_id": watershed.id,
        "watershed_area": watershed_area,
        "drainage_area": drainage_area,
        "glacial_area": glacial_area_m,
        "glacial_coverage": glacial_coverage,
        "annual_precipitation": annual_precipitation,
        "potential_evapotranspiration": potential_evapotranspiration,
        "hydrological_zone": hydrological_zone,
        "average_slope": slope_percent,
        "solar_exposure": solar_exposure,
        "median_elevation": median_elev,
        "elevation_stats": elev_stats,
        "aspect": aspect
    }

    return data
