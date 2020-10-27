"""
Endpoints for returning statistics about watersheds
"""
from logging import getLogger
import datetime
import json
import geojson
from geojson import FeatureCollection, Feature
from fastapi import APIRouter, Depends, HTTPException, Query, Path
from fastapi.encoders import jsonable_encoder
from sqlalchemy import func
from sqlalchemy.orm import Session

from shapely.geometry import shape, MultiPolygon, Polygon, Point
from shapely.ops import transform


from api.db.utils import get_db
from api.v1.hydat.db_models import Station as StreamStation

from api.v1.aggregator.controller import (
    databc_feature_search,

    EXTERNAL_API_REQUESTS,
    API_DATASOURCES,
    DATABC_GEOMETRY_FIELD,
    DATABC_LAYER_IDS)
from api.v1.aggregator.schema import WMSGetMapQuery, WMSGetFeatureQuery, ExternalAPIRequest, LayerResponse
from api.v1.aggregator.helpers import transform_4326_3005, transform_3005_4326
from api.v1.aggregator.excel import xlsx_export
from api.v1.watersheds.controller import (
    get_watershed_details,
    surface_water_rights_licences,
    surface_water_approval_points,
    calculate_watershed,
    get_watershed,
    surficial_geology,
    export_summary_as_xlsx,
    known_fish_observations,
    find_50k_watershed_codes,
    get_stream_inventory_report_link_for_region,
    get_scsb2016_input_stats
)
from api.v1.hydat.controller import (get_stations_in_area)
from api.v1.watersheds.schema import (
    WatershedDetails,
    LicenceDetails,
    SurficialGeologyDetails,
    SurficialGeologyTypeSummary
)
from api.v1.models.isolines.controller import calculate_runoff_in_area
from api.v1.models.scsb2016.controller import get_hydrological_zone, calculate_mean_annual_runoff, model_output_as_dict
from api.v1.models.hydrological_zones.controller import get_hydrological_zone_model

logger = getLogger("aggregator")

router = APIRouter()

watershed_feature_description = """
    Watershed features follow the format <dataset>.<id>. Dataset is either
    the DataBC dataset code or 'calculated' for Wally generated watersheds.
    If using a calculated watershed, `id` is the FWA Watershed feature ID
    to start calculating a watershed from.
    Example:
    'WHSE_WATER_MANAGEMENT.HYDZ_HYD_WATERSHED_BND_POLY.1111111'
    'calculated.1111111'.
    """


@router.get('/streamflow_inventory')
def get_streamflow_inventory_report_link(
    db: Session = Depends(get_db),
    point: str = Query(
        "", title="Search point",
        description="Point to search within")):
    """ returns a link to the streamflow inventory report for this watershed"""
    if not point:
        raise HTTPException(
            status_code=400, detail="No search point. Supply a `point` in [long, lat] format")

    point_parsed = json.loads(point)
    point = Point(point_parsed)

    report_link, report_name = get_stream_inventory_report_link_for_region(
        point)

    return {
        "report_link": report_link,
        "report_name": report_name,
        "hydrologic_zone": get_hydrological_zone(point)
    }


@router.get('/')
def get_watersheds(
    db: Session = Depends(get_db),
    point: str = Query(
        "", title="Search point",
        description="Point to search within"),
    include_self: bool = Query(
        False, title="Include the area around the point of interest in generated polygons")
):
    """ returns a list of watersheds at this point, if any.
    Watersheds are sourced from the following datasets:
    https://catalogue.data.gov.bc.ca/dataset/freshwater-atlas-assessment-watersheds
    https://catalogue.data.gov.bc.ca/dataset/hydrology-hydrometric-watershed-boundaries
    https://catalogue.data.gov.bc.ca/dataset/freshwater-atlas-watersheds

    """
    assessment_watershed_layer_id = 'WHSE_BASEMAPPING.FWA_ASSESSMENT_WATERSHEDS_POLY'
    fwa_watersheds_layer_id = 'WHSE_BASEMAPPING.FWA_WATERSHEDS_POLY'
    hydrometric_watershed_layer_id = 'WHSE_WATER_MANAGEMENT.HYDZ_HYD_WATERSHED_BND_POLY'

    search_layers = ','.join([
        assessment_watershed_layer_id,
        fwa_watersheds_layer_id,
        hydrometric_watershed_layer_id
    ])

    if not point:
        raise HTTPException(
            status_code=400, detail="No search point. Supply a `point` (geojson geometry)")

    if point:
        point_parsed = json.loads(point)
        point = Point(point_parsed)

    watersheds = databc_feature_search(search_layers, search_area=point)

    watershed_features = []

    calculated_ws = calculate_watershed(db, point, include_self=include_self)

    if calculated_ws:
        watershed_features.append(calculated_ws)

    for ws in watersheds.features:
        watershed_features.append(
            Feature(
                geometry=transform(transform_3005_4326, shape(ws.geometry)),
                properties=dict(ws.properties),
                id=ws.id
            )
        )

    return FeatureCollection(watershed_features)


