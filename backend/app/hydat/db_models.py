"""
Database table models for Water Survey of Canada National Water Data Archive Hydrometic Data

https://www.canada.ca/en/environment-climate-change/services/water-overview/quantity/monitoring/survey/data-products-services/national-archive-hydat.html

These models were autogenerated using sqlacodegen (https://pypi.org/project/sqlacodegen/) using the schema
from the original database available at the link above.
Primary keys were manually added to the generated models.
Warning: the original database schema did not include any foreign key constraints.

"""
# coding: utf-8
from typing import List, Optional
from geojson import Feature, Point
from sqlalchemy import BigInteger, Column, DateTime, Float, Index, Text, text, ForeignKey, func
from sqlalchemy.orm import relationship, Session
from sqlalchemy.dialects.postgresql import DOUBLE_PRECISION
from geoalchemy2 import Geometry
from app.db.base_class import BaseLayerTable
import app.hydat.models as streams_v1
import app.aggregator.db as agr_repo
from shapely.geometry import Polygon
from logging import getLogger
logger = getLogger("Hydat")


class AgencyList(BaseLayerTable):
    __tablename__ = 'agency_list'
    __table_args__ = {'schema': 'hydat'}

    agency_id = Column(BigInteger, primary_key=True, server_default=text(
        "nextval('hydat.agency_list_agency_id_seq'::regclass)"))
    agency_en = Column(Text)
    agency_fr = Column(Text)


class AnnualInstantPeak(BaseLayerTable):
    __tablename__ = 'annual_instant_peaks'
    __table_args__ = (
        Index('idx_20802_annual_instant_peaks___uniqueindex',
              'station_number', 'data_type', 'year', 'peak_code', unique=True),
        {'schema': 'hydat'}
    )

    station_number = Column(Text, primary_key=True, nullable=False)
    data_type = Column(Text, primary_key=True, nullable=False)
    year = Column(BigInteger, primary_key=True, nullable=False)
    peak_code = Column(Text, primary_key=True, nullable=False)
    precision_code = Column(BigInteger, index=True)
    month = Column(BigInteger)
    day = Column(BigInteger)
    hour = Column(BigInteger)
    minute = Column(BigInteger)
    time_zone = Column(Text)
    peak = Column(DOUBLE_PRECISION)
    symbol = Column(Text)


class AnnualStatistic(BaseLayerTable):
    __tablename__ = 'annual_statistics'
    __table_args__ = (
        Index('idx_20940_annual_statistics_primarykey',
              'station_number', 'data_type', 'year', unique=True),
        {'schema': 'hydat'}
    )

    station_number = Column(Text, primary_key=True, nullable=False)
    data_type = Column(Text, primary_key=True, nullable=False)
    year = Column(BigInteger, primary_key=True, nullable=False)
    mean = Column(DOUBLE_PRECISION)
    min_month = Column(BigInteger)
    min_day = Column(BigInteger)
    min = Column(DOUBLE_PRECISION)
    min_symbol = Column(Text)
    max_month = Column(BigInteger)
    max_day = Column(BigInteger)
    max = Column(DOUBLE_PRECISION)
    max_symbol = Column(Text)


class ConcentrationSymbol(BaseLayerTable):
    __tablename__ = 'concentration_symbols'
    __table_args__ = {'schema': 'hydat'}

    concentration_symbol = Column(Text, primary_key=True)
    concentration_en = Column(Text)
    concentration_fr = Column(Text)


class DataSymbol(BaseLayerTable):
    __tablename__ = 'data_symbols'
    __table_args__ = {'schema': 'hydat'}

    symbol_id = Column(Text, primary_key=True)
    symbol_en = Column(Text)
    symbol_fr = Column(Text)


class DataType(BaseLayerTable):
    __tablename__ = 'data_types'
    __table_args__ = {'schema': 'hydat'}

    data_type = Column(Text, primary_key=True)
    data_type_en = Column(Text)
    data_type_fr = Column(Text)


