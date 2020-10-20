
SELECT count(*) from DLY_FLOWS;
SELECT count(*) from DLY_LEVELS where YEAR > 2000;
SELECT count(DISTINCT STATION_NUMBER) from DLY_LEVELS where YEAR > 2000;

select count(*) from DLY_FLOWS where MONTHLY_MEAN is not NULL and YEAR > 2000;
select * from DLY_FLOWS limit 1;
select distinct FLOW_SYMBOL1 from DLY_FLOWS;


SELECT count(DISTINCT STATION_NUMBER) from STATIONS where STATION_NUMBER in 
(SELECT DISTINCT STATION_NUMBER from DLY_FLOWS where YEAR > 2000 and FULL_MONTH = 1 and MONTHLY_MEAN is not NULL)
and PROV_TERR_STATE_LOC = 'BC';

SELECT STATION_NUMBER, STATION_NAME, DRAINAGE_AREA_GROSS, LATITUDE, LONGITUDE from STATIONS where STATION_NUMBER in 
(SELECT DISTINCT STATION_NUMBER from DLY_FLOWS where YEAR > 2000 and FULL_MONTH = 1 and MONTHLY_MEAN is not NULL)
and PROV_TERR_STATE_LOC = 'BC';

-- DLY_FLOWS in BC, gt 2000, fullmonth
select STATION_NUMBER, "YEAR", "MONTH", NO_DAYS, MONTHLY_MEAN, MONTHLY_TOTAL, "MIN", "MAX" from DLY_FLOWS
where STATION_NUMBER in (SELECT STATION_NUMBER from STATIONS where STATION_NUMBER in 
(SELECT DISTINCT STATION_NUMBER from DLY_FLOWS where YEAR > 2000 and FULL_MONTH = 1 and MONTHLY_MEAN is not NULL)
and PROV_TERR_STATE_LOC = 'BC');

select * from ANNUAL_STATISTICS limit 1;

-- Get Annual Statistics Information
-- select count(distinct STATION_NUMBER)
select distinct STATION_NUMBER
-- select STATION_NUMBER, "YEAR", MEAN, MIN_MONTH, "MIN", MAX_MONTH, "MAX"
from ANNUAL_STATISTICS 
where "YEAR" >= 2000 
and MEAN is not NULL
and STATION_NUMBER in (select STATION_NUMBER from STATIONS where PROV_TERR_STATE_LOC = 'BC');


SELECT STATION_NUMBER, STATION_NAME, DRAINAGE_AREA_GROSS, LATITUDE, LONGITUDE from STATIONS where STATION_NUMBER in 
(select distinct STATION_NUMBER from ANNUAL_STATISTICS where "YEAR" >= 2000 and MEAN is not NULL
and STATION_NUMBER in (select STATION_NUMBER from STATIONS where PROV_TERR_STATE_LOC = 'BC'));



-- DLY_FLOWS in BC, fullmonth

select DLY_FLOWS.STATION_NUMBER, DLY_FLOWS."YEAR", DLY_FLOWS."MONTH", 
DLY_FLOWS.NO_DAYS, DLY_FLOWS.MONTHLY_MEAN, DLY_FLOWS.MONTHLY_TOTAL, DLY_FLOWS."MIN", DLY_FLOWS."MAX", 
STATIONS.DRAINAGE_AREA_GROSS, STATIONS.DRAINAGE_AREA_EFFECT, STATIONS.LATITUDE, STATIONS.LONGITUDE
from DLY_FLOWS JOIN STATIONS on DLY_FLOWS.STATION_NUMBER = STATIONS.STATION_NUMBER
where DLY_FLOWS.FULL_MONTH = 1
and DLY_FLOWS.MONTHLY_MEAN is not NULL and DLY_FLOWS."MONTH" = 12
and STATIONS.PROV_TERR_STATE_LOC = 'BC';



SELECT count(*) from STATIONS where PROV_TERR_STATE_LOC = 'BC';

