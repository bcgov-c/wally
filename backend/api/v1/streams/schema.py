"""
API data models for FreshWater Stream Atlas analysis.
These are external facing data models/schemas that users see.
"""
from pydantic import BaseModel
from typing import List, Any, Optional
from geojson import Feature


class Stream(BaseModel):
    # search_point

    ogc_fid: int
    geojson: Feature
    length_metre: Any
    feature_source: Any
    gnis_name: Any
    left_right_tributary: Any
    geometry_length: Any
    # geometry: str
    watershed_group_code: str
    fwa_watershed_code: str
    distance_degrees: float
    distance: float

    closest_stream_point: Any
    inverse_distance: float
    apportionment: float


class Streams(BaseModel):
    weighting_factor: int

    streams: List[Stream]