class DatumList(BaseLayerTable):
    __tablename__ = 'datum_list'
    __table_args__ = {'schema': 'hydat'}

    datum_id = Column(BigInteger, primary_key=True, server_default=text(
        "nextval('hydat.datum_list_datum_id_seq'::regclass)"))
    datum_en = Column(Text)
    datum_fr = Column(Text)


class DailyFlow(BaseLayerTable):
    __tablename__ = 'dly_flows'
    __table_args__ = (
        Index('idx_20862_dly_flows_primarykey',
              'station_number', 'year', 'month', unique=True),
        {'schema': 'hydat'}
    )

    station_number = Column(Text, ForeignKey(
        'hydat.stations.station_number'), primary_key=True, nullable=False)
    year = Column(BigInteger, primary_key=True, nullable=False)
    month = Column(BigInteger, primary_key=True, nullable=False)
    full_month = Column(BigInteger)
    no_days = Column(BigInteger)
    monthly_mean = Column(DOUBLE_PRECISION)
    monthly_total = Column(DOUBLE_PRECISION)
    first_day_min = Column(BigInteger)
    min = Column(DOUBLE_PRECISION)
    first_day_max = Column(BigInteger)
    max = Column(DOUBLE_PRECISION)
    flow1 = Column(DOUBLE_PRECISION)
    flow_symbol1 = Column(Text)
    flow2 = Column(DOUBLE_PRECISION)
    flow_symbol2 = Column(Text)
    flow3 = Column(DOUBLE_PRECISION)
    flow_symbol3 = Column(Text)
    flow4 = Column(DOUBLE_PRECISION)
    flow_symbol4 = Column(Text)
    flow5 = Column(DOUBLE_PRECISION)
    flow_symbol5 = Column(Text)
    flow6 = Column(DOUBLE_PRECISION)
    flow_symbol6 = Column(Text)
    flow7 = Column(DOUBLE_PRECISION)
    flow_symbol7 = Column(Text)
    flow8 = Column(DOUBLE_PRECISION)
    flow_symbol8 = Column(Text)
    flow9 = Column(DOUBLE_PRECISION)
    flow_symbol9 = Column(Text)
    flow10 = Column(DOUBLE_PRECISION)
    flow_symbol10 = Column(Text)
    flow11 = Column(DOUBLE_PRECISION)
    flow_symbol11 = Column(Text)
    flow12 = Column(DOUBLE_PRECISION)
    flow_symbol12 = Column(Text)
    flow13 = Column(DOUBLE_PRECISION)
    flow_symbol13 = Column(Text)
    flow14 = Column(DOUBLE_PRECISION)
    flow_symbol14 = Column(Text)
    flow15 = Column(DOUBLE_PRECISION)
    flow_symbol15 = Column(Text)
    flow16 = Column(DOUBLE_PRECISION)
    flow_symbol16 = Column(Text)
    flow17 = Column(DOUBLE_PRECISION)
    flow_symbol17 = Column(Text)
    flow18 = Column(DOUBLE_PRECISION)
    flow_symbol18 = Column(Text)
    flow19 = Column(DOUBLE_PRECISION)
    flow_symbol19 = Column(Text)
    flow20 = Column(DOUBLE_PRECISION)
    flow_symbol20 = Column(Text)
    flow21 = Column(DOUBLE_PRECISION)
    flow_symbol21 = Column(Text)
    flow22 = Column(DOUBLE_PRECISION)
    flow_symbol22 = Column(Text)
    flow23 = Column(DOUBLE_PRECISION)
    flow_symbol23 = Column(Text)
    flow24 = Column(DOUBLE_PRECISION)
    flow_symbol24 = Column(Text)
    flow25 = Column(DOUBLE_PRECISION)
    flow_symbol25 = Column(Text)
    flow26 = Column(DOUBLE_PRECISION)
    flow_symbol26 = Column(Text)
    flow27 = Column(DOUBLE_PRECISION)
    flow_symbol27 = Column(Text)
    flow28 = Column(DOUBLE_PRECISION)
    flow_symbol28 = Column(Text)
    flow29 = Column(DOUBLE_PRECISION)
    flow_symbol29 = Column(Text)
    flow30 = Column(DOUBLE_PRECISION)
    flow_symbol30 = Column(Text)
    flow31 = Column(DOUBLE_PRECISION)
    flow_symbol31 = Column(Text)
    station = relationship("Station", back_populates="dly_flows")

    @classmethod
    def get_available_flow_years(cls, db: Session, station: str):
        """ fetch a list of years for which stream flow data is available """
        return db.query(cls).filter(
            cls.station_number == station).distinct("year")

    @classmethod
    def get_monthly_flows_by_station(cls, db: Session, station: str, year: int) -> List[streams_v1.MonthlyFlow]:
        """ fetch monthly stream levels for a specified station_number and year """
        if year:
            return db.query(cls).filter(
                cls.station_number == station,
                cls.year == year
            ).all()

        # year not specified, return average by month for all available years.
        return db.query(
            func.avg(cls.monthly_mean).label('monthly_mean'),
            func.min(cls.min).label('min'),
            func.max(cls.max).label('max'),
            cls.month) \
            .filter(cls.station_number == station, cls.full_month == 1) \
            .group_by(cls.month) \
            .order_by(cls.month).all()


