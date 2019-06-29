import Vue from 'vue';
import Vuex from 'vuex';
import { Feature, Point, FeatureCollection } from 'geojson';
import L from 'leaflet'

import {
    FETCH_WELL_LOCATIONS,
    FETCH_DATA_SOURCES,
    FETCH_MAP_OBJECTS,
    CLEAR_MAP_SELECTIONS,
    SELECT_SINGLE_MAP_OBJECT
} from './actions.types'

import {
    SET_SEARCH_BOUNDS,
    SET_SEARCH_PARAMS,
    SET_LOCATION_SEARCH_RESULTS,
    SET_DATA_SOURCES,
    SET_MAP_LAYER_STATE,
    SET_MAP_OBJECT_SELECTIONS,
    SET_SINGLE_MAP_OBJECT_SELECTION,
    SET_MAP_SELECTION_OBJECTS_EMPTY
} from './mutations.types'

// @ts-ignore
import ApiService from '../../services/ApiService'
import { IDataSource } from '@/interfaces';

const cleanParams = (payload: { [s: string]: unknown; } | ArrayLike<unknown>) => {
    // Clear any null or empty string values, to keep URLs clean.
    return Object.entries(payload).filter(([key, value]) => {
        return !(value === undefined || value === '' || value === null)
    }).reduce((cleanedParams, [key, value]) => {
        // @ts-ignore
        cleanedParams[key] = value
        return cleanedParams
    }, {})
}

// Layer Names
const WMS_WATER_RIGHTS_LICENSES = 'WHSE_WATER_MANAGEMENT.SSL_SNOW_ASWS_STNS_SP'
// const WMS_ARTESIAN = 'WHSE_WATER_MANAGEMENT.GW_WATER_WELLS_WRBC_SVW'
const WMS_CADASTRAL = 'WHSE_CADASTRE.PMBC_PARCEL_FABRIC_POLY_SVW'
const WMS_ECOCAT = 'WHSE_FISH.ACAT_REPORT_POINT_PUB_SVW'
const WMS_GWLIC = 'WHSE_WATER_MANAGEMENT.WLS_PWD_LICENCES_SVW'
// const WMS_OBS_ACTIVE = 'WHSE_WATER_MANAGEMENT.GW_WATER_WELLS_WRBC_SVW'
// const WMS_OBS_INACTIVE = 'WHSE_WATER_MANAGEMENT.GW_WATER_WELLS_WRBC_SVW'
const WMS_WELLS = 'WHSE_WATER_MANAGEMENT.GW_WATER_WELLS_WRBC_SVW'
const DATA_CAN_CLIMATE_NORMALS_1980_2010 = 'DATA_CAN_CLIMATE_NORMALS_1980_2010'

// temporary hardcoded list of map layers
const DEMO_MAP_LAYERS = [
    // {
    //     id: WMS_ARTESIAN,
    //     name: 'Artesian wells',
    //     uri: '',
    //     geojson: ''
    // },
    {
        id: WMS_CADASTRAL,
        name: 'Cadastral',
        uri: '',
        geojson: ''
    },
    {
        id: WMS_ECOCAT,
        name: 'Ecocat - Water related reports',
        uri: '',
        geojson: ''
    },
    {
        id: WMS_GWLIC,
        name: 'Groundwater licences',
        uri: '',
        geojson: ''
    },
    // {
    //     id: WMS_OBS_ACTIVE,
    //     name: 'Observation wells - active',
    //     uri: '',
    //     geojson: ''
    // },
    // {
    //     id: WMS_OBS_INACTIVE,
    //     name: 'Observation wells - inactive',
    //     uri: '',
    //     geojson: ''
    // },
    {
        id: WMS_WELLS,
        name: 'Wells - All',
        uri: '',
        geojson: ''
    }
]

const DEMO_DATA_LAYERS = [
    {
        id: DATA_CAN_CLIMATE_NORMALS_1980_2010,
        name: 'Canadian Climate Normals 1980-2010',
        uri: '',
        geojson: ''
    }
]

