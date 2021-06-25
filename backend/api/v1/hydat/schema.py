"""
API data models.
These are external facing data models/schemas that users see.
"""
from typing import Optional, List
from pydantic import BaseModel, Schema
from shapely.geometry import Point


class StreamStation(BaseModel):
    """
    Information about a monitoring station where stream flow data is collected.
    """
    station_number: str
    station_name: str
    prov_terr_state_loc: str
    regional_office_id: str
    hyd_status: Optional[str]
    sed_status: Optional[str]
    latitude: Optional[float]
    longitude: Optional[float]
    drainage_area_gross: Optional[float]
    drainage_area_effect: Optional[float]
    geom: Point

    class Config:
        orm_mode = True
        arbitrary_types_allowed = True


class StreamStationResponse(BaseModel):
    """
    Information about a monitoring station where stream flow data is collected.
    """
    name: str
    url: str
    station_number: str
    station_name: str
    prov_terr_state_loc: str
    regional_office_id: str
    hyd_status: Optional[str]
    sed_status: Optional[str]
    latitude: Optional[float]
    longitude: Optional[float]
    drainage_area_gross: Optional[float]
    drainage_area_effect: Optional[float]
    rhbn: int
    real_time: int
    flow_years: List[int] = Schema(
        [], description="Years for which flow data is available")
    level_years: List[int] = Schema(
        [], description="Years for which stream level data is available")
    stream_flows_url: Optional[str] = Schema(
        None, description="URL where stream flow data is accessible")
    stream_levels_url: Optional[str] = Schema(
        None, description="URL where stream level data is accessible")
    external_urls: List[dict] = Schema(
        [], description="External links (e.g. links out to the original source of data")

    class Config:
        orm_mode = True


class MonthlyLevel(BaseModel):
    """
    Water level at a stream flow monitoring station, grouped by month
    """

    station_number: Optional[str]
    year: Optional[int]
    month: int
    full_month: Optional[int]
    no_days: Optional[int]
    precision_code: Optional[int]
    monthly_mean: Optional[float]
    monthly_total: Optional[float]
    min: Optional[float]
    max: Optional[float]

    class Config:
        orm_mode = True


class MonthlyFlow(BaseModel):
    """
    Flow at a stream flow monitoring station, grouped by month
    """

    station_number: Optional[str]
    year: Optional[int]
    month: int
    full_month: Optional[int]
    no_days: Optional[int]
    monthly_mean: Optional[float]
    monthly_total: Optional[float]
    min: Optional[float]
    max: Optional[float]

    class Config:
        orm_mode = True


class NearbyStream(BaseModel):
    """a stream segment near a HYDAT station.

    stream_point is the point on each segment nearest
    to the station.
    """
    stream_point: Point
    stream_feature_id: int

    class Config:
        arbitrary_types_allowed = True