class DailyLevel(BaseLayerTable):
    __tablename__ = 'dly_levels'
    __table_args__ = (
        Index('idx_20916_dly_levels_primarykey',
              'station_number', 'year', 'month', unique=True),
        {'schema': 'hydat'}
    )

    station_number = Column(Text, ForeignKey(
        'hydat.stations.station_number'), primary_key=True, nullable=False)
    year = Column(BigInteger, primary_key=True, nullable=False)
    month = Column(BigInteger, primary_key=True, nullable=False)
    precision_code = Column(BigInteger)
    full_month = Column(BigInteger)
    no_days = Column(BigInteger)
    monthly_mean = Column(DOUBLE_PRECISION)
    monthly_total = Column(DOUBLE_PRECISION)
    first_day_min = Column(BigInteger)
    min = Column(DOUBLE_PRECISION)
    first_day_max = Column(BigInteger)
    max = Column(DOUBLE_PRECISION)
    level1 = Column(DOUBLE_PRECISION)
    level_symbol1 = Column(Text)
    level2 = Column(DOUBLE_PRECISION)
    level_symbol2 = Column(Text)
    level3 = Column(DOUBLE_PRECISION)
    level_symbol3 = Column(Text)
    level4 = Column(DOUBLE_PRECISION)
    level_symbol4 = Column(Text)
    level5 = Column(DOUBLE_PRECISION)
    level_symbol5 = Column(Text)
    level6 = Column(DOUBLE_PRECISION)
    level_symbol6 = Column(Text)
    level7 = Column(DOUBLE_PRECISION)
    level_symbol7 = Column(Text)
    level8 = Column(DOUBLE_PRECISION)
    level_symbol8 = Column(Text)
    level9 = Column(DOUBLE_PRECISION)
    level_symbol9 = Column(Text)
    level10 = Column(DOUBLE_PRECISION)
    level_symbol10 = Column(Text)
    level11 = Column(DOUBLE_PRECISION)
    level_symbol11 = Column(Text)
    level12 = Column(DOUBLE_PRECISION)
    level_symbol12 = Column(Text)
    level13 = Column(DOUBLE_PRECISION)
    level_symbol13 = Column(Text)
    level14 = Column(DOUBLE_PRECISION)
    level_symbol14 = Column(Text)
    level15 = Column(DOUBLE_PRECISION)
    level_symbol15 = Column(Text)
    level16 = Column(DOUBLE_PRECISION)
    level_symbol16 = Column(Text)
    level17 = Column(DOUBLE_PRECISION)
    level_symbol17 = Column(Text)
    level18 = Column(DOUBLE_PRECISION)
    level_symbol18 = Column(Text)
    level19 = Column(DOUBLE_PRECISION)
    level_symbol19 = Column(Text)
    level20 = Column(DOUBLE_PRECISION)
    level_symbol20 = Column(Text)
    level21 = Column(DOUBLE_PRECISION)
    level_symbol21 = Column(Text)
    level22 = Column(DOUBLE_PRECISION)
    level_symbol22 = Column(Text)
    level23 = Column(DOUBLE_PRECISION)
    level_symbol23 = Column(Text)
    level24 = Column(DOUBLE_PRECISION)
    level_symbol24 = Column(Text)
    level25 = Column(DOUBLE_PRECISION)
    level_symbol25 = Column(Text)
    level26 = Column(DOUBLE_PRECISION)
    level_symbol26 = Column(Text)
    level27 = Column(DOUBLE_PRECISION)
    level_symbol27 = Column(Text)
    level28 = Column(DOUBLE_PRECISION)
    level_symbol28 = Column(Text)
    level29 = Column(DOUBLE_PRECISION)
    level_symbol29 = Column(Text)
    level30 = Column(DOUBLE_PRECISION)
    level_symbol30 = Column(Text)
    level31 = Column(DOUBLE_PRECISION)
    level_symbol31 = Column(Text)
    station = relationship("Station", back_populates="dly_levels")

    @classmethod
    def get_available_level_years(cls, db: Session, station: str):
        """ fetch a list of years for which stream level data is available """
        return db.query(cls).filter(
            cls.station_number == station).distinct("year")

    @classmethod
    def get_monthly_levels_by_station(cls, db: Session, station: str, year: int) -> List[streams_v1.MonthlyLevel]:
        """ fetch monthly stream levels for a specified station_number and year """
        if year:
            return db.query(cls).filter(
                cls.station_number == station,
                cls.year == year
            ).all()

        # year not specified, return an average by month for all years.
        return db.query(
            func.avg(cls.monthly_mean).label('monthly_mean'),
            func.min(cls.min).label('min'),
            func.max(cls.max).label('max'),
            cls.month
        ) \
            .filter(cls.station_number == station, cls.full_month == 1) \
            .group_by(cls.month) \
            .order_by(cls.month).all()


