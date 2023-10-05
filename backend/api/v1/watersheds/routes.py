"""
Endpoints for returning statistics about watersheds
"""
from logging import getLogger
import datetime
import json
import requests
import pprint
from fastapi import APIRouter, Depends, HTTPException, Query, Path
from fastapi.encoders import jsonable_encoder
from sqlalchemy.orm import Session

from shapely.geometry import shape, Point
from urllib.parse import unquote

from api.db.utils import get_db
from api.v1.watersheds.controller import (
    export_summary_as_zipped_shp,
    get_watershed_details,
    surface_water_rights_licences,
    surface_water_approval_points,
    calculate_watershed,
    get_watershed,
    surficial_geology,
    export_summary_as_xlsx,
    known_fish_observations,
    find_50k_watershed_codes,
    get_stream_inventory_report_link_for_region,
    get_scsb2016_input_stats
)
from api.v1.hydat.controller import (get_stations_in_area, get_fasstr_longterm_summary)
from api.v1.hydat.routes import get_station
from api.v1.watersheds.schema import (
    GeneratedWatershedDetails
)
from api.v1.models.isolines.controller import calculate_runoff_in_area
from api.v1.models.scsb2016.controller import get_hydrological_zone, calculate_mean_annual_runoff, model_output_as_dict
from api.v1.user.db_models import User
from api.v1.user.session import get_user
from api.config import WATERSHED_DEBUG


logger = getLogger("aggregator")

router = APIRouter()

watershed_feature_description = """
    Watershed features follow the format <dataset>.<id>. Dataset is either
    the DataBC dataset code or 'calculated' for Wally generated watersheds.
    If using a calculated watershed, `id` is the FWA Watershed feature ID
    to start calculating a watershed from.
    Example:
    'WHSE_WATER_MANAGEMENT.HYDZ_HYD_WATERSHED_BND_POLY.1111111'
    'calculated.1111111'.
    """


@router.get('/streamflow_inventory')
def get_streamflow_inventory_report_link(
    db: Session = Depends(get_db),
    point: str = Query(
        "", title="Search point",
        description="Point to search within")):
    """ returns a link to the streamflow inventory report for this watershed"""
    if not point:
        raise HTTPException(
            status_code=400, detail="No search point. Supply a `point` in [long, lat] format")

    point_parsed = json.loads(point)
    point = Point(point_parsed)

    report_link, report_name = get_stream_inventory_report_link_for_region(
        point)

    return {
        "report_link": report_link,
        "report_name": report_name,
        "hydrologic_zone": get_hydrological_zone(point)
    }


@router.get('/', response_model=GeneratedWatershedDetails)
def get_watersheds(
    db: Session = Depends(get_db),
    user: User = Depends(get_user),
    point: str = Query(
        "", title="Search point",
        description="Point to search within"),
    upstream_method: str = Query(
        "DEM+FWA", title="Upstream catchment estimation method",
        description="Method for estimating upstream catchment area. See watersheds/controller.py"
    )
):
    """ returns a list of watersheds at this point, if any.
    Watersheds are sourced from the following datasets:
    https://catalogue.data.gov.bc.ca/dataset/freshwater-atlas-assessment-watersheds
    https://catalogue.data.gov.bc.ca/dataset/hydrology-hydrometric-watershed-boundaries

    """

    if not point:
        raise HTTPException(
            status_code=400, detail="No search point. Supply a `point` (geojson geometry)")

    if point:
        point_parsed = json.loads(point)
        point = Point(point_parsed)

    upstream_method = unquote(upstream_method)

    return calculate_watershed(
        db, user, point, upstream_method=upstream_method)


