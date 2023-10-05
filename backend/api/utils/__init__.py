""" general utility functions """

import os
import uuid
import fiona
import math
from osgeo import gdal
from typing import Optional
from tempfile import TemporaryDirectory
from shapely.geometry import Polygon, Point, mapping
from shapely.ops import transform
from api.v1.aggregator.helpers import transform_4326_3005, transform_3005_4326
from logging import getLogger

logger = getLogger("utils")


def normalize_quantity(qty, qty_unit: str):
    """ takes a qty and a unit (as a string) and returns the quantity in m3/year
        accepts:
        m3/sec
        m3/day
        m3/year
        Returns None if QUANTITY_UNITS doesn't match one of the options.
    """

    qty_unit = qty_unit.strip()

    if qty_unit == 'm3/year':
        return qty
    elif qty_unit == 'm3/day':
        return qty * 365
    elif qty_unit == 'm3/sec':
        return qty * 60 * 60 * 24 * 365
    else:
        # could not interpret QUANTITY_UNIT value
        return None
    
def normalize_quantity_seconds(qty, qty_unit: str):
    """ takes a qty and a unit (as a string) and returns the quantity in m3/second
        accepts:
        m3/sec
        m3/day
        m3/year
        Returns None if QUANTITY_UNITS doesn't match one of the options.
    """

    qty_unit = qty_unit.strip()

    if qty_unit == 'm3/year':
        return qty / (60 * 60 * 24 * 365)
    elif qty_unit == 'm3/day':
        return qty / (60 * 60 * 24)
    elif qty_unit == 'm3/sec':
        return qty 
    else:
        # could not interpret QUANTITY_UNIT value
        return None


def get_file_ext(file_path: str) -> str:
    file_name, file_extension = os.path.splitext(file_path)
    return file_extension


def get_file_name(file_path: str) -> str:
    file_name, file_extension = os.path.splitext(file_path)
    return file_name


def generate_file_name(file_name: str) -> str:
    file_ext = get_file_ext(file_name)
    return f'{str(uuid.uuid4())}{file_ext}'


def new_polygon(centroid: Point, size_sqm: float = 5e6):
    """
    Returns a new polygon centered at `centroid` with area `size_sqm` (sq. m)
    centroid should be EPSG:4326
    """

    centroid_3005 = transform(transform_4326_3005, centroid)

    side = math.sqrt(size_sqm)

    poly = Polygon((
        (centroid_3005.x - side/2, centroid_3005.y - side/2),
        (centroid_3005.x + side/2, centroid_3005.y - side/2),
        (centroid_3005.x + side/2, centroid_3005.y + side/2),
        (centroid_3005.x - side/2, centroid_3005.y + side/2),
        (centroid_3005.x - side/2, centroid_3005.y - side/2),
    ))

    return transform(transform_3005_4326, poly)


# The maximum artificial buffer we should use for sampling raster values in a small area.
# This is needed for when we try to sample raster data in areas that are too
# small to return full pixels, and we need to buffer the area and retry.  This constant
# represents the max buffered area to use before raising an exception rather than
# retrying.
MAX_RASTER_RETRY_BUFFER_AREA_SQM = 20e6


def get_raster_dataset(file_name: str, area: Polygon, no_data: int = -32768, retry_min_size: Optional[float] = None):
    """
    Returns a GDAL Dataset containing raster data for a given area

    Area must use crs EPSG:4326 (lat long)

    retry_min_size is an optional argument that sets the size of a polygon to retry, if we fail to
    receive a single pixel when sampling the raster file.  A new, square polygon will be created with
    `retry_min_size` (in square metres) and the function will be called again until we either
    hit MAX_RASTER_RETRY_BUFFER_AREA_SQM or we get a valid result (a dataset with more than 0 pixels)
    """

    with TemporaryDirectory() as rasterdir:
        extents_file = rasterdir + "/extents.shp"

        # Define a Polygon feature geometry with one attribute
        poly_schema = {
            'geometry': 'Polygon',
            'properties': {'id': 'int'},
        }

        # Write a new Shapefile with the area of interest
        with fiona.open(extents_file, 'w', 'ESRI Shapefile', poly_schema, crs=f"EPSG:4326") as c:
            c.write({
                'geometry': mapping(area),
                'properties': {'id': 1},
            })

        # use gdalwarp to get a raster clipped to the area of interest
        dataset = gdal.Warp("", file_name, format="MEM",
                            cutlineDSName=extents_file, cropToCutline=True,
                            dstNodata=no_data,
                            )

        if not dataset and retry_min_size:
            retry_area_sqm = retry_min_size
            logger.warning(
                'get_raster_dataset: Area was too small to sample a pixel.  Retrying with a %s sq km square',
                retry_area_sqm / 1e6)
            retry_area = new_polygon(area.centroid, size_sqm=retry_area_sqm)

            # set the next retry size to pass into the recursion call. If we're still within the max acceptable
            # buffered size, set it to double the current area.  If we've hit our limit, set it to None
            # and we will end up raising an exception instead of retrying.
            next_retry_size = 2*retry_min_size if retry_min_size < MAX_RASTER_RETRY_BUFFER_AREA_SQM else None
            return get_raster_dataset(file_name, area=retry_area, no_data=no_data, retry_min_size=next_retry_size)

        if not dataset:
            raise Exception("Dataset could not be loaded. No data returned.")

        return dataset