class MeasurementCode(BaseLayerTable):
    __tablename__ = 'measurement_codes'
    __table_args__ = {'schema': 'hydat'}

    measurement_code = Column(Text, primary_key=True)
    measurement_en = Column(Text)
    measurement_fr = Column(Text)


class OperationCode(BaseLayerTable):
    __tablename__ = 'operation_codes'
    __table_args__ = {'schema': 'hydat'}

    operation_code = Column(Text, primary_key=True)
    operation_en = Column(Text)
    operation_fr = Column(Text)


class PeakCode(BaseLayerTable):
    __tablename__ = 'peak_codes'
    __table_args__ = {'schema': 'hydat'}

    peak_code = Column(Text, primary_key=True)
    peak_en = Column(Text)
    peak_fr = Column(Text)


class PrecisionCode(BaseLayerTable):
    __tablename__ = 'precision_codes'
    __table_args__ = {'schema': 'hydat'}

    precision_code = Column(BigInteger, primary_key=True, server_default=text(
        "nextval('hydat.precision_codes_precision_code_seq'::regclass)"))
    precision_en = Column(Text)
    precision_fr = Column(Text)


class RegionalOfficeList(BaseLayerTable):
    __tablename__ = 'regional_office_list'
    __table_args__ = {'schema': 'hydat'}

    regional_office_id = Column(BigInteger, primary_key=True, server_default=text(
        "nextval('hydat.regional_office_list_regional_office_id_seq'::regclass)"))
    regional_office_name_en = Column(Text)
    regional_office_name_fr = Column(Text)


class SampleRemarkCode(BaseLayerTable):
    __tablename__ = 'sample_remark_codes'
    __table_args__ = {'schema': 'hydat'}

    sample_remark_code = Column(BigInteger, primary_key=True, server_default=text(
        "nextval('hydat.sample_remark_codes_sample_remark_code_seq'::regclass)"))
    sample_remark_en = Column(Text)
    sample_remark_fr = Column(Text)


