"""
API data models for Projects.
"""
from pydantic import BaseModel, ValidationError, validator
from typing import Optional, List
from shapely import wkt
from shapely.errors import WKTReadingError
from api.constants import FEATURE_TYPES
from uuid import UUID


class SavedAnalysisMapLayer(BaseModel):
    map_layer: Optional[str]


class SavedAnalysis(BaseModel):
    name: Optional[str]
    description: Optional[str]
    geometry: Optional[str]
    feature_type: Optional[str]
    zoom_level: Optional[float]
    map_layers: Optional[List[str]]


class SavedAnalysisCreate(SavedAnalysis):

    @validator('geometry')
    def geometry_wkt(cls, v):
        try:
            geom = wkt.loads(v)
        except WKTReadingError:
            raise ValueError('Invalid geometry')
        return v

    @validator('feature_type')
    def feature_type_valid(cls, v):

        if v not in FEATURE_TYPES:
            raise ValueError('Invalid feature type')


class SavedAnalysisGet(SavedAnalysis):
    saved_analysis_id: UUID
