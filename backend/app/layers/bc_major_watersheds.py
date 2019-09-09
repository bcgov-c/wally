# coding: utf-8
from sqlalchemy import Integer, String, Column, DateTime, BLOB, Float
from app.db.base_class import BaseTable
from geoalchemy2 import Geometry


class BcMajorWatersheds(BaseTable):
    __tablename__ = 'bc_major_watersheds'

    AREA = Column(Float, comment='')
    PERIMETER = Column(Float, comment='')
    MAJOR_WATERSHED_CODE = Column(String, comment='')
    MAJOR_WATERSHED_SYSTEM = Column(String, comment='')
    FCODE = Column(String, comment='')
    GEOMETRY = Column(Geometry, comment='GEOMETRY is the column used to reference the spatial coordinates '
                                        'defining the feature.')
    OBJECTID = Column(String, primary_key=True, comment='OBJECTID is a required attribute of feature classes and '
                                                        'object classes in a geodatabase.')
    SE_ANNO_CAD_DATA = Column(BLOB, comment='SE_ANNO_CAD_DATA is a binary column used by spatial tools to store '
                                            'annotation, curve features and CAD data when using the SDO_GEOMETRY '
                                            'storage data type.')
    FEATURE_AREA_SQM = Column(Float, comment='FEATURE_AREA_SQM is the system calculated area of a two-dimensional '
                                             'polygon in square meters')
    FEATURE_LENGTH_M = Column(Float, comment='FEATURE_LENGTH_M is the system calculated length or perimeter of a '
                                             'geometry in meters')