class SedDataType(BaseLayerTable):
    __tablename__ = 'sed_data_types'
    __table_args__ = {'schema': 'hydat'}

    sed_data_type = Column(Text, primary_key=True)
    sed_data_type_en = Column(Text)
    sed_data_type_fr = Column(Text)


class SedDlyLoad(BaseLayerTable):
    __tablename__ = 'sed_dly_loads'
    __table_args__ = (
        Index('idx_20910_sed_dly_loads_primarykey',
              'station_number', 'year', 'month', unique=True),
        {'schema': 'hydat'}
    )

    station_number = Column(Text, primary_key=True, nullable=False)
    year = Column(BigInteger, primary_key=True, nullable=False)
    month = Column(BigInteger, primary_key=True, nullable=False)
    full_month = Column(BigInteger)
    no_days = Column(BigInteger)
    monthly_mean = Column(DOUBLE_PRECISION)
    monthly_total = Column(DOUBLE_PRECISION)
    first_day_min = Column(BigInteger)
    min = Column(DOUBLE_PRECISION)
    first_day_max = Column(BigInteger)
    max = Column(DOUBLE_PRECISION)
    load1 = Column(DOUBLE_PRECISION)
    load2 = Column(DOUBLE_PRECISION)
    load3 = Column(DOUBLE_PRECISION)
    load4 = Column(DOUBLE_PRECISION)
    load5 = Column(DOUBLE_PRECISION)
    load6 = Column(DOUBLE_PRECISION)
    load7 = Column(DOUBLE_PRECISION)
    load8 = Column(DOUBLE_PRECISION)
    load9 = Column(DOUBLE_PRECISION)
    load10 = Column(DOUBLE_PRECISION)
    load11 = Column(DOUBLE_PRECISION)
    load12 = Column(DOUBLE_PRECISION)
    load13 = Column(DOUBLE_PRECISION)
    load14 = Column(DOUBLE_PRECISION)
    load15 = Column(DOUBLE_PRECISION)
    load16 = Column(DOUBLE_PRECISION)
    load17 = Column(DOUBLE_PRECISION)
    load18 = Column(DOUBLE_PRECISION)
    load19 = Column(DOUBLE_PRECISION)
    load20 = Column(DOUBLE_PRECISION)
    load21 = Column(DOUBLE_PRECISION)
    load22 = Column(DOUBLE_PRECISION)
    load23 = Column(DOUBLE_PRECISION)
    load24 = Column(DOUBLE_PRECISION)
    load25 = Column(DOUBLE_PRECISION)
    load26 = Column(DOUBLE_PRECISION)
    load27 = Column(DOUBLE_PRECISION)
    load28 = Column(DOUBLE_PRECISION)
    load29 = Column(DOUBLE_PRECISION)
    load30 = Column(DOUBLE_PRECISION)
    load31 = Column(DOUBLE_PRECISION)