@router.get('/{watershed_feature}')
def watershed_stats(
    db: Session = Depends(get_db),
    user: User = Depends(get_user),
    watershed_feature: str = Path(...,
                                  title="The watershed feature ID at the point of interest",
                                  description=watershed_feature_description),
    format: str = Query(
        "json",
        title="Format",
        description="Format to return results in. Options: json (default), xlsx, shp (zipped shapefile)"
    ),
    generated_watershed_id: int = Query(
        None,
        title="Generated watershed ID",
        description="An ID assigned to each unique watershed WALLY has generated."
    )
):
    """ aggregates statistics/info about a watershed """
    if WATERSHED_DEBUG:
        logger.warning("Watershed Details - Request Started")

    # watershed area calculations
    watershed_data = get_watershed(db, user, watershed_feature,
                                   generated_watershed_id=generated_watershed_id)
    watershed = watershed_data.watershed
    watershed_poly = shape(watershed.geometry)

    watershed_details = get_watershed_details(db, watershed)
    wd = watershed_details  # purely for shorthand below

    # isoline model outputs
    isoline_runoff_model = calculate_runoff_in_area(db, watershed_poly)

    # custom linear mad model outputs
    scsb2016_model = calculate_mean_annual_runoff(
        db, wd["hydrological_zone"],
        wd["median_elevation"],
        wd["glacial_coverage"],
        wd["annual_precipitation"],
        wd["potential_evapotranspiration"],
        wd["drainage_area"],
        wd["solar_exposure"],
        wd["average_slope"])
    
     # hydro stations from federal source
    hydrometric_stations = get_stations_in_area(db, shape(watershed.geometry))

    scsb2016_input_stats = get_scsb2016_input_stats(db)

    data = {
        "watershed_name": watershed.properties.get("name", None),
        "watershed_source": watershed.properties.get("watershed_source", None),
        **watershed_details,
        "runoff_isoline_avg": (isoline_runoff_model['runoff'] /
                               isoline_runoff_model['area'] * 1000) if isoline_runoff_model['area'] else 0,
        "runoff_isoline_discharge_m3s": isoline_runoff_model['runoff'] / 365 / 24 / 60 / 60,
        "scsb2016_model": scsb2016_model,
        "scsb2016_output": model_output_as_dict(scsb2016_model),
        "scsb2016_input_stats": scsb2016_input_stats,
        "hydrometric_stations": hydrometric_stations,
        "generated_watershed_id": watershed_data.generated_watershed_id
        
    }

    if format == 'xlsx':

        #For each station found in the watershed we will add the station number to a new array. 
        #Then for the first station in that list, retrieve the monthly data to calculate averages. 
    
        stationNumbers = []
        for station in hydrometric_stations:
            stationNumber = station.properties.station_number  # Access the 'stream_flows_url' property
            if stationNumber:
                stationNumbers.append(stationNumber)
        

        #Take the first Hydro Station and get the FASSTR DATA
        #Extract Stations annual average, and monthly data
        #Creating a new array which will be passed to the excel export
        # # TO DO: PENDING REVIEW FROM TESTERS - Make multiple templates to handle more than 1 hydat station per report.  
        
        try:
            if stationNumbers:
                flowData = get_fasstr_longterm_summary(db, stationNumbers[0])
                StationMean = flowData.mean
                flowMonths = flowData.months
                flowMean = []
                for month in flowMonths:
                    flowMean.append((month.mean / StationMean * 100))

                # Only want to do this when a hydrometric station is found within the area
                # Extracting data for date range from Hydro Metric station
                # This is not included in the FASSTR data, so will be extracted directly from the 
                # hydrometric station as Station number is available at this point.
                stationNumber = hydrometric_stations[0].properties.station_number
                stationYearData = get_station(stationNumber, db)
                startYear = min(stationYearData.flow_years)
                endYear = max(stationYearData.flow_years)
                data["flowData"] = flowData
                data["startYear"] = startYear
                data["endYear"] = endYear
                data["flowMean"] = flowMean
                    
        except Exception as e:
            logger.error("Error:", e)
            logger.error("Hydrometric station has incomplete information")
        
        try:
            #Simliar to above but using Wally modeled data instead of FASSTR
            #Get the scsb2016 data, calculate the annual discharge for baseline. 
            #Make a list of the monthly discharges and calculate how that compare to the annual average
            #This will be added to the excel export
            monthlyDischarge = model_output_as_dict(scsb2016_model)
            baseLine = monthlyDischarge["mad"]
            monthlyDischarge = monthlyDischarge["monthly_discharge"]
            monthAverages = []
            for key in monthlyDischarge:
                monthAverages.append(monthlyDischarge[key]["model_result"] / baseLine * 100)
            data["baseLineMean"] = monthAverages
        except Exception as e:
            logger.error("Error:", e)
            logger.info("Error loading scbc2016 data for selected watershed")
        


        try: 
            # Retrieve approval data
            # Add all of the properties for each object returned to the data object
            # Once data is passed to excel will loop through to extract each approval in template
            approvals_data = surface_water_approval_points(watershed_poly)
            if approvals_data.approvals and approvals_data.approvals.features:
                data["approvals_data"] = [dict(**x.properties)
                                    for x in approvals_data.approvals.features]
        except Exception as e:
            logger.error("Error:", e)
            logger.info("Error finding approval points for selected watershed")
        
        data['generated_date'] = datetime.datetime.now().strftime(
            "%Y-%m-%d %H:%M:%S")


        try:
            #Get lisence data, for each licence add it to a dictionary and attach to the data object
            #Will use a loop in the excel doc to iterate through and display each of the licences
            licence_data = surface_water_rights_licences(watershed_poly)
            if licence_data.licences and licence_data.licences.features:
                data['licences'] = [dict(**x.properties)
                                    for x in licence_data.licences.features]
                data['inactive_licences'] = [dict(**x.properties)
                                            for x in licence_data.inactive_licences.features]
                data['licences_count_pod'] = len(licence_data.licences.features)
        except Exception as e:
            logger.error("Error:", e)
            logger.info("Error finding approval licenses for selected watershed")


        try:
            #Get Fish obvservation data to add to excel export
            #Add each type of fish species returned from the Known observations to data in a new dictionary
            #Important to only do it for fish_data.fish_species_data otherwise it will add all observations to the dictionary
            #once these have been added to the dictionary created a podcount to use an index when importing to excel
            
            fish_data = known_fish_observations(watershed_poly)
            if fish_data and fish_data.fish_species_data:
                data["fish_data"] = [dict(**x)
                                    for x in fish_data.fish_species_data]
        except Exception as e:
            logger.error("Error:", e)
            logger.info("Error finding fish observation data for selected watershed")

        return export_summary_as_xlsx(jsonable_encoder(data))

    if format == 'shp':
        return export_summary_as_zipped_shp(watershed_poly, jsonable_encoder(data))

    if WATERSHED_DEBUG:
        logger.warning("Watershed Details - Request Finished")

    return data


