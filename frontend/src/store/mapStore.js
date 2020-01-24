// TODO: change to api call, or create new array just for map layers
import html2canvas from 'html2canvas'
import { saveAs } from 'file-saver'

import ApiService from '../services/ApiService'
import baseMapDescriptions from '../utils/baseMapDescriptions'
import HighlightPoint from '../components/map/MapHighlightPoint'

const emptyPoint = {
  'type': 'Feature',
  'geometry': {
    'type': 'Point',
    'coordinates': [[]]
  }
}
const emptyPolygon = {
  'type': 'Feature',
  'geometry': {
    'type': 'Polygon',
    'coordinates': [[]]
  }
}

export default {
  namespaced: true,
  state: {
    map: null,
    draw: {},
    geocoder: {},
    activeSelection: null,
    layerSelectTriggered: false,
    selectedMapLayerNames: [],
    activeMapLayers: [],
    mapLayers: [],
    highlightFeatureData: {},
    highlightFeatureCollectionData: {},
    layerCategories: [],
    layerSelectionActive: true,
    selectedBaseLayers: [
      'national-park',
      'landuse',
      'contour-line',
      'hillshade'
    ],
    baseMapLayers: [{
      id: 'base-map-layers',
      name: 'Base Map Layers',
      children: baseMapDescriptions
    }]
  },
  actions: {
    async addPointOfInterest ({ state, dispatch }, feature) {
      if (!state.map.loaded()) {
        return
      }

      state.draw.add(feature)
      dispatch('addActiveSelection', { features: [feature] })
    },
    addActiveSelection ({ commit, dispatch, state }, feature, options) {
      // default options when calling this handler.
      //
      // showFeatureList: whether features selected by the user should be immediately shown in
      // a panel.  This might be false if the user is selecting layers and may want to select
      // several before being "bumped" to the selected features list.
      //
      // example: this.addActiveSelection(feature, { showFeatureList: false })

      const defaultOptions = {
        showFeatureList: true
      }

      options = Object.assign({}, defaultOptions, options)

      if (!feature || !feature.features || !feature.features.length) return

      if (options.showFeatureList) {
        commit('setLayerSelectionActiveState', false)
      }

      const newFeature = feature.features[0]
      commit('replaceOldFeatures', newFeature.id)

      // Active selection is a Point
      if (newFeature.geometry.type === 'Point') {
        newFeature.display_data_name = 'point_of_interest'
        commit('setDataMartFeatureInfo', newFeature, { root: true })
        return
      }

      // Active selection is a LineString
      if (newFeature.geometry.type === 'LineString') {
        newFeature.display_data_name = 'user_defined_line'
        commit('setDataMartFeatureInfo', newFeature, { root: true })
        return
      }

      // for drawn rectangular regions, the polygon describing the rectangle is the first
      // element in the array of drawn features.
      // note: this is what might break if extending the selection tools to draw more objects.
      dispatch('getMapObjects', newFeature)
      commit('setSelectionBoundingBox', newFeature, { root: true })
    },
    clearActiveSelection ({ commit }) {
      commit('replaceOldFeatures', null)
    },
    getAllLayers () {

    },
    getLayerCategories () {

    },

    updateActiveMapLayers ({ commit, state, dispatch }, selectedLayers) {
      // accepts an array of layer names and sets the active map layers accordingly
      state.selectedMapLayerNames = selectedLayers

      // list of prev layers.  the payload is the new list of layers about to be active.
      const prev = state.activeMapLayers.map(l => l.display_data_name)

      // get list of layers that were deselected (they were in `prev`, but are not in payload),
      // and sent an event to remove them.
      prev.filter((l) => !selectedLayers.includes(l)).forEach((l) => dispatch('removeMapLayer', l))
      // prev.filter((l) => !selectedLayers.includes(l)).forEach((l) => EventBus.$emit(`layer:removed`, l))

      // similarly, now get a list of layers that are in payload but weren't in the previous active layers.
      selectedLayers.filter((l) => !prev.includes(l)).forEach((l) => commit('activateLayer', l))
      // selectedLayers.filter((l) => !prev.includes(l)).forEach((l) => EventBus.$emit(`layer:added`, l))

      // reset the list of active layers
      commit('setActiveMapLayers', selectedLayers)

      // redraw any current features and update selection.
      dispatch('addActiveSelection', state.draw.getAll(), { showFeatureList: false })
    },
    disableLayer () {

    },
    expandMapLegend () {},
    collapseMapLegend () {},
    addMapLayer ({ commit, dispatch, state }, displayDataName) {
      let mapLayer = state.mapLayers.find((layer) => {
        return layer.display_data_name === displayDataName
      })

      // mapLayer may be undefined if it wasn't found in the list of
      // map layers (for example, addMapLayer was called before the layer
      // catalogue loaded or was called with an unexpected layer).  If so,
      // stop here.
      if (!mapLayer) {
        return
      }

      if (!state.activeMapLayers.includes(mapLayer)) {
        state.activeMapLayers.push(mapLayer)
        commit('activateLayer', displayDataName)
      }
    },
    removeMapLayer ({ state, dispatch, commit }, payload) {
      state.activeMapLayers = state.activeMapLayers.filter((layer) => {
        return layer.display_data_name !== payload
      })
      dispatch('clearHighlightLayer')
      commit('deactivateLayer', payload)
      // EventBus.$emit(`layer:removed`, payload)
    },
    clearMapLayers () {},
    // getFeatures() <--datamartStore
    getMapLayers ({ commit, dispatch }) {
      // We only fetch maplayers if we don't have a copy cached
      if (this.state.mapLayers === undefined) {
        return new Promise((resolve, reject) => {
          console.log('Getting map layers')
          ApiService.getApi('/catalogue/all')
            .then((response) => {
              commit('setMapLayers', response.data.layers)
              commit('setLayerCategories', response.data.categories)
              // EventBus.$emit(`layers:loaded`)
              dispatch('loadLayers')
            })
            .catch((error) => {
              reject(error)
            })
        })
      }
    },
    async getMapObjects ({ commit, dispatch, state, getters }, bounds) {
      // TODO: Separate activeMaplayers by activeWMSLayers and activeDataMartLayers

      const canvas = await state.map.getCanvas()
      const size = { x: canvas.width, y: canvas.height }

      commit('clearDataMartFeatures', {}, { root: true })
      dispatch('getDataMartFeatures', {
        bounds: bounds,
        size: size,
        layers: state.activeMapLayers
      }, { root: true })
    },
    clearSelections ({ state, commit, dispatch }) {
      commit('replaceOldFeatures')
      commit('clearDataMartFeatures', {}, { root: true })
      commit('clearDisplayTemplates', {}, { root: true })
      dispatch('removeElementsByClass', 'annotationMarker')
      commit('removeShapes')

      // if (this.dataMartFeatureInfo && this.dataMartFeatureInfo.display_data_name === 'point_of_interest') {
      commit('resetDataMartFeatureInfo', {}, { root: true })
      dispatch('clearHighlightLayer')
      // EventBus.$emit('highlight:clear')
      // }
    },
    clearHighlightLayer ({ commit, state, dispatch }) {
      state.map.getSource('highlightPointData').setData(emptyPoint)
      state.map.getSource('highlightLayerData').setData(emptyPolygon)
      commit('updateHighlightFeatureCollectionData', {})
      commit('resetStreamData', {}, { root: true })
      commit('resetStreamBufferData', {}, { root: true })
      dispatch('removeElementsByClass', 'annotationMarker')
    },
    clearStreamHighlights ({ commit, state }) {

    },
    setActiveBaseMapLayers ({ state, commit }, payload) {
      let prev = state.selectedBaseLayers
      // prev.filter((l) => !payload.includes(l)).forEach((l) => EventBus.$emit(`baseLayer:removed`, l))
      prev.filter((l) => !payload.includes(l)).forEach((l) => commit('deactivateBaseLayer', l))
      // payload.filter((l) => !prev.includes(l)).forEach((l) => EventBus.$emit(`baseLayer:added`, l))
      payload.filter((l) => !prev.includes(l)).forEach((l) => commit('activateBaseLayer', l))
      state.selectedBaseLayers = payload
    },
    loadLayers ({ state, commit }) {
      const layers = state.mapLayers

      // load each layer, but default to no visibility.
      // the user can toggle layers on and off with the layer controls.
      for (let i = 0; i < layers.length; i++) {
        const layer = layers[i]

        // All layers are now vector based sourced from mapbox
        // so we don't need to check for layer type anymore
        const vector = layer['display_data_name']
        // state.map.on('click', vector, this.setSingleFeature)
        state.map.on('mouseenter', vector, commit('setCursorPointer'))
        state.map.on('mouseleave', vector, commit('resetCursor'))
      }
    },
    initStreamHighlights ({ state, rootGetters }) {
      // Import sources and layers for stream segment highlighting
      rootGetters.getStreamSources.forEach((s) => {
        state.map.addSource(s.name, { type: 'geojson', data: s.options })
      })
      rootGetters.getStreamLayers.forEach((l) => {
        state.map.addLayer(l)
      })
    },
    async initHighlightLayers ({ state }) {
      await state.map.on('load', () => {
        // initialize highlight layer
        state.map.addSource('customShapeData', { type: 'geojson', data: emptyPolygon })
        state.map.addLayer({
          'id': 'customShape',
          'type': 'fill',
          'source': 'customShapeData',
          'layout': {},
          'paint': {
            'fill-color': 'rgba(26, 193, 244, 0.08)',
            'fill-outline-color': 'rgb(8, 159, 205)'
          }
        })
        state.map.addSource('highlightLayerData', {
          type: 'geojson',
          data: emptyPolygon
        })
        state.map.addLayer({
          'id': 'highlightLayer',
          'type': 'fill',
          'source': 'highlightLayerData',
          'layout': {},
          'paint': {
            'fill-color': 'rgba(154, 63, 202, 0.25)'
          }
        })
        state.map.addImage('highlight-point', HighlightPoint(state.map, 90), { pixelRatio: 2 })
        state.map.addSource('highlightPointData', { type: 'geojson', data: emptyPoint })
        state.map.addLayer({
          'id': 'highlightPoint',
          'type': 'symbol',
          'source': 'highlightPointData',
          'layout': {
            'icon-image': 'highlight-point'
          }
        })
      })
    },
    /*
      Highlights a single Feature dataset
     */
    updateHighlightLayerData ({ state, commit, dispatch }, data) {
      // For stream networks layer we add custom highlighting and reset poly/point highlight layering
      if (data.display_data_name === 'freshwater_atlas_stream_networks') {
        state.map.getSource('highlightPointData').setData(emptyPoint)
        state.map.getSource('highlightLayerData').setData(emptyPolygon)
        // For local rendered streams only calculation
        commit('resetStreamData', {}, { root: true })

        // Update stream layer
        let layer = state.map.queryRenderedFeatures({ layers: ['freshwater_atlas_stream_networks'] })
        dispatch('calculateStreamHighlights', { stream: data, streams: layer }, { root: true })

        // Backend query for all connected streams
        // this.$store.dispatch('fetchConnectedStreams', { stream: data })
      } else if (data.geometry.type === 'Point') { // Normal poly/point highlighting
        state.map.getSource('highlightPointData').setData(data)
        state.map.getSource('highlightLayerData').setData(emptyPolygon)
        commit('resetStreamData', {}, { root: true })
        commit('resetStreamBufferData', {}, { root: true })
      } else {
        state.map.getSource('highlightPointData').setData(emptyPoint)
        state.map.getSource('highlightLayerData').setData(data)
        commit('resetStreamData', {}, { root: true })
        commit('resetStreamBufferData', {}, { root: true })
      }
    },
    /*
     Highlights a FeatureCollection dataset
    */
    updateHighlightsLayerData ({ state }, data) {
      if (data.display_data_name === 'stream_apportionment') {
        state.map.getSource('streamApportionmentSource').setData(data.feature_collection)
      }
    },
    downloadMapImage ({ state }) {
      let filename = 'map--'.concat(new Date().toISOString()) + '.png'
      html2canvas(state.map._container).then(canvas => {
        canvas.toBlob(function (blob) {
          saveAs(blob, filename)
        })
      })
    },
    removeElementsByClass ({ state }, payload) {
      let elements = document.getElementsByClassName(payload)
      while (elements.length > 0) {
        elements[0].parentNode.removeChild(elements[0])
      }
    }
  },
  mutations: {
    activateLayer (state, displayDataName) {
      state.map.setLayoutProperty(displayDataName, 'visibility', 'visible')
    },
    deactivateLayer (state, displayDataName) {
      state.map.setLayoutProperty(displayDataName, 'visibility', 'none')
    },
    activateBaseLayer (state, layerId) {
      state.map.setLayoutProperty(layerId, 'visibility', 'visible')
    },
    deactivateBaseLayer (state, layerId) {
      state.map.setLayoutProperty(layerId, 'visibility', 'none')
    },
    removeLayer (state, layerId) {
      state.map.removeLayer(layerId)
    },
    addShape (state, shape) {
      // adds a mapbox-gl-draw shape to the map
      state.map.getSource('customShapeData').setData(shape)
    },
    removeShapes (state) {
      state.map.getSource('customShapeData').setData(emptyPolygon)
    },
    replaceOldFeatures (state, newFeature = null) {
      // replace all previously drawn features with the new one.
      // this has the effect of only allowing one selection box to be drawn at a time.
      const old = state.draw.getAll().features.filter((f) => f.id !== newFeature)
      state.draw.delete(old.map((feature) => feature.id))
    },
    setMap (state, payload) {
      state.map = payload
    },
    setDraw (state, payload) {
      state.draw = payload
    },
    setGeocoder (state, payload) {
      state.geocoder = payload
    },
    setLayerSelectTriggered (state, payload) {
      state.layerSelectTriggered = payload
    },
    setLayerSelectionActiveState (state, payload) {
      state.layerSelectionActive = payload
    },
    setLayerCategories (state, payload) {
      state.layerCategories = payload
    },
    setActiveMapLayers (state, payload) {
      // TODO: See if this is actually used anywhere else
      // Could have been deprecated by updateActiveMapLayers
      state.activeMapLayers = state.mapLayers.filter((l) => {
        return payload.includes(l.display_data_name)
      })
    },
    setMapLayers (state, payload) {
      state.mapLayers = payload
    },
    updateHighlightFeatureData (state, payload) {
      state.highlightFeatureData = payload
    },
    updateHighlightFeatureCollectionData (state, payload) {
      state.highlightFeatureCollectionData = payload
    },
    setCursorPointer (state) {
      state.map.getCanvas().style.cursor = 'pointer'
    },
    resetCursor (state) {
      state.map.getCanvas().style.cursor = ''
    }
  },
  getters: {
    selectedMapLayerNames: state => state.selectedMapLayerNames,
    activeMapLayers: state => state.activeMapLayers,
    isMapLayerActive: state => displayDataName => !!state.activeMapLayers.find((x) => x && x.display_data_name === displayDataName),
    mapLayerName: (state) => (wmsName) => {
      let layer = state.mapLayers.find(e => e.wms_name === wmsName)
      return layer ? layer.display_name : ''
    },
    getMapLayer: (state) => (displayDataName) => {
      let layer = state.mapLayers.find(e => e.display_data_name === displayDataName)
      return layer || null
    },
    allMapLayers: state => state.mapLayers,
    highlightFeatureData: state => state.highlightFeatureData,
    highlightFeatureCollectionData: state => state.highlightFeatureCollectionData,
    getCategories: state => state.layerCategories,
    layerSelectionActive: state => state.layerSelectionActive,
    selectedBaseLayers: state => state.selectedBaseLayers,
    baseMapLayers: state => state.baseMapLayers,
    map: state => state.map,
    draw: state => state.draw,
    geocoder: state => state.geocoder,
    layerSelectTriggered: state => state.layerSelectTriggered
  }
}