class SedDlySuscon(BaseLayerTable):
    __tablename__ = 'sed_dly_suscon'
    __table_args__ = (
        Index('idx_20886_sed_dly_suscon_primarykey',
              'station_number', 'year', 'month', unique=True),
        {'schema': 'hydat'}
    )

    station_number = Column(Text, primary_key=True, nullable=False)
    year = Column(BigInteger, primary_key=True, nullable=False)
    month = Column(BigInteger, primary_key=True, nullable=False)
    full_month = Column(BigInteger)
    no_days = Column(BigInteger)
    monthly_total = Column(DOUBLE_PRECISION)
    first_day_min = Column(BigInteger)
    min = Column(DOUBLE_PRECISION)
    first_day_max = Column(BigInteger)
    max = Column(DOUBLE_PRECISION)
    suscon1 = Column(DOUBLE_PRECISION)
    suscon_symbol1 = Column(Text)
    suscon2 = Column(DOUBLE_PRECISION)
    suscon_symbol2 = Column(Text)
    suscon3 = Column(DOUBLE_PRECISION)
    suscon_symbol3 = Column(Text)
    suscon4 = Column(DOUBLE_PRECISION)
    suscon_symbol4 = Column(Text)
    suscon5 = Column(DOUBLE_PRECISION)
    suscon_symbol5 = Column(Text)
    suscon6 = Column(DOUBLE_PRECISION)
    suscon_symbol6 = Column(Text)
    suscon7 = Column(DOUBLE_PRECISION)
    suscon_symbol7 = Column(Text)
    suscon8 = Column(DOUBLE_PRECISION)
    suscon_symbol8 = Column(Text)
    suscon9 = Column(DOUBLE_PRECISION)
    suscon_symbol9 = Column(Text)
    suscon10 = Column(DOUBLE_PRECISION)
    suscon_symbol10 = Column(Text)
    suscon11 = Column(DOUBLE_PRECISION)
    suscon_symbol11 = Column(Text)
    suscon12 = Column(DOUBLE_PRECISION)
    suscon_symbol12 = Column(Text)
    suscon13 = Column(DOUBLE_PRECISION)
    suscon_symbol13 = Column(Text)
    suscon14 = Column(DOUBLE_PRECISION)
    suscon_symbol14 = Column(Text)
    suscon15 = Column(DOUBLE_PRECISION)
    suscon_symbol15 = Column(Text)
    suscon16 = Column(DOUBLE_PRECISION)
    suscon_symbol16 = Column(Text)
    suscon17 = Column(DOUBLE_PRECISION)
    suscon_symbol17 = Column(Text)
    suscon18 = Column(DOUBLE_PRECISION)
    suscon_symbol18 = Column(Text)
    suscon19 = Column(DOUBLE_PRECISION)
    suscon_symbol19 = Column(Text)
    suscon20 = Column(DOUBLE_PRECISION)
    suscon_symbol20 = Column(Text)
    suscon21 = Column(DOUBLE_PRECISION)
    suscon_symbol21 = Column(Text)
    suscon22 = Column(DOUBLE_PRECISION)
    suscon_symbol22 = Column(Text)
    suscon23 = Column(DOUBLE_PRECISION)
    suscon_symbol23 = Column(Text)
    suscon24 = Column(DOUBLE_PRECISION)
    suscon_symbol24 = Column(Text)
    suscon25 = Column(DOUBLE_PRECISION)
    suscon_symbol25 = Column(Text)
    suscon26 = Column(DOUBLE_PRECISION)
    suscon_symbol26 = Column(Text)
    suscon27 = Column(DOUBLE_PRECISION)
    suscon_symbol27 = Column(Text)
    suscon28 = Column(DOUBLE_PRECISION)
    suscon_symbol28 = Column(Text)
    suscon29 = Column(DOUBLE_PRECISION)
    suscon_symbol29 = Column(Text)
    suscon30 = Column(DOUBLE_PRECISION)
    suscon_symbol30 = Column(Text)
    suscon31 = Column(DOUBLE_PRECISION)
    suscon_symbol31 = Column(Text)


class SedSample(BaseLayerTable):
    __tablename__ = 'sed_samples'
    __table_args__ = (
        Index('idx_20970_sed_samples_primarykey', 'station_number',
              'sed_data_type', 'date', unique=True),
        {'schema': 'hydat'}
    )

    station_number = Column(Text, primary_key=True, nullable=False)
    sed_data_type = Column(Text, primary_key=True, nullable=False)
    date = Column(DateTime(True), primary_key=True, nullable=False)
    sample_remark_code = Column(Text, index=True)
    time_symbol = Column(Text)
    flow = Column(DOUBLE_PRECISION)
    flow_symbol = Column(Text)
    sampler_type = Column(Text)
    sampling_vertical_location = Column(Text)
    sampling_vertical_symbol = Column(Text)
    temperature = Column(DOUBLE_PRECISION)
    concentration = Column(DOUBLE_PRECISION)
    concentration_symbol = Column(Text)
    dissolved_solids = Column(DOUBLE_PRECISION)
    sample_depth = Column(DOUBLE_PRECISION)
    streambed = Column(Text)
    sv_depth1 = Column(DOUBLE_PRECISION)
    sv_depth2 = Column(DOUBLE_PRECISION)


