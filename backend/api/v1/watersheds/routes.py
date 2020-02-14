"""
Aggregate data from different WMS and/or API sources.
"""
from logging import getLogger
import json
import geojson
from geojson import FeatureCollection, Feature
from fastapi import APIRouter, Depends, HTTPException, Query, Path
from sqlalchemy import func
from sqlalchemy.orm import Session
from shapely.geometry import shape, MultiPolygon, Polygon, Point
from shapely.ops import transform


from api.db.utils import get_db
from api.v1.hydat.db_models import Station as StreamStation
from api.layers.freshwater_atlas_watersheds import FreshwaterAtlasWatersheds

from api.v1.aggregator.controller import (
    databc_feature_search,

    EXTERNAL_API_REQUESTS,
    API_DATASOURCES,
    DATABC_GEOMETRY_FIELD,
    DATABC_LAYER_IDS)
from api.v1.aggregator.schema import WMSGetMapQuery, WMSGetFeatureQuery, ExternalAPIRequest, LayerResponse
from api.v1.aggregator.helpers import transform_4326_3005, transform_3005_4326
from api.v1.aggregator.excel import xlsxExport
from api.v1.watersheds.controller import (
    calculate_glacial_area,
    pcic_data_request,
    surface_water_rights_licences,
    get_watershed,
    get_upstream_catchment_area,
    surficial_geology,
    get_temperature,
    calculate_potential_evapotranspiration_thornthwaite,
    calculate_potential_evapotranspiration_hamon
)
from api.v1.watersheds.schema import (
    WatershedDetails,
    LicenceDetails,
    SurficialGeologyDetails,
    SurficialGeologyTypeSummary
)
from api.v1.isolines.controller import calculate_runoff_in_area


logger = getLogger("aggregator")

router = APIRouter()


@router.get('/')
def get_watersheds(
    db: Session = Depends(get_db),
    point: str = Query(
        "", title="Search point",
        description="Point to search within")
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

    if not len(watersheds.features):
        return FeatureCollection([])

    watershed_features = [
        Feature(
            geometry=transform(transform_3005_4326, shape(ws.geometry)),
            properties=dict(ws.properties),
            id=ws.id
        ) for i, ws in enumerate(watersheds.features)]

    for feature in watershed_features:
        isoline_runoff = calculate_runoff_in_area(db, shape(feature.geometry))
        feature.properties["ISOLINE_ANNUAL_RUNOFF"] = isoline_runoff["runoff"]
        feature.properties["ISOLINE_AREA"] = isoline_runoff["area"]
        # feature.properties["HYDROLOGICZONE_NO"] = hydrologic_zone

    return FeatureCollection(watershed_features)


@router.get('/calc')
def calculate_watershed(
    db: Session = Depends(get_db),
    point: str = Query(
        "", title="Search point",
        description="Point to search within"),
    include_self: bool = Query(
        False, title="Include polygon at POI",
        description="Indicates whether or not to include the polygon containing the point of interest in the estimation."
    )
):
    """ calculates watershed area upstream of a POI """
    if not point:
        raise HTTPException(
            status_code=400, detail="No search point. Supply a `point` (geojson geometry)")

    if point:
        point_parsed = json.loads(point)
        point = Point(point_parsed)

    logger.info('---------------------------------------------------')
    logger.info(point.wkt)
    logger.info('---------------------------------------------------')

    q = db.query(FreshwaterAtlasWatersheds.WATERSHED_FEATURE_ID).filter(
        func.ST_Contains(
            FreshwaterAtlasWatersheds.GEOMETRY,
            func.ST_GeomFromText(point.wkt, 4326)
        )
    )

    logger.info(q)

    watershed_id = q.first()

    feature = get_upstream_catchment_area(
        db, watershed_id, include_self=include_self)

    geom = shape(feature.geometry)

    feature.properties['area'] = transform(
        transform_4326_3005, geom).area

    isoline_runoff = calculate_runoff_in_area(db, geom)

    feature.properties['runoff_isoline_avg'] = (isoline_runoff['runoff'] /
                                                isoline_runoff['area'] * 1000) if isoline_runoff['area'] else 0

    return FeatureCollection([feature])


@router.get('/{watershed_feature_id}')
def watershed_stats(
    db: Session = Depends(get_db),
    watershed_feature_id: int = Path(...,
                                     title="The watershed feature ID at the point of interest")


):
    """ aggregates statistics/info about a watershed """

    watershed = get_upstream_catchment_area(db, watershed_feature_id)

    watershed_poly = shape(watershed.geometry)
    watershed_area = transform(transform_4326_3005, watershed_poly).area

    watershed_rect = watershed_poly.minimum_rotated_rectangle

    glacial_area_m, glacial_coverage = calculate_glacial_area(
        db, watershed_rect)

    isoline_runoff = calculate_runoff_in_area(db, watershed_poly)

    temp_data = get_temperature(watershed_poly)

    potential_evapotranspiration_hamon = calculate_potential_evapotranspiration_hamon(
        watershed_poly, temp_data)

    potential_evapotranspiration_thornthwaite = calculate_potential_evapotranspiration_thornthwaite(
        watershed_poly, temp_data
    )

    return WatershedDetails(
        glacial_coverage=glacial_coverage,
        glacial_area=glacial_area_m,
        watershed_area=watershed_area,
        potential_evapotranspiration_hamon=potential_evapotranspiration_hamon,
        potential_evapotranspiration_thornthwaite=potential_evapotranspiration_thornthwaite,
        runoff_isoline_avg=(isoline_runoff['runoff'] /
                            isoline_runoff['area'] * 1000) if isoline_runoff['area'] else 0
    )


@router.get('/{watershed_feature_id}/licences')
def get_watershed_demand(
    db: Session = Depends(get_db),
    watershed_feature_id: int = Path(...,
                                     title="The watershed feature ID at the point of interest")


):
    """ returns data about watershed demand by querying DataBC """

    watershed = get_upstream_catchment_area(db, watershed_feature_id)

    return surface_water_rights_licences(shape(watershed.geometry))


@router.get('/{watershed_feature_id}/surficial_geology')
def get_surficial_geology(
    db: Session = Depends(get_db),
    watershed_feature_id: int = Path(...,
                                     title="The watershed feature ID at the point of interest")
):
    """ returns data about watershed demand by querying DataBC """

    watershed = get_upstream_catchment_area(db, watershed_feature_id)

    watershed_poly = shape(watershed.geometry)

    surf_geol_summary = surficial_geology(watershed_poly)

    return surf_geol_summary
