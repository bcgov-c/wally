import EventBus from '../services/EventBus.js'
import ApiService from '../services/ApiService.js'
import { wmsBaseURl, wmsParamString } from '../utils/wmsUtils'
import * as utils from '../utils/mapUtils'

export default {
  state: {
    activeDataMarts: [],
    dataMartFeatureInfo: { content: { properties: {} } },
    dataMartFeatures: [] // selected points
  },
  actions: {
    getDataMart ({ commit }, payload) {
      // Get the datamart either via API or wms layer
      const { id, url } = payload
      ApiService.getRaw(url).then((response) => {
        commit('addDataMart', {
          id: id,
          data: response.data
        })
        EventBus.$emit(`dataMart:updated`, payload)
      }).catch((error) => {
        console.log(error) // TODO create error state item and mutation
      })
    },
    getDataMartFeatureInfo ({ commit }, payload) {
      // WMS info
      // TODO: Complete this request
      ApiService.getRaw(payload.url).then((res) => {
        // TODO validate properties
        commit('setDataMartFeatureInfo', {
          id: res.data.features[0].id,
          coordinates: [payload.lat, payload.lng],
          properties: res.data.features[0].properties })
        EventBus.$emit(`feature:added`, payload)
      }).catch((error) => {
        console.log(error) // TODO create error state item and mutation
      })
    },
    getDataMartFeatures ({ commit }, payload) {
      // Get the datamart features (points, lines etc)
      payload.type === 'wms' &&
      ApiService.getRaw(wmsBaseURl + payload.layer + '/ows' + wmsParamString(payload))
        .then((response) => {
          console.log('wms response for geometries', response)
          let points = response.data.objects[payload.layer].geometries // TODO Test functional
          commit('setDataMartFeatures', { [payload.layer]: points })
        }).catch((error) => {
          console.log(error)
        })

      payload.type === 'api' &&
      ApiService.getRaw(utils.API_URL + payload.feature.properties.url).then((response) => {
        console.log('response', response)
        // TODO: get coordinates
        let points = [response.data.longitude, response.data.latitude]
        // TODO: setLayerFeatures
        commit('setDataMartFeatures', { [payload.layer]: points })
      }).catch(error => {
        console.log(error)
      })
    }
  },
  mutations: {
    setDataMartFeatureInfo: (state, payload) => { state.dataMartFeatureInfo = payload },
    setDataMartFeatures: (state, payload) => { state.dataMartFeatures.push(payload) },
    clearDataMartFeatures: (state) => { state.dataMartFeatures = [] },
    addDataMart (state, payload) {
      state.activeDataMarts.push(payload)
      EventBus.$emit(`dataMart:added`, payload)
    },
    removeDataMart (state, payload) {
      state.activeDataMarts = state.activeDataMarts.filter(function (source) {
        return source.id !== payload
      })
      EventBus.$emit(`dataMart:removed`, payload)
    }
  },
  getters: {
    dataMartFeatureInfo: state => state.dataMartFeatureInfo,
    dataMartFeatures: state => state.dataMartFeatures,
    activeDataMarts: state => state.activeDataMarts,
    isDataMartActive: state => id => !!state.activeDataMarts.find((x) => x && x.id === id),
    allDataMarts: () => [], // ideally grab these from the meta data api
  }
}