class SedSamplesPsd(BaseLayerTable):
    __tablename__ = 'sed_samples_psd'
    __table_args__ = (
        Index('idx_20796_sed_samples_psd_primarykey', 'station_number',
              'sed_data_type', 'date', 'particle_size', unique=True),
        {'schema': 'hydat'}
    )

    station_number = Column(Text, primary_key=True, nullable=False)
    sed_data_type = Column(Text, primary_key=True, nullable=False)
    date = Column(DateTime(True), primary_key=True, nullable=False)
    particle_size = Column(DOUBLE_PRECISION, primary_key=True, nullable=False)
    percent = Column(BigInteger)


class SedVerticalLocation(BaseLayerTable):
    __tablename__ = 'sed_vertical_location'
    __table_args__ = {'schema': 'hydat'}

    sampling_vertical_location_id = Column(Text, primary_key=True)
    sampling_vertical_location_en = Column(Text)
    sampling_vertical_location_fr = Column(Text)


class SedVerticalSymbol(BaseLayerTable):
    __tablename__ = 'sed_vertical_symbols'
    __table_args__ = {'schema': 'hydat'}

    sampling_vertical_symbol = Column(Text, primary_key=True)
    sampling_vertical_en = Column(Text)
    sampling_vertical_fr = Column(Text)


class Station(BaseLayerTable):
    __tablename__ = 'stations'
    __table_args__ = {'schema': 'hydat'}

    station_number = Column(Text, primary_key=True)
    station_name = Column(Text)
    prov_terr_state_loc = Column(Text)
    regional_office_id = Column(Text)
    hyd_status = Column(Text)
    sed_status = Column(Text)
    latitude = Column(DOUBLE_PRECISION)
    longitude = Column(DOUBLE_PRECISION)
    geom = Column(Geometry(geometry_type='POINT', srid=4326))
    drainage_area_gross = Column(DOUBLE_PRECISION)
    drainage_area_effect = Column(DOUBLE_PRECISION)
    rhbn = Column(BigInteger)
    real_time = Column(BigInteger)
    contributor_id = Column(BigInteger)
    operator_id = Column(BigInteger, index=True)
    datum_id = Column(BigInteger)
    dly_flows = relationship("DailyFlow", back_populates="station")
    dly_levels = relationship("DailyLevel", back_populates="station")

    @classmethod
    def get_as_feature(cls, row, geom_col):
        data = streams_v1.StreamStation(
            name=row.station_name,
            url=f"/api/v1/hydat/{row.station_number}",
            stream_flows_url=f"/api/v1/hydat/{row.station_number}/flows",
            stream_levels_url=f"/api/v1/hydat/{row.station_number}/levels",
            external_urls=[
                {
                    "name": "Real-Time Hydrometric Data (Canada)",
                    "url": f"https://wateroffice.ec.gc.ca/report/real_time_e.html?stn={row.station_number}"
                },
            ],
            **row.__dict__)
        pt = Point([row.longitude, row.latitude])
        feat = Feature(geometry=pt, id=getattr(
            row, cls.primary_key_name()), properties=data)
        return feat

    @classmethod
    def get_all(cls, db: Session, search_area: Polygon = None):
        """ gets all records, with an optional bounding box """
        q = db.query(cls).filter(
            cls.prov_terr_state_loc == 'BC')

        if search_area:
            column = cls.get_geom_column(db)
            q = q.filter(
                func.ST_Intersects(func.ST_GeomFromText(
                    search_area.wkt, 4326), column)
            )
        objs = q.all()
        logger.info(objs)
        return objs


class StnDataCollection(BaseLayerTable):
    __tablename__ = 'stn_data_collection'
    __table_args__ = (
        Index('idx_20826_stn_data_collection___uniqueindex',
              'station_number', 'data_type', 'year_from', unique=True),
        {'schema': 'hydat'}
    )

    station_number = Column(Text, primary_key=True, nullable=False)
    data_type = Column(Text, primary_key=True, nullable=False)
    year_from = Column(BigInteger, primary_key=True, nullable=False)
    year_to = Column(BigInteger)
    measurement_code = Column(Text)
    operation_code = Column(Text)


