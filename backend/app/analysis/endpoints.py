"""
Analysis functions for data in the Wally system
"""
import json
from typing import List
from logging import getLogger
from fastapi import APIRouter, Depends, HTTPException, Query, Path
from sqlalchemy.orm import Session
from shapely.geometry import Point, shape
from app.db.utils import get_db
from app.analysis.wells.well_analysis import get_wells_by_distance, merge_wells_datasources, get_screens
from app.analysis.licences.licence_analysis import get_licences_by_distance
from app.analysis.licences.licence_analysis import get_licences_within_buffer
from app.analysis.wells.models import WellDrawdown
from app.analysis.licences.models import WaterRightsLicence
from app.analysis.first_nations.nearby_areas import get_nearest_locations
from app.analysis.first_nations.models import NearbyAreasResponse
logger = getLogger("geocoder")

router = APIRouter()


@router.get("/analysis/wells/nearby", response_model=List[WellDrawdown])
def get_nearby_wells(
    db: Session = Depends(get_db),
    point: str = Query(..., title="Point of interest",
                       description="Point of interest to centre search at"),
    radius: float = Query(1000, title="Search radius",
                          description="Search radius from point", ge=0, le=10000)
):
    """ finds wells near to a point
        fetches distance data using the Wally database, and combines
        it with screen data from GWELLS
    """

    point_parsed = json.loads(point)
    point_shape = Point(point_parsed)

    wells_with_distances = get_wells_by_distance(db, point_shape, radius)

    # convert nearby wells to a list of strings of well tag numbers
    wells_to_search = map(lambda x: str(
        int(x[0])).lstrip("0"), wells_with_distances)

    wells_with_screens = get_screens(list(wells_to_search))

    wells_drawdown_data = merge_wells_datasources(
        wells_with_screens, wells_with_distances)

    return wells_drawdown_data


@router.get("/analysis/licences/nearby", response_model=List[WaterRightsLicence])
def get_nearby_licences(
    db: Session = Depends(get_db),
    point: str = Query(..., title="Point of interest",
                       description="Point of interest to centre search at"),
    radius: float = Query(1000, title="Search radius",
                          description="Search radius from point", ge=0, le=10000)
):
    point_parsed = json.loads(point)
    point_shape = Point(point_parsed)

    licences_with_distances = get_licences_by_distance(db, point_shape, radius)
    return licences_with_distances


@router.get("/analysis/licences/buffer", response_model=List[WaterRightsLicence])
def get_licences_within_buffer_zone(
    db: Session = Depends(get_db),
    geometry: str = Query(..., title="Geometry to search within",
                       description="Complex Geometry to create buffer with and find points within."),
    buffer: float = Query(100, title="Buffer size in meters",
                          description="Buffer size to create around geometry", ge=0, le=100)
):
    geometry_parsed = json.loads(geometry)
    geometry_shape = shape(geometry_parsed)

    licences_within_buffer = get_licences_within_buffer(db, geometry_shape, buffer)
    return licences_within_buffer


@router.get("/analysis/firstnations/nearby", response_model=NearbyAreasResponse)
def get_nearby_first_nations_areas(
    db: Session = Depends(get_db),
    geometry: str = Query(...,
                          title="Geometry to search near",
                          description="Geometry (such as a point or polygon) to search within and near to")
):
    """
    Search for First Nations Communities, First Nations Treaty Areas and First Nations Treaty Lands near a feature
    """
    geometry_parsed = json.loads(geometry)
    geometry_shape = shape(geometry_parsed)
    nearest = get_nearest_locations(db, geometry_shape)
    return nearest
