-- BC STATION LOCATIONS
select STATION_NUMBER, LATITUDE, LONGITUDE
from STATIONS where PROV_TERR_STATE_LOC = 'BC';

-- BC STATION LOCATIONS MEAN NOT NULL
select DISTINCT ANNUAL_STATISTICS.STATION_NUMBER, STATIONS.LATITUDE, STATIONS.LONGITUDE
from ANNUAL_STATISTICS JOIN STATIONS on ANNUAL_STATISTICS.STATION_NUMBER = STATIONS.STATION_NUMBER
where STATIONS.PROV_TERR_STATE_LOC = 'BC'
and ANNUAL_STATISTICS.MEAN is not NULL;

-- BC DLY MONTHLY FLOWS (full months only)
select DLY_FLOWS.STATION_NUMBER, DLY_FLOWS."YEAR", DLY_FLOWS."MONTH", 
DLY_FLOWS.NO_DAYS, DLY_FLOWS.MONTHLY_MEAN, DLY_FLOWS.MONTHLY_TOTAL, DLY_FLOWS."MIN", DLY_FLOWS."MAX", 
STATIONS.DRAINAGE_AREA_GROSS, STATIONS.DRAINAGE_AREA_EFFECT, STATIONS.LATITUDE, STATIONS.LONGITUDE
from DLY_FLOWS JOIN STATIONS on DLY_FLOWS.STATION_NUMBER = STATIONS.STATION_NUMBER
where DLY_FLOWS.FULL_MONTH = 1
and DLY_FLOWS.MONTHLY_MEAN is not NULL and DLY_FLOWS."MONTH" = 12
and STATIONS.PROV_TERR_STATE_LOC = 'BC';

-- BC MEAN ANNUAL FLOWS
select ANNUAL_STATISTICS.STATION_NUMBER, ANNUAL_STATISTICS.YEAR, 
ANNUAL_STATISTICS.MEAN, ANNUAL_STATISTICS."MIN", ANNUAL_STATISTICS."MAX",
ANNUAL_STATISTICS.MIN_MONTH, ANNUAL_STATISTICS.MAX_MONTH, 
STATIONS.LATITUDE, STATIONS.LONGITUDE, STATIONS.DRAINAGE_AREA_GROSS -- Km^2
from ANNUAL_STATISTICS JOIN STATIONS on ANNUAL_STATISTICS.STATION_NUMBER = STATIONS.STATION_NUMBER
where STATIONS.PROV_TERR_STATE_LOC = 'BC'
and ANNUAL_STATISTICS.MEAN is not NULL;

-- MAIN SOURCE DATA QUERY
select ANNUAL_STATISTICS.STATION_NUMBER, ANNUAL_STATISTICS.YEAR, 
ANNUAL_STATISTICS.MEAN, ANNUAL_STATISTICS."MIN", ANNUAL_STATISTICS."MAX",
ANNUAL_STATISTICS.MIN_MONTH, ANNUAL_STATISTICS.MAX_MONTH, 
STATIONS.LATITUDE, STATIONS.LONGITUDE, STATIONS.DRAINAGE_AREA_GROSS -- Km^2
from ANNUAL_STATISTICS 
JOIN STATIONS on ANNUAL_STATISTICS.STATION_NUMBER = STATIONS.STATION_NUMBER
JOIN STN_REGULATION on ANNUAL_STATISTICS.STATION_NUMBER = STN_REGULATION.STATION_NUMBER
where STATIONS.PROV_TERR_STATE_LOC = 'BC'
-- and STN_REGULATION.REGULATED != 1
and ANNUAL_STATISTICS.MEAN is not NULL
and ANNUAL_STATISTICS.DATA_TYPE = 'Q';

select * from STN_REGULATION where STATION_NUMBER = '08MH029';

select count(DISTINCT STATION_NUMBER) from STATIONS where PROV_TERR_STATE_LOC = 'BC';
SELECT count(*) from STATIONS where PROV_TERR_STATE_LOC = 'BC';
