"""
Analysis functions for data in the Wally system
"""
import json
from logging import getLogger
from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session
from api.v1.isolines.controller import calculate_runnoff_in_area
from api.v1.aggregator.helpers import transform_4326_3005
from shapely.geometry import Polygon, MultiPolygon, shape
from shapely.ops import transform
from api.db.utils import get_db

logger = getLogger("isolines")

router = APIRouter()


@router.get("/runoff")
def get_isoline_runoff(
        db: Session = Depends(get_db),
        polygon: str = Query(
            "", title="Search polygon",
            description="Polygon to search within"
        )):
    if not polygon:
        raise HTTPException(
            status_code=400, detail="No search bounds. Supply a `polygon` (geojson geometry)")

    if polygon:
        poly_parsed = json.loads(polygon)
        polygon = MultiPolygon([Polygon(x) for x in poly_parsed])

    if polygon.area <= 0:
        raise HTTPException(
            status_code=400, detail="Polygon has zero area")
    polygon = transform(transform_4326_3005, polygon)

    runoff = calculate_runnoff_in_area(db, polygon)

    return {
        "runoff": runoff
    }