// @ts-ignore
export default {
    state: {
        searchBounds: {},
        searchParams: {},
        // lastSearchTrigger: null,
        locationSearchResults: [],
        pendingSearch: null,
        searchResultFilters: {},
        pendingLocationSearch: null,
        externalDataSources: { features: [] },
        dataLayers: [
            {
                id: DATA_CAN_CLIMATE_NORMALS_1980_2010,
                name: 'Canadian Climate Normals 1980-2010',
                uri: '',
                geojson: ''
            }
        ],
        mapLayers: [
            // {
            //     id: WMS_ARTESIAN,
            //     name: 'Artesian wells',
            //     uri: '',
            //     geojson: ''
            // },
            {
                id: WMS_CADASTRAL,
                name: 'Cadastral',
                uri: '',
                geojson: ''
            },
            {
                id: WMS_ECOCAT,
                name: 'Ecocat - Water related reports',
                uri: '',
                geojson: ''
            },
            {
                id: WMS_GWLIC,
                name: 'Groundwater licences',
                uri: '',
                geojson: ''
            },
            // {
            //     id: WMS_OBS_ACTIVE,
            //     name: 'Observation wells - active',
            //     uri: '',
            //     geojson: ''
            // },
            // {
            //     id: WMS_OBS_INACTIVE,
            //     name: 'Observation wells - inactive',
            //     uri: '',
            //     geojson: ''
            // },
            {
                id: WMS_WELLS,
                name: 'Wells - All',
                uri: '',
                geojson: ''
            }
        ],
        activeMapLayers: {
            [WMS_WATER_RIGHTS_LICENSES]: true,
            // [WMS_ARTESIAN]: false,
            [WMS_CADASTRAL]: false,
            [WMS_ECOCAT]: false,
            [WMS_GWLIC]: false,
            // [WMS_OBS_ACTIVE]: false,
            // [WMS_OBS_INACTIVE]: false,
            [WMS_WELLS]: false,
            [DATA_CAN_CLIMATE_NORMALS_1980_2010]: false
        },
        mapLayerSelections: {
            // [WMS_ARTESIAN]: [],
            [WMS_CADASTRAL]: [],
            [WMS_ECOCAT]: [],
            [WMS_GWLIC]: [],
            // [WMS_OBS_ACTIVE]: [],
            // [WMS_OBS_INACTIVE]: [],
            [WMS_WELLS]: [],
            [DATA_CAN_CLIMATE_NORMALS_1980_2010]: [
                {
                    id: 'cb7d1bf2-66ec-4ff0-8e95-9af7b6a1de18',
                    name: 'Canadian Climate Normals 1981-2010 Station Data - N VANCOUVER WHARVES',
                    web_uri: 'http://climate.weather.gc.ca/climate_normals/results_1981_2010_e.html?searchType=stnProv&lstProvince=BC&txtCentralLatMin=0&txtCentralLatSec=0&txtCentralLongMin=0&txtCentralLongSec=0&stnID=833&dispBack=0',
                    coordinates: [-123.12, 49.31]
                }
            ]
        },
        mapLayerSingleSelection: {}
    },
    mutations: {
        [SET_SEARCH_BOUNDS] (state: { searchBounds: any; }, payload: any) {
            state.searchBounds = payload
        },
        [SET_SEARCH_PARAMS] (state: { searchParams: {}; }, payload: ArrayLike<unknown> | { [s: string]: unknown; }) {
            state.searchParams = cleanParams(payload)
        },
        [SET_LOCATION_SEARCH_RESULTS] (state: { locationSearchResults: any; }, payload: any) {
            state.locationSearchResults = payload
        },
        [SET_DATA_SOURCES] (state: { externalDataSources: any; }, payload: any) {
            state.externalDataSources = payload
        },
        [SET_MAP_LAYER_STATE] (state: { activeMapLayers: any; }, payload: { name: string, status: boolean }) {
            state.activeMapLayers[payload.name] = payload.status
        },
        [SET_SINGLE_MAP_OBJECT_SELECTION] (state: { mapLayerSingleSelection: any; }, payload: any) {
            state.mapLayerSingleSelection = payload;
        },
        [SET_MAP_OBJECT_SELECTIONS] (state: { mapLayerSelections: any; }, payload: any) {
            state.mapLayerSelections = payload;
        },
        [SET_MAP_SELECTION_OBJECTS_EMPTY] (state: {mapLayerSelections: any}, payload: any){
            state.mapLayerSelections = []
        }
    },
    actions: {
        // @ts-ignore
        [SELECT_SINGLE_MAP_OBJECT] ({commit}, content) {
            commit(SET_SINGLE_MAP_OBJECT_SELECTION, content)
        },
        // @ts-ignore
        [CLEAR_MAP_SELECTIONS] ({commit}) {
            commit(SET_MAP_SELECTION_OBJECTS_EMPTY)
        },
        // @ts-ignore
        [FETCH_MAP_OBJECTS] ({commit}, payload) {
            let params = {
                request: 'GetMap',
                service: 'WMS',
                srs: 'EPSG:4326',
                version: '1.1.1',
                format: 'application/json;type=topojson',
                bbox: payload.bounds,
                height: payload.size.y,
                width: payload.size.x,
                layers: payload.layer
            };
            ApiService.getRaw("https://openmaps.gov.bc.ca/geo/pub/" + payload.layer + "/ows" + L.Util.getParamString(params))
                .then((response: { data: { objects: { [x: string]: { geometries: any; }; }; }; }) => {
                    console.log(response.data)
                    let points = response.data.objects[params.layers].geometries
                    console.log(points)
                    commit(SET_MAP_OBJECT_SELECTIONS, {[payload.layer]: points})
                }).catch((error: any) => {
                    console.log(error)
                })
        },

        // @ts-ignore
        [FETCH_WELL_LOCATIONS] ({ commit }) {
            return new Promise((resolve, reject) => {
                ApiService.getRaw("https://gwells-staging.pathfinder.gov.bc.ca/gwells/api/v1/locations")
                .then((response: { data: any; }) => {
                    commit(SET_LOCATION_SEARCH_RESULTS, response.data)
                }).catch((error: any) => {
                    reject(error)
                })
            })
        },
        // @ts-ignore
        [FETCH_DATA_SOURCES] ({ commit }) {

            const demoData: Array<IDataSource> = [
                {
                    id: 'cb7d1bf2-66ec-4ff0-8e95-9af7b6a1de18',
                    name: 'Canadian Climate Normals 1981-2010 Station Data - N VANCOUVER WHARVES',
                    web_uri: 'http://climate.weather.gc.ca/climate_normals/results_1981_2010_e.html?searchType=stnProv&lstProvince=BC&txtCentralLatMin=0&txtCentralLatSec=0&txtCentralLongMin=0&txtCentralLongSec=0&stnID=833&dispBack=0',
                    coordinates: [-123.12, 49.31]
                }
            ]

            const demoDataGeoJSON: FeatureCollection = {
                type: 'FeatureCollection',
                features: [
                    {
                        id: 'cb7d1bf2-66ec-4ff0-8e95-9af7b6a1de18',
                        type: 'Feature',
                        geometry: {
                            type: 'Point',
                            coordinates: [-123.12, 49.31]
                        },
                        properties: {
                            name: 'Canadian Climate Normals 1981-2010 Station Data - N VANCOUVER WHARVES',
                            web_uri: 'http://climate.weather.gc.ca/climate_normals/results_1981_2010_e.html?searchType=stnProv&lstProvince=BC&txtCentralLatMin=0&txtCentralLatSec=0&txtCentralLongMin=0&txtCentralLongSec=0&stnID=833&dispBack=0',
                        }
                    }
                ]
            }

            return new Promise((resolve, reject) => {
                commit(SET_DATA_SOURCES, demoDataGeoJSON)
            })
        }
    },
    getters: {
        // lastSearchTrigger (state) {
        //     return state.lastSearchTrigger
        // },
        // pendingSearch (state) {
        //     return state.pendingSearch
        // },
        // searchParams (state) {
        //     return state.searchParams
        // },
        // searchResultFilters (state) {
        //     return state.searchResultFilters
        // },
        locationSearchResults (state: { locationSearchResults: any; }) {
            return state.locationSearchResults
        },
        // pendingLocationSearch (state) {
        //     return state.pendingLocationSearch
        // },
        externalDataSources (state: { externalDataSources: any; }) {
            return state.externalDataSources
        },
        activeMapLayers (state: { activeMapLayers: any; }) {
            return state.activeMapLayers
        },
        mapLayerSelections (state: { mapLayerSelections: any; }) {
            return state.mapLayerSelections
        },
        mapLayers (state: { mapLayers: any; }) {
            return state.mapLayers
        },
        dataLayers (state: { dataLayers: any; }) {
            return state.dataLayers
        },
    }
}