class StnDataRange(BaseLayerTable):
    __tablename__ = 'stn_data_range'
    __table_args__ = (
        Index('idx_20898_stn_data_range_primarykey', 'station_number',
              'data_type', 'sed_data_type', unique=True),
        {'schema': 'hydat'}
    )

    station_number = Column(Text, primary_key=True, nullable=False)
    data_type = Column(Text, primary_key=True, nullable=False)
    sed_data_type = Column(Text, primary_key=True, nullable=False)
    year_from = Column(BigInteger)
    year_to = Column(BigInteger)
    record_length = Column(BigInteger)


class StnDatumConversion(BaseLayerTable):
    __tablename__ = 'stn_datum_conversion'
    __table_args__ = (
        Index('idx_20874_stn_datum_conversion_primarykey',
              'station_number', 'datum_id_from', 'datum_id_to', unique=True),
        {'schema': 'hydat'}
    )

    station_number = Column(Text, primary_key=True, nullable=False)
    datum_id_from = Column(BigInteger, primary_key=True, nullable=False)
    datum_id_to = Column(BigInteger, primary_key=True, nullable=False)
    conversion_factor = Column(DOUBLE_PRECISION)


class StnDatumUnrelated(BaseLayerTable):
    __tablename__ = 'stn_datum_unrelated'
    __table_args__ = (
        Index('idx_20808_stn_datum_unrelated_primarykey',
              'station_number', 'datum_id', unique=True),
        {'schema': 'hydat'}
    )

    station_number = Column(Text, primary_key=True, nullable=False)
    datum_id = Column(BigInteger, primary_key=True, nullable=False)
    year_from = Column(DateTime(True))
    year_to = Column(DateTime(True))


class StnOperationSchedule(BaseLayerTable):
    __tablename__ = 'stn_operation_schedule'
    __table_args__ = (
        Index('idx_20892_stn_operation_schedule___uniqueindex',
              'station_number', 'data_type', 'year', unique=True),
        {'schema': 'hydat'}
    )

    station_number = Column(Text, primary_key=True, nullable=False)
    data_type = Column(Text, primary_key=True, nullable=False)
    year = Column(BigInteger, primary_key=True, nullable=False)
    month_from = Column(Text)
    month_to = Column(Text)


class StnRegulation(BaseLayerTable):
    __tablename__ = 'stn_regulation'
    __table_args__ = {'schema': 'hydat'}

    station_number = Column(Text, primary_key=True)
    year_from = Column(BigInteger)
    year_to = Column(BigInteger)
    regulated = Column(BigInteger)


class StnRemarkCode(BaseLayerTable):
    __tablename__ = 'stn_remark_codes'
    __table_args__ = {'schema': 'hydat'}

    remark_type_code = Column(BigInteger, primary_key=True, server_default=text(
        "nextval('hydat.stn_remark_codes_remark_type_code_seq'::regclass)"))
    remark_type_en = Column(Text)
    remark_type_fr = Column(Text)


class StnRemark(BaseLayerTable):
    __tablename__ = 'stn_remarks'
    __table_args__ = (
        Index('idx_20868_stn_remarks___uniqueindex', 'station_number',
              'remark_type_code', 'year', unique=True),
        {'schema': 'hydat'}
    )

    station_number = Column(Text, primary_key=True, nullable=False)
    remark_type_code = Column(BigInteger, primary_key=True, nullable=False)
    year = Column(BigInteger, primary_key=True, nullable=False)
    remark_en = Column(Text)
    remark_fr = Column(Text)


class StnStatusCode(BaseLayerTable):
    __tablename__ = 'stn_status_codes'
    __table_args__ = {'schema': 'hydat'}

    status_code = Column(Text, primary_key=True)
    status_en = Column(Text)
    status_fr = Column(Text)


class Version(BaseLayerTable):
    __tablename__ = 'version'
    __table_args__ = {'schema': 'hydat'}

    version = Column(Text, primary_key=True)
    date = Column(DateTime(True))
