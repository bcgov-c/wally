import MapLegend from './MapLegend.vue'
import EventBus from '../../services/EventBus.js'
import { mapGetters, mapActions } from 'vuex'
import { wmsBaseURL } from '../../utils/wmsUtils'
import mapboxgl from 'mapbox-gl'
import MapboxDraw from '@mapbox/mapbox-gl-draw'
import MapboxGeocoder from '@mapbox/mapbox-gl-geocoder'
import HighlightPoint from './MapHighlightPoint'
import MapScale from './MapScale'
import circle from '@turf/circle'
import * as metadata from '../../utils/metadataUtils'
import coordinatesGeocoder from './localGeocoder'
import bbox from '@turf/bbox'
import _ from 'lodash';

import qs from 'querystring'
import ApiService from '../../services/ApiService'

const point = {
  'type': 'Feature',
  'geometry': {
    'type': 'Point',
    'coordinates': [[]]
  }
}
const polygon = {
  'type': 'Feature',
  'geometry': {
    'type': 'Polygon',
    'coordinates': [[]]
  }
}
const featureCollection = {
  "type": "FeatureCollection",
  "features": []
}

export default {
  name: 'Map',
  components: { MapLegend },
  mounted () {
    this.initMap()
    EventBus.$on('layer:added', this.handleAddLayer)
    EventBus.$on('layer:removed', this.handleRemoveLayer)
    EventBus.$on('baseLayer:added', this.handleAddBaseLayer)
    EventBus.$on('baseLayer:removed', this.handleRemoveBaseLayer)
    EventBus.$on('dataMart:added', this.handleAddApiLayer)
    EventBus.$on('dataMart:removed', this.handleRemoveApiLayer)
    EventBus.$on('feature:added', this.handleAddFeature)
    EventBus.$on('layers:loaded', this.loadLayers)
    EventBus.$on('draw:reset', this.replaceOldFeatures)
    EventBus.$on('shapes:add', this.addShape)
    EventBus.$on('shapes:reset', this.removeShapes)
    EventBus.$on('draw:redraw', (opts) => this.handleSelect(this.draw.getAll(), opts))
    EventBus.$on('highlight:clear', this.clearHighlightLayer)

    // this.$store.dispatch(FETCH_DATA_LAYERS)
  },
  beforeDestroy () {
    EventBus.$off('layer:added', this.handleAddLayer)
    EventBus.$off('layer:removed', this.handleRemoveLayer)
    EventBus.$off('baseLayer:added', this.handleAddBaseLayer)
    EventBus.$off('baseLayer:removed', this.handleRemoveBaseLayer)
    EventBus.$off('dataMart:added', this.handleAddApiLayer)
    EventBus.$off('dataMart:removed', this.handleRemoveApiLayer)
    EventBus.$off('feature:added', this.handleAddFeature)
    EventBus.$off('layers:loaded', this.loadLayers)
    EventBus.$off('draw:reset', this.replaceOldFeatures)
    EventBus.$off('shapes:add', this.addShape)
    EventBus.$off('shapes:reset', this.removeShapes)
    EventBus.$off('draw:redraw', () => this.handleSelect(this.draw.getAll()))
    EventBus.$off('highlight:clear', this.clearHighlightLayer)
  },
  data () {
    return {
      map: null,
      // legendControlContent: null,
      // activeLayerGroup: L.layerGroup(),
      // markerLayerGroup: L.layerGroup(),
      activeLayers: {},
      draw: null, // mapbox draw object (controls drawn polygons e.g. for area select)
      isDrawingToolActive: false
    }
  },
  computed: {
    ...mapGetters([
      'allMapLayers',
      'activeMapLayers',
      'allDataMarts',
      'activeDataMarts',
      'highlightFeatureData',
      'dataMartFeatureInfo',
      'infoPanelVisible'
    ])
  },
  methods: {
    async initMap () {
      // temporary public token with limited scope (reading layers) just for testing.

      const mapConfig = await ApiService.get('api/v1/map-config')
      mapboxgl.accessToken = mapConfig.data.mapbox_token

      const zoomConfig = {
        center: process.env.VUE_APP_MAP_CENTER ? JSON.parse(process.env.VUE_APP_MAP_CENTER) : [-124, 54.5],
        zoomLevel: process.env.VUE_APP_MAP_ZOOM_LEVEL ? process.env.VUE_APP_MAP_ZOOM_LEVEL : 4.7
      }

      this.map = new mapboxgl.Map({
        container: 'map', // container id
        style: mapConfig.data.mapbox_style, // dev or prod map style
        center: zoomConfig.center, // starting position
        zoom: zoomConfig.zoomLevel, // starting zoom
        attributionControl: false // hide default and re-add to the top left
      })

      const modes = MapboxDraw.modes
      modes.simple_select.onTrash = this.clearSelections
      modes.draw_polygon.onTrash = this.clearSelections
      modes.draw_point.onTrash = this.clearSelections
      modes.direct_select.onTrash = this.clearSelections

      this.draw = new MapboxDraw({
        modes: modes,
        displayControlsDefault: false,
        controls: {
          polygon: true,
          point: true,
          trash: true
        }
      })

      const geocoder = new MapboxGeocoder({
        accessToken: mapboxgl.accessToken,
        mapboxgl: this.map,
        origin: ApiService.baseURL,
        marker: false,
        localGeocoder: coordinatesGeocoder,
        container: 'geocoder-container',
        minLength: 1
      })
      geocoder.on('result', this.updateBySearchResult)

      // Add zoom and rotation controls to the map.
      if (!document.getElementById('geocoder').hasChildNodes()) {
        document.getElementById('geocoder')
          .appendChild(geocoder.onAdd(this.map))
      }

      this.map.addControl(new mapboxgl.NavigationControl(), 'top-right')
      this.map.addControl(this.draw, 'top-right')
      this.map.addControl(new mapboxgl.ScaleControl(), 'bottom-right')
      this.map.addControl(new mapboxgl.ScaleControl({ unit: 'imperial' }), 'bottom-right')
      this.map.addControl(new mapboxgl.AttributionControl(), 'top-left')
      this.map.addControl(new mapboxgl.GeolocateControl({
        positionOptions: {
          enableHighAccuracy: true
        },
        showUserLocation: false
      }), 'top-right')
      this.map.on('style.load', () => {
        this.getMapLayers()
        this.initStreamHighlights()
      })

      this.initHighlightLayers()
      this.listenForAreaSelect()

      // special handling for parcels because we may not want to have
      // users turn this layer on/off (it should always be on)
      this.map.on('click', this.setSingleFeature)
      // this.map.on('click', 'parcels', this.setSingleFeature)
      this.map.on('mouseenter', 'parcels', this.setCursorPointer)
      this.map.on('mouseleave', 'parcels', this.resetCursor)

      // Subscribe to mode change event to toggle drawing state
      this.map.on('draw.modechange', this.handleModeChange)
    },
    addShape (shape) {
      // adds a mapbox-gl-draw shape to the map
      this.map.getSource('customShapeData').setData(shape)
    },
    removeShapes () {
      this.map.getSource('customShapeData').setData(polygon)
    },
    clearSelections () {
      this.replaceOldFeatures()
      this.$store.commit('clearDataMartFeatures')
      this.$store.commit('clearDisplayTemplates')

      if (this.dataMartFeatureInfo && this.dataMartFeatureInfo.display_data_name === 'user_defined_point') {
        this.$store.commit('resetDataMartFeatureInfo')
        EventBus.$emit('highlight:clear')
      }
    },
    handleModeChange (e) {
      if (e.mode === 'draw_polygon') {
        this.isDrawingToolActive = true
        this.polygonToolHelp()
      } else if (e.mode === 'simple_select') {
        setTimeout(() => {
          this.isDrawingToolActive = false
        }, 500)
      }
    },
    initHighlightLayers () {
      this.map.on('load', () => {
        // initialize highlight layer
        this.map.addSource('customShapeData', { type: 'geojson', data: polygon })
        this.map.addLayer({
          'id': 'customShape',
          'type': 'fill',
          'source': 'customShapeData',
          'layout': {},
          'paint': {
            'fill-color': 'rgba(26, 193, 244, 0.08)',
            'fill-outline-color': 'rgb(8, 159, 205)'
          }
        })
        this.map.addSource('highlightLayerData', { type: 'geojson', data: polygon })
        this.map.addLayer({
          'id': 'highlightLayer',
          'type': 'fill',
          'source': 'highlightLayerData',
          'layout': {},
          'paint': {
            'fill-color': 'rgba(154, 63, 202, 0.25)'
          }
        })
        this.map.addImage('highlight-point', HighlightPoint(this.map, 90), { pixelRatio: 2 })
        this.map.addSource('highlightPointData', { type: 'geojson', data: point })
        this.map.addLayer({
          'id': 'highlightPoint',
          'type': 'symbol',
          'source': 'highlightPointData',
          'layout': {
            'icon-image': 'highlight-point'
          }
        })
      })
    },
    initStreamHighlights() {
      // This highlights the selected stream
      this.map.addSource('selectedStreamSource', { type: 'geojson', data: featureCollection })
      this.map.addLayer({
          "id": "selectedstream",
          "type": "line",
          "source": "selectedStreamSource",
          "layout": {
            "line-join": "round",
            "line-cap": "round"
          },
          "paint": {
              "line-color": "#1500ff",
              "line-width": 3
          }
      })
      // This layer highlights all upstream stream segments
      this.map.addSource('upStreamSource', { type: 'geojson', data: featureCollection })
      this.map.addLayer({
          "id": "upstream",
          "type": "line",
          "source": "upStreamSource",
          "layout": {
            "line-join": "round",
            "line-cap": "round"
          },
          "paint": {
              "line-color": "#00ff26",
              "line-width": 3
          }
      })
      // This layer highlights all downstream stream segments
      this.map.addSource('downStreamSource', { type: 'geojson', data: featureCollection }) 
      this.map.addLayer({
          "id": "downstream",
          "type": "line",
          "source": "downStreamSource",
          "layout": {
            "line-join": "round",
            "line-cap": "round"
          },
          "paint": {
              "line-color": "#ff4800",
              "line-width": 3
          }
      })
    },
    updateStreamHighlight(stream) {
        // Get slected watershed code and trim un-needed depth
        const watershedCode = stream.properties["FWA_WATERSHED_CODE"].replace(/-000000/g,'')

        // Build our downstream code list
        const codes = watershedCode.split("-")
        var downstreamCodes = [codes[0]]
        for (let i = 0; i < codes.length - 1; i++) {
          downstreamCodes.push(downstreamCodes[i] + "-" + codes[i+1])
        }
      
        // get all visible streams from fwa steams layer
        var streams = this.map.queryRenderedFeatures({ layers: ['freshwater_atlas_stream_networks'] })

        // loop streams to find matching cases for selected, upstream, and downstream conditions
        let selectedFeatures = []
        let upstreamFeatures = []
        let downstreamFeatures = []
        streams.forEach(stream => {
          const code = stream.properties["FWA_WATERSHED_CODE"].replace(/-000000/g,'') // remove empty stream ids
          if(code === watershedCode)  { selectedFeatures.push(stream) } // selected stream condition
          if(code.includes(watershedCode) && code.length > watershedCode.length)  { upstreamFeatures.push(stream) } // up stream condition
          if(downstreamCodes.indexOf(code) > -1 && code.length < watershedCode.length)  { downstreamFeatures.push(stream) } // down stream condition
        })

        // Clean out downstream features that are upwards water flow
        // TODO may want to toggle this based on user feedback
        let cleanedDownstreamFeatures = this.cleanDownStreams(downstreamFeatures, stream.properties["FWA_WATERSHED_CODE"])

        // Insert the upstream data into the upstream data source
        var upStreamCollection = Object.assign({}, featureCollection)
        upStreamCollection["features"] = upstreamFeatures
        this.map.getSource('upStreamSource').setData(upStreamCollection)

        // Insert the selected stream data into the selected stream data source
        var selectedStreamCollection = Object.assign({}, featureCollection)
        selectedStreamCollection["features"] = selectedFeatures
        this.map.getSource('selectedStreamSource').setData(selectedStreamCollection)

        // Insert the downstream data into the downstream data source
        var downStreamCollection = Object.assign({}, featureCollection) 
        downStreamCollection["features"] = cleanedDownstreamFeatures
        this.map.getSource('downStreamSource').setData(downStreamCollection)
    },
    cleanDownStreams(streams, code, builder = []) {
      // This is a recursive function that walks down the stream network
      // from the selected stream segment location. It removes any stream
      // segments that are at the same order but have an upwards stream flow.
      // Returns an array (builder) of cleaned stream segment features.
      var segment = streams.find((s) => {
        if(s.properties["LOCAL_WATERSHED_CODE"]) {
          let local = s.properties["LOCAL_WATERSHED_CODE"]
          let global = s.properties["FWA_WATERSHED_CODE"]
          if(local === code && global !== local) {
            return s
          }
        }
      })
      if(segment) {
        let drm = segment.properties["DOWNSTREAM_ROUTE_MEASURE"]
        let segmentCode = segment.properties["FWA_WATERSHED_CODE"]
        let elements = streams.filter((f) => { 
          if(f.properties["FWA_WATERSHED_CODE"] === segmentCode && 
             f.properties["DOWNSTREAM_ROUTE_MEASURE"] < drm){
              return f
            }
        })
        builder = builder.concat(elements)
        return this.cleanDownStreams(streams, segmentCode, builder)
      } else {
        return builder
      }
    },
    polygonToolHelp () {
      const disableKey = 'disablePolygonToolHelp'
      if (JSON.parse(localStorage.getItem(disableKey)) !== true) {
        EventBus.$emit(
          'help',
          {
            text: 'Draw a polygon by single clicking a series of points. Finish drawing by clicking again on any of the points, or cancel by pressing Escape. The polygon can be cleared by pressing Delete or clicking the trash button.',
            disableKey: disableKey
          })
      }
    },
    loadLayers () {
      const layers = this.allMapLayers

      // load each layer, but default to no visibility.
      // the user can toggle layers on and off with the layer controls.
      for (let i = 0; i < layers.length; i++) {
        const layer = layers[i]

        // All layers are now vector based sourced from mapbox
        // so we don't need to check for layer type anymore
        const vector = layer['display_data_name']
        // this.map.on('click', vector, this.setSingleFeature)
        this.map.on('mouseenter', vector, this.setCursorPointer)
        this.map.on('mouseleave', vector, this.resetCursor)
      }
    },
    updateBySearchResult (data) {
      let lat = data.result.center[1]
      let lng = -Math.abs(data.result.center[0])
      const options = { steps: 10, units: 'kilometers', properties: {} }
      const bounds = circle([lng, lat], 0.01, options) // 10m radius (in km)
      const canvas = this.map.getCanvas()
      const size = { x: canvas.width, y: canvas.height }
      let payload = {
        layers: [{ display_data_name: data.result.layer }],
        bounds: bounds,
        size: size,
        primary_key_match: data.result.primary_id
      }
      // Our search db view trims the pks on gwells queries
      // so here we add the 00s back for feature requests
      if (data.result.layer === 'groundwater_wells') {
        payload.primary_key_match = payload.primary_key_match.padStart(12, '0')
      } else if (data.result.layer === 'aquifers') {
        payload.primary_key_match = payload.primary_key_match.padStart(4, '0')
      }

      this.clearHighlightLayer()
      this.updateHighlightLayerData(data.result)

      if (data.result.place_type === 'coordinate') {
        return
      }

      this.$store.commit('clearDataMartFeatures')
      this.$store.commit('addMapLayer', data.result.layer)
      this.$store.dispatch('getDataMartFeatures', payload)
    },
    updateHighlightLayerData (data) {
      // For stream networks layer we add custom highlighting and reset poly/point highlight layering
      if(data.display_data_name === 'freshwater_atlas_stream_networks') {
        this.map.getSource('highlightPointData').setData(point)
        this.map.getSource('highlightLayerData').setData(polygon)
        this.updateStreamHighlight(data)
      } else if (data.geometry.type === 'Point') { // Normal poly/point highlighting
        this.map.getSource('highlightPointData').setData(data)
        this.map.getSource('highlightLayerData').setData(polygon)
        this.clearStreamHighlightLayers()
      } else {
        this.map.getSource('highlightPointData').setData(point)
        this.map.getSource('highlightLayerData').setData(data)
        this.clearStreamHighlightLayers()
      }
    },
    clearHighlightLayer () {
      this.map.getSource('highlightPointData').setData(point)
      this.map.getSource('highlightLayerData').setData(polygon)
      this.clearStreamHighlightLayers()
    },
    clearStreamHighlightLayers() {
      this.map.getSource('selectedStreamSource').setData(featureCollection)
      this.map.getSource('downStreamSource').setData(featureCollection)
      this.map.getSource('upStreamSource').setData(featureCollection)
    },
    handleAddLayer (displayDataName) {
      this.map.setLayoutProperty(displayDataName, 'visibility', 'visible')
    },
    handleRemoveLayer (displayDataName) {
      this.clearHighlightLayer()
      this.map.setLayoutProperty(displayDataName, 'visibility', 'none')
    },
    handleAddBaseLayer (layerId) {
      this.map.setLayoutProperty(layerId, 'visibility', 'visible')
    },
    handleRemoveBaseLayer (layerId) {
      this.map.setLayoutProperty(layerId, 'visibility', 'none')
    },
    handleAddApiLayer (datamart) {
      const layer = this.activeDataMarts.find((x) => {
        return x.display_data_name === datamart.displayDataName
      })
      this.addGeoJSONLayer(layer)
    },
    handleRemoveApiLayer (displayDataName) {
      this.removeLayer(displayDataName)
    },
    addGeoJSONLayer (layer) {
      if (!layer || !layer.data) {
        console.error('invalid format for data source/data mart')
        return
      }

      // layer.data should have a "features" or "geojson" property, which
      // must be a list of geojson Features.  For example, layer.data could be
      // a FeatureCollection format object. The 'features' list will be added to the map.
      let features
      if (layer.data.features && layer.data.features.length) {
        features = layer.data.features
      } else if (layer.data.geojson && layer.data.geojson.length) {
        features = layer.data.geojson
      }
      if (!features) {
        console.error('could not find a features list or object to add to map')
        return
      }

      // this.activeLayers[layer.display_data_name] = L.geoJSON(features, {
      //   onEachFeature: function (feature, layer) {
      //     layer.bindPopup('<h3>' + feature.properties.name + '</h3><p>' + feature.properties.description + '</p>')
      //   }
      // })
      this.activeLayers[layer.display_data_name].addTo(this.map)
    },
    addWMSLayer (layer) {
      const layerID = layer.display_data_name || layer.wms_name || layer.display_name
      if (!layerID) {
        return
      }

      const wmsOpts = {
        service: 'WMS',
        request: 'GetMap',
        format: 'image/png',
        layers: 'pub:' + layer.wms_name,
        styles: layer.wms_style,
        transparent: true,
        name: layer.name,
        height: 256,
        width: 256,
        overlay: true,
        srs: 'EPSG:3857'
      }

      const query = qs.stringify(wmsOpts)
      const url = wmsBaseURL + layer.wms_name + '/ows?' + query + '&BBOX={bbox-epsg-3857}'

      const newLayer = {
        'id': layerID,
        'type': 'raster',
        'layout': {
          'visibility': 'none'
        },
        'source': {
          'type': 'raster',
          'tiles': [
            url
          ],
          'tileSize': 256
        }
      }

      this.map.addLayer(newLayer, 'groundwater_wells')
    },
    removeLayer (layer) {
      const displayDataName = layer.display_data_name || layer
      if (!displayDataName || !this.activeLayers[displayDataName]) {
        return
      }
      this.map.removeLayer(layer.id)
      // delete this.legendGraphics[layer.id]
      delete this.activeLayers[layer.id]
    },
    replaceOldFeatures (newFeature = null) {
      // replace all previously drawn features with the new one.
      // this has the effect of only allowing one selection box to be drawn at a time.
      const old = this.draw.getAll().features.filter((f) => f.id !== newFeature)
      this.draw.delete(old.map((feature) => feature.id))
    },
    handleAddPointSelection (feature) {
      feature.display_data_name = 'user_defined_point'
      this.$store.commit('setDataMartFeatureInfo', feature)
    },
    handleSelect (feature, options) {
      // default options when calling this handler.
      //
      // showFeatureList: whether features selected by the user should be immediately shown in
      // a panel.  This might be false if the user is selecting layers and may want to select
      // several before being "bumped" to the selected features list.
      //
      // example: EventBus.$emit('draw:redraw', { showFeatureList: false })
      const defaultOptions = {
        showFeatureList: true
      }

      options = Object.assign({}, defaultOptions, options)

      if (!feature || !feature.features || !feature.features.length) return

      console.log(options.showFeatureList)

      if (options.showFeatureList) {
        this.$store.commit('setLayerSelectionActiveState', false)
      }

      const newFeature = feature.features[0]
      this.replaceOldFeatures(newFeature.id)

      if (newFeature.geometry.type === 'Point') {
        return this.handleAddPointSelection(newFeature)
      }
      // for drawn rectangular regions, the polygon describing the rectangle is the first
      // element in the array of drawn features.
      // note: this is what might break if extending the selection tools to draw more objects.
      this.getMapObjects(newFeature)
      this.$store.commit('setSelectionBoundingBox', newFeature)
    },
    listenForAreaSelect () {
      this.map.on('draw.create', this.handleSelect)
      this.map.on('draw.update', this.handleSelect)
    },
    getMapObjects (bounds) {
      // TODO: Separate activeMaplayers by activeWMSLayers and activeDataMartLayers
      const canvas = this.map.getCanvas()
      const size = { x: canvas.width, y: canvas.height }

      this.$store.commit('clearDataMartFeatures')
      this.$store.dispatch('getDataMartFeatures', { bounds: bounds, size: size, layers: this.activeMapLayers })
    },
    setSingleFeature (e) {
      if (!this.isDrawingToolActive) {
        const loc = e.lnglat
        const scale = MapScale(this.map)
        const radius = scale / 1000 * 0.065 // scale radius based on map zoom level
        const options = { steps: 10, units: 'kilometers', properties: {} }
        const bounds = circle([e.lngLat['lng'], e.lngLat['lat']], radius, options)
        // this.map.getSource('highlightLayerData').setData(bounds) // debug can see search radius
        this.getMapObjects(bounds)
      }
    },
    getPolygonCenter (arr) {
      if (arr.length === 1) { return arr }
      var x = arr.map(x => x[0])
      var y = arr.map(x => x[1])
      var cx = (Math.min(...x) + Math.max(...x)) / 2
      var cy = (Math.min(...y) + Math.max(...y)) / 2
      return [cx, cy]
    },
    getArrayDepth (value) {
      return Array.isArray(value) ? 1 + Math.max(...value.map(this.getArrayDepth)) : 0
    },
    formatLatLon (lon, lat) {
      // Formats lat lon to be within proper ranges
      lon = lon < 0 ? lon : -lon
      lat = lat > 0 ? lat : -lat
      return [lon, lat]
    },
    setCursorPointer () {
      this.map.getCanvas().style.cursor = 'pointer'
    },
    resetCursor () {
      this.map.getCanvas().style.cursor = ''
    },
    ...mapActions(['getMapLayers'])
  },
  watch: {
    highlightFeatureData (value) {
      if (value && value.geometry) {
        if (value.geometry.type === 'Point') {
          let coordinates = value.geometry.coordinates
          value.geometry.coordinates = this.formatLatLon(coordinates[0], coordinates[1])
        }
        this.updateHighlightLayerData(value)
      }
    },
    dataMartFeatureInfo (value) {
      if (value && value.geometry) {
        let coordinates = value.geometry.coordinates
        if (value.geometry.type === 'Point') {
          coordinates = this.formatLatLon(coordinates[0], coordinates[1])
          value.geometry.coordinates = coordinates
        } else {
          let depth = this.getArrayDepth(coordinates)
          let flattened = coordinates.flat(depth - 2)
          coordinates = this.getPolygonCenter(flattened)
        }

        // Offset the selected point to show up a little to the right
        // So that the InfoSheet / floating panel doesn't cover it
        // TODO: Refactor this into clean & reusable code
        let flyToCoordinates = [...coordinates]
        if (this.infoPanelVisible) {
          flyToCoordinates[0] = flyToCoordinates[0] - 0.04
        }
        this.map.flyTo({
          center: flyToCoordinates
        })
        this.updateHighlightLayerData(value)
      }
    },
    infoPanelVisible (value) {
      // TODO: Refactor this into clean & reusable code
      let coordinates = this.map.getCenter()
      let flyToCoordinates = [coordinates.lng, coordinates.lat]
      if (!value) {
        // Move the the left
        flyToCoordinates[0] = flyToCoordinates[0] + 0.04
      } else {
        // Move to the right
        flyToCoordinates[0] = flyToCoordinates[0] - 0.04
      }
      this.map.flyTo({
        center: flyToCoordinates
      })
    }
  }
}