@router.get('/details/')
def get_generated_watershed_details(
    db: Session = Depends(get_db),
    user: User = Depends(get_user),
    point: str = Query(
        "", title="Search point",
        description="Point to search within"),
    use_sea: bool = True
):
    """ returns generated watershed characteristics, used as source for modelling data """

    if not point:
        raise HTTPException(
            status_code=400, detail="No search point. Supply a `point` (geojson geometry)")

    if point:
        point_parsed = json.loads(point)
        point = Point(point_parsed)

    if WATERSHED_DEBUG:
        logger.warning("watershed details point: %s", point)

    watershed = calculate_watershed(db, user, point)

    if not watershed:
        raise HTTPException(
            status_code=500, detail="Could not generate watershed.")

    watershed_details = get_watershed_details(db, watershed, use_sea)

    if WATERSHED_DEBUG:
        logger.warning("watershed details: %s", watershed_details)

    return watershed_details


@router.get('/{watershed_feature}/fwa_50k_codes')
def get_50k_watershed_codes(
    db: Session = Depends(get_db),
    user: User = Depends(get_user),
    watershed_feature: str = Path(...,
                                  title="The watershed feature ID at the point of interest",
                                  description=watershed_feature_description),
    generated_watershed_id: int = Query(
        None,
        title="Generated watershed ID",
        description="An ID assigned to each unique watershed WALLY has generated."
    )
):
    """ returns 50k (old) watershed codes. Useful for searching legacy applications """

    watershed = get_watershed(db, user, watershed_feature,
                              generated_watershed_id=generated_watershed_id).watershed

    return find_50k_watershed_codes(db, shape(watershed.geometry))


@router.get('/{watershed_feature}/licences')
def get_watershed_demand(
    db: Session = Depends(get_db),
    user: User = Depends(get_user),
    watershed_feature: str = Path(...,
                                  title="The watershed feature ID at the point of interest",
                                  description=watershed_feature_description),
    generated_watershed_id: int = Query(
        None,
        title="Generated watershed ID",
        description="An ID assigned to each unique watershed WALLY has generated."
    )
):
    """ returns data about watershed demand by querying DataBC """

    watershed = get_watershed(db, user, watershed_feature,
                              generated_watershed_id=generated_watershed_id).watershed

    return surface_water_rights_licences(shape(watershed.geometry))


@router.get('/{watershed_feature}/approvals')
def get_watershed_short_term_demand(
    db: Session = Depends(get_db),
    user: User = Depends(get_user),
    watershed_feature: str = Path(...,
                                  title="The watershed feature ID at the point of interest",
                                  description=watershed_feature_description),
    generated_watershed_id: int = Query(
        None,
        title="Generated watershed ID",
        description="An ID assigned to each unique watershed WALLY has generated."
    )
):
    """ returns data about watershed demand by querying DataBC """

    watershed = get_watershed(db, user, watershed_feature,
                              generated_watershed_id=generated_watershed_id).watershed

    return surface_water_approval_points(shape(watershed.geometry))


@router.get('/{watershed_feature}/surficial_geology')
def get_surficial_geology(
    db: Session = Depends(get_db),
    user: User = Depends(get_user),
    watershed_feature: str = Path(...,
                                  title="The watershed feature ID at the point of interest",
                                  description=watershed_feature_description),
    generated_watershed_id: int = Query(
        None,
        title="Generated watershed ID",
        description="An ID assigned to each unique watershed WALLY has generated."
    )
):
    """ returns data about watershed demand by querying DataBC """

    watershed = get_watershed(db, user, watershed_feature,
                              generated_watershed_id=generated_watershed_id).watershed

    surf_geol_summary = surficial_geology(shape(watershed.geometry))

    return surf_geol_summary


@router.get('/{watershed_feature}/fish_observations')
def get_fish_observations(
    db: Session = Depends(get_db),
    user: User = Depends(get_user),
    watershed_feature: str = Path(...,
                                  title="The watershed feature ID at the point of interest",
                                  description=watershed_feature_description),
    generated_watershed_id: int = Query(
        None,
        title="Generated watershed ID",
        description="An ID assigned to each unique watershed WALLY has generated."
    )
):
    """ returns data about fish observations within a watershed by querying DataBC """

    watershed = get_watershed(db, user, watershed_feature,
                              generated_watershed_id=generated_watershed_id).watershed

    watershed_fish_observations = known_fish_observations(
        shape(watershed.geometry))

    return watershed_fish_observations