@router.get('/{watershed_feature}')
def watershed_stats(
    db: Session = Depends(get_db),
    watershed_feature: str = Path(...,
                                  title="The watershed feature ID at the point of interest",
                                  description=watershed_feature_description),
    format: str = Query(
        "json",
        title="Format",
        description="Format to return results in. Options: json (default), xlsx"
    )
):
    """ aggregates statistics/info about a watershed """
    logger.warn("Watershed Details - Request Started")

    # watershed area calculations
    watershed = get_watershed(db, watershed_feature)
    watershed_poly = shape(watershed.geometry)

    watershed_details = get_watershed_details(db, watershed)
    wd = watershed_details # purely for shorthand below

    # isoline model outputs
    isoline_runoff_model = calculate_runoff_in_area(db, watershed_poly)

    # custom linear mad model outputs
    scsb2016_model = calculate_mean_annual_runoff(db, wd["hydrological_zone"], wd["median_elevation"],
                                                  wd["glacial_coverage"], wd["annual_precipitation"], wd["potential_evapotranspiration_thornthwaite"],
                                                  wd["drainage_area"], wd["solar_exposure"], wd["average_slope"])

    scsb2016_input_stats = get_scsb2016_input_stats(db)

    try:
        wally_hydrological_zone_model = get_hydrological_zone_model(
            wd["hydrological_zone"], wd["drainage_area"], wd["median_elevation"], wd["annual_precipitation"])
    except:
        wally_hydrological_zone_model = None

    # hydro stations from federal source
    hydrometric_stations = get_stations_in_area(db, shape(watershed.geometry))

    data = {
        "watershed_name": watershed.properties.get("name", None),
        "watershed_source": watershed.properties.get("watershed_source", None),
        **watershed_details,
        "runoff_isoline_avg": (isoline_runoff_model['runoff'] /
                               isoline_runoff_model['area'] * 1000) if isoline_runoff_model['area'] else 0,
        "runoff_isoline_discharge_m3s": isoline_runoff_model['runoff'] / 365 / 24 / 60 / 60,
        "scsb2016_model": scsb2016_model,
        "scsb2016_output": model_output_as_dict(scsb2016_model),
        "wally_hydro_zone_model_output": wally_hydrological_zone_model,
        "scsb2016_input_stats": scsb2016_input_stats,
        "hydrometric_stations": hydrometric_stations,
    }

    if format == 'xlsx':
        licence_data = surface_water_rights_licences(watershed_poly)
        # TODO add approvals data to xlsx output
        # approvals_data = surface_water_approval_points(watershed_poly)
        data['generated_date'] = datetime.datetime.now().strftime(
            "%Y-%m-%d %H:%M:%S")

        if licence_data.licences and licence_data.licences.features:
            data['licences'] = [dict(**x.properties)
                                for x in licence_data.licences.features]
            data['inactive_licences'] = [dict(**x.properties)
                                         for x in licence_data.inactive_licences.features]
            data['licences_count_pod'] = len(licence_data.licences.features)

        return export_summary_as_xlsx(jsonable_encoder(data))

    logger.warn("Watershed Details - Request Finished")

    return data


@router.get('/details/')
def get_generated_watershed_details(
    db: Session = Depends(get_db),
    point: str = Query(
        "", title="Search point",
        description="Point to search within"),
    use_sea: bool = True
):
    """ returns generated watershed characteristics, used as source for modelling data """

    if not point:
        raise HTTPException(
            status_code=400, detail="No search point. Supply a `point` (geojson geometry)")

    if point:
        point_parsed = json.loads(point)
        point = Point(point_parsed)

    watershed = calculate_watershed(db, point, include_self=True)

    if not watershed:
        raise HTTPException(
            status_code=500, detail="Could not generate watershed.")

    watershed_details = get_watershed_details(db, watershed, use_sea)

    return watershed_details


@router.get('/{watershed_feature}/fwa_50k_codes')
def get_50k_watershed_codes(
    db: Session = Depends(get_db),
    watershed_feature: str = Path(...,
                                  title="The watershed feature ID at the point of interest",
                                  description=watershed_feature_description)
):
    """ returns 50k (old) watershed codes. Useful for searching legacy applications """

    watershed = get_watershed(db, watershed_feature)

    return find_50k_watershed_codes(db, shape(watershed.geometry))


@router.get('/{watershed_feature}/licences')
def get_watershed_demand(
    db: Session = Depends(get_db),
    watershed_feature: str = Path(...,
                                  title="The watershed feature ID at the point of interest",
                                  description=watershed_feature_description)
):
    """ returns data about watershed demand by querying DataBC """

    watershed = get_watershed(db, watershed_feature)

    return surface_water_rights_licences(shape(watershed.geometry))


@router.get('/{watershed_feature}/approvals')
def get_watershed_short_term_demand(
    db: Session = Depends(get_db),
    watershed_feature: str = Path(...,
                                  title="The watershed feature ID at the point of interest",
                                  description=watershed_feature_description)
):
    """ returns data about watershed demand by querying DataBC """

    watershed = get_watershed(db, watershed_feature)

    return surface_water_approval_points(shape(watershed.geometry))


@router.get('/{watershed_feature}/surficial_geology')
def get_surficial_geology(
    db: Session = Depends(get_db),
    watershed_feature: str = Path(...,
                                  title="The watershed feature ID at the point of interest",
                                  description=watershed_feature_description)
):
    """ returns data about watershed demand by querying DataBC """

    watershed = get_watershed(db, watershed_feature)

    surf_geol_summary = surficial_geology(shape(watershed.geometry))

    return surf_geol_summary


@router.get('/{watershed_feature}/fish_observations')
def get_fish_observations(
    db: Session = Depends(get_db),
    watershed_feature: str = Path(...,
                                  title="The watershed feature ID at the point of interest",
                                  description=watershed_feature_description)
):
    """ returns data about fish observations within a watershed by querying DataBC """

    watershed = get_watershed(db, watershed_feature)

    watershed_fish_observations = known_fish_observations(
        shape(watershed.geometry))

    return watershed_fish_observations
