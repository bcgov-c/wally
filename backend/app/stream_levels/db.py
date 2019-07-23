"""
Database tables and data access functions for Water Survey of Canada's
National Water Data Archive Hydrometic Data
"""
from typing import List
from geojson import FeatureCollection, Feature, Point
from sqlalchemy import Column, Integer, ForeignKey, String
from sqlalchemy.orm import Session, relationship
from sqlalchemy.dialects.postgresql import DOUBLE_PRECISION

from app.db.base_class import BaseTable

import app.stream_levels.models as streams_v1


class MonthlyLevel(BaseTable):
    """
    Water level at a stream flow monitoring station, grouped by month.
    Note: daily data is also available on this table.
    """
    __tablename__ = "dly_levels"

    station_number = Column(String, ForeignKey(
        'stations.station_number'), primary_key=True)
    year = Column(Integer, primary_key=True)
    month = Column(Integer, primary_key=True)
    full_month = Column(Integer)
    no_days = Column(Integer)
    precision_code = Column(Integer)
    monthly_mean = Column(DOUBLE_PRECISION)
    monthly_total = Column(DOUBLE_PRECISION)
    min = Column(DOUBLE_PRECISION)
    max = Column(DOUBLE_PRECISION)
    station = relationship("StreamStation", back_populates="monthly_levels")


class MonthlyFlow(BaseTable):
    """
    Water flows at a stream flow monitoring station, grouped by month.
    Note: daily data is also available on this table.
    """
    __tablename__ = "dly_flows"

    station_number = Column(String, ForeignKey(
        'stations.station_number'), primary_key=True)
    year = Column(Integer, primary_key=True)
    month = Column(Integer, primary_key=True)
    full_month = Column(Integer)
    no_days = Column(Integer)
    monthly_mean = Column(DOUBLE_PRECISION)
    monthly_total = Column(DOUBLE_PRECISION)
    min = Column(DOUBLE_PRECISION)
    max = Column(DOUBLE_PRECISION)
    station = relationship("StreamStation", back_populates="monthly_flows")


class StreamStation(BaseTable):
    """ 
    A station where stream data is collected
    Data and schema from National Water Data Archive
    https://www.canada.ca/en/environment-climate-change/services/water-overview/ \
        quantity/monitoring/survey/data-products-services/national-archive-hydat.html

    """
    __tablename__ = "stations"

    station_number = Column(String, primary_key=True)
    station_name = Column(String)
    prov_terr_state_loc = Column(String)
    regional_office_id = Column(String)
    hyd_status = Column(String)
    sed_status = Column(String)
    latitude = Column(DOUBLE_PRECISION)
    longitude = Column(DOUBLE_PRECISION)
    drainage_area_gross = Column(DOUBLE_PRECISION)
    drainage_area_effect = Column(DOUBLE_PRECISION)
    rhbn = Column(Integer)
    real_time = Column(Integer)
    sed_status = Column(Integer)
    monthly_flows = relationship("MonthlyFlow", back_populates="station")
    monthly_levels = relationship("MonthlyLevel", back_populates="station")


def get_stations(db: Session):
    """ list all stream monitoring stations in BC as a FeatureCollection """
    return db.query(StreamStation).filter(
        StreamStation.prov_terr_state_loc == 'BC').all()


def get_monthly_levels_by_station(db: Session, station: str, year: int) -> List[streams_v1.MonthlyLevel]:
    """ fetch monthly stream levels for a specified station_number and year """
    return db.query(MonthlyLevel).filter(
        MonthlyLevel.station_number == station,
        MonthlyLevel.year == year
    ).all()


def get_monthly_flows_by_station(db: Session, station: str, year: int) -> List[streams_v1.MonthlyFlow]:
    """ fetch monthly stream levels for a specified station_number and year """
    return db.query(MonthlyFlow).filter(
        MonthlyFlow.station_number == station,
        MonthlyFlow.year == year
    ).all()


def get_station_details(db: Session, station: str) -> streams_v1.StreamStation:
    """
    fetch details for a given stream monitoring station, including a list of years
    for which relevant data is available.
    """

    return db.query(StreamStation).get(station)


def get_available_flow_years(db: Session, station: str):
    """ fetch a list of years for which stream flow data is available """
    return db.query(MonthlyFlow).filter(
        MonthlyFlow.station_number == station).distinct("year")


def get_available_level_years(db: Session, station: str):
    """ fetch a list of years for which stream level data is available """
    return db.query(MonthlyLevel).filter(
        MonthlyLevel.station_number == station).distinct("year")
