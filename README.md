# Water Allocation Data Library

1. [Working on WALLY (Getting started)](#working-on-wally-getting-started)
1. [Application architecture](#application-architecture)
1. [Feature-specific documentation](#feature-specific-documentation)
1. [Contributing / Code of Conduct](#contributing)

## Working on WALLY (Getting started)

WALLY runs locally using docker-compose (for the backend stack) and node (for the frontend web app development server).  The local environment
includes fixtures that cover the Whistler, BC area.

### Prerequisites

* Docker
* Node

#### Environment variables
Running WALLY locally requires the following env vars:

`MAPBOX_ACCESS_TOKEN` (required): a token from mapbox.com for making Mapbox API requests (e.g. requesting tiles and map images).

#### Feature flags

The backend also uses [Pydantic's settings management](https://github.com/bcgov-c/wally/blob/0dc732c241bff5e8d8ce72d40ab88b9286e4566c/backend/api/config.py#L61-L82)
Create a file called `dev.env` under `backend/.config/` to test your feature flags and other settings.

### Running the backend services
Start the backend API and database stack with Docker Compose:

```bash
docker-compose up -d
```

This will start up Wally's Python backend, PostGIS, and Minio services.

Database fixtures will be loaded automatically using the `backend/api/initial_data.py` script. Raster fixtures are also
automatically copied to the Minio container. This script is only run on local and PR dev environments.


#### Access the database directly

The database is exposed at `localhost:5432`.  For a shortcut to launch the psql client, use:

```sh
make psql
```


#### Browse the backend API documentation

The backend's Swagger API documentation is available at http://localhost:8000/docs.


### Running the frontend web app
Start the frontend development server:
```bash
cd frontend
npm install
npm run serve
```

The frontend will be deployed at http://localhost:8080/.  It requires the backend docker-compose stack to also be running.

## Application architecture

Wally is deployed as a group of services:

* Luketo Proxy (Gatekeeper) - Luketo Proxy (formerly Keycloak Gatekeeper) is used to authenticate incoming requests.  This is also the entrypoint into the WALLY app for all requests (on OpenShift).

* `frontend/` (Vue app served by nginx) - The frontend folder contains Wally's web app and a Dockerfile for an nginx service that serves the built assets in the `dist` folder.
nginx also proxies requests to other services based on the `nginx.conf.templ` file in the frontend folder.

* `backend/` (FastAPI Python backend) - the backend folder contains the REST API backend that serves data at the `/api/v1/` path.

* PostGIS - Data used by Wally is stored in a PostGIS-enabled PostgreSQL database, which uses Patroni for managing multiple replicas.  The Dockerfile and other build resources are in `openshift/patroni-postgis`.
PostGIS is used for querying the Freshwater Atlas and HYDAT data as well as storing user project data.

* Minio - WALLY uses Minio to host spatial data raster files, store Freshwater Atlas data, and store uploaded user files. See the configuration in `openshift/ocp4/minio`.


### WALLY and OpenShift

WALLY runs on BCGov's OpenShift 4 platform.

For day to day feature work, WALLY's CI/CD will take care of deploying PR environments and automatically deploying merged PR's to staging.  See `Jenkinsfile.ocp4` and
the templates in the `openshift/ocp4` folder.

For configuration and data that WALLY needs to get up and running the first time, see [Migrating to OpenShift 4](openshift/ocp4/README.md).

### Spatial data

WALLY relies on spatial raster files, in Cloud Optimized GeoTIFF format, hosted on Minio.  The files will be accessed at runtime during certain requests (to query precipitation, for example).
Querying cloud optimized geotiff files using GDAL has generally been faster (in our environment) than PostGIS and is easier to set up.

The files are in the `raster` Minio bucket on all environments.

If you need to edit or update spatial raster files, you'll need to create two files: the BC-wide file that staging and production will use,
and a Whistler area cropped version for local dev fixtures.

See [the Watersheds README](backend/api/v1/watersheds/README.md) for instructions on how to create Cloud Optimized GeoTIFF rasters for use with WALLY,
and the [fixture extents README](backend/fixtures/extents/README.md) for instructions on how to create a corresponding fixture file in the `raster` dir.

All raster fixtures in the `/backend/fixtures/raster` dir will automatically be copied to the local Minio instance when using `docker-compose`. However, for staging and production,
you must manually upload any new raster files to the staging and prod minio servers.

## Feature-specific documentation

### Surface Water Analysis - Watershed delineation

The Surface Water Analysis feature delineates watersheds from a point that the user drops.  This requires
Freshwater Atlas fundamental watersheds and Freshwater Atlas stream networks layers to be loaded into
the database, as well as a stream-burned DEM. See the [the Watersheds README](backend/api/v1/watersheds/README.md)
for instructions on creating the DEMs.

The stream-burned DEM needs to be loaded in Minio, and the extents of the DEM need to be loaded in
the `dem.stream_burned_cdem_tile` database table. The Surface Water Analysis feature will automatically
select the best DEM in the area based on the extents in the table.

See [the Caribou DEM extent migration](backend/alembic/versions/20210625150931_add_caribou_dem_extent.py) for an example
of loading an extent.  The shapefile that represents the DEM extent needs to be created separately.

## Contributing

Please read and follow our [Code of Conduct](./CODE_OF_CONDUCT.md).
