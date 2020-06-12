import json
import geojson
from typing import List
from logging import getLogger
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import func
from shapely.geometry import Point, LineString, mapping

from api.db.utils import get_db
from api.v1.wells.schema import WellDrawdown, CrossSection
from api.v1.aggregator.excel import geojson_to_xlsx
from api.v1.elevations.controllers.profile import get_profile_line_by_length
from api.v1.elevations.controllers.surface import fetch_surface_lines
from api.v1.wells.controller import (
    get_wells_by_distance,
    get_waterbodies_along_line,
    merge_wells_datasources,
    create_line_buffer,
    get_screens,
    get_wells_along_line,
    get_line_buffer_polygon,
    get_parallel_line_offset
)

logger = getLogger("wells")

router = APIRouter()


@router.get("/nearby", response_model=List[WellDrawdown])
def get_nearby_wells(
        db: Session = Depends(get_db),
        point: str = Query(..., title="Point of interest",
                           description="Point of interest to centre search at"),
        radius: float = Query(1000, title="Search radius",
                              description="Search radius from point", ge=0, le=10000),
        format: str = Query('json', title="Format",
                            description="Format that results will be returned in (json, xlsx)")
):
    """ finds wells near to a point
        fetches distance data using the Wally database, and combines
        it with screen data from GWELLS
    """
    """ search for licences near a point """
    point_parsed = json.loads(point)
    point_shape = Point(point_parsed)

    # wells_with_distances = get_wells_by_distance(db, point_shape, radius)

    # # convert nearby wells to a list of strings of well tag numbers
    # wells_to_search = map(lambda x: str(
    #     int(x[0])).lstrip("0"), wells_with_distances)

    wells_drawdown_data = get_screens(point_shape, radius)

    if format == 'xlsx':
        return geojson_to_xlsx(
            [geojson.FeatureCollection(
                [
                    geojson.Feature(
                        geometry=geojson.Point([x.longitude, x.latitude]),
                        properties=x.dict(exclude={'screen_set'})
                    ) for x in wells_drawdown_data
                ],
                properties={
                    "name": "Available drawdown"
                }
            )]
        )

    return wells_drawdown_data


@router.get("/section", response_model=CrossSection)
def get_wells_section(
        db: Session = Depends(get_db),
        line: str = Query(..., title="Section line",
                          description="Section line along which wells will be plotted"),
        radius: float = Query(200, title="Search radius",
                              description="Search radius (or offset) from line", ge=0, le=10000)
):
    """ search for wells along a line, returning a cross section of well data """

    line_parsed = json.loads(line)
    line_shape = LineString(line_parsed)

    left = get_parallel_line_offset(db, line_shape, -radius)
    left_half = get_parallel_line_offset(db, line_shape, -radius/2)
    right = get_parallel_line_offset(db, line_shape, radius)
    right_half = get_parallel_line_offset(db, line_shape, radius/2)
    lines = [left[0], left_half[0], line_shape.wkt, right_half[0], right[0]]
    # surface of 5 lines used for 3d display
    surface = fetch_surface_lines(lines)

    profile_line_linestring = surface[2]
    profile_line = get_profile_line_by_length(db, profile_line_linestring)
    wells_along_line = get_wells_along_line(
        db, profile_line_linestring, radius)

    buffer = create_line_buffer(profile_line_linestring, radius)

    surface_lines = [list(line.coords) for line in surface]
    # we need to reverse the point lists for the -radius results
    surface_lines[0].reverse()
    surface_lines[1].reverse()

    # waterbodies that cross profile
    waterbodies_along_line = get_waterbodies_along_line(
        line_shape, profile_line_linestring)

    # logger.info(surface_lines)
    section = CrossSection(search_area=mapping(buffer), wells=wells_along_line,
                           waterbodies=waterbodies_along_line,
                           elevation_profile=profile_line, surface=surface_lines)

    return section
