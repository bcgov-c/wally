import { mapGetters } from 'vuex'
import { humanReadable } from '../../helpers'
import * as utils from '../../utils/mapUtils'
import * as dataUtils from '../../utils/dataUtils'

export default {
  name: 'Sidebar',
  data () {
    return {
      active_tab: 0,
      tabs: [
        { id: 1, name: 'Layers' },
        { id: 2, name: 'Features' },
        { id: 3, name: 'Info' }
      ],
      drawer: true,
      items: [
        {
          title: 'Layers',
          icon: 'layers',
          action: 'layers',
          choices: utils.MAP_LAYERS
        },
        {
          title: 'Data Sources',
          icon: 'library_books',
          action: 'library_books',
          choices: dataUtils.DATAMARTS
        }
      ],
      mini: true,
      subHeading: ''
    }
  },
  computed: {
    ...mapGetters([
      'isMapLayerActive',
      'isDataMartActive',
      'dataMartInfo',
      'dataMartFeatureInfo',
      'dataMartLayers'
    ])
  },
  methods: {
    setTabById (id) {
      this.active_tab = id
    },
    handleSelectLayer (id, type, resource) {
      if (type === dataUtils.API_DATAMART) {
        this.updateDataLayer(id, resource)
      } else {
        this.updateMapLayer(id)
      }
    },
    updateMapLayer (id) {
      if (this.isMapLayerActive(id)) {
        this.$store.commit('removeMapLayer', id)
      } else {
        this.$store.commit('addMapLayer', id)
      }
    },
    updateDataLayer (id, url) {
      if (this.isDataMartActive(id)) {
        this.$store.commit('removeDataMart', id)
      } else {
        this.$store.dispatch('getDataMart', { id: id, url: url })
      }
    },
    createReportFromSelection () {
      if (this.active_tab === 1) {
        this.$store.dispatch('downloadLayersReport', this.dataMartLayers)
      } else if (this.active_tab === 2) {
        this.$store.dispatch('downloadFeatureReport',
          { featureName: this.mapSubheading(this.dataMartInfo.id), ...this.dataMartInfo })
      }
    },
    handleSelectListItem (item) {
      // this.$store.dispatch(FETCH_MAP_OBJECT, item.id)
      if ('LATITUDE' in item.properties && 'LONGITUDE' in item.properties) {
        item.coordinates = [item.properties['LATITUDE'], item.properties['LONGITUDE']]
      } else {
        item.coordinates = null
      }
      this.$store.commit('setDataMartInfo', item)
    },
    humanReadable: val => humanReadable(val),
    mapLayerItemTitle: val => utils.mapLayerItemTitle(val),
    mapLayerItemValue: val => utils.mapLayerItemValue(val),
    mapLayerName: val => utils.mapLayerName(val),
    mapSubheading: val => utils.mapSubheading(val)
  },
  watch: {
    dataMartInfo (value) {
      if (value && value.properties) {
        this.setTabById(2)
      }
    },
    dataMartLayers (value) {
      if (value.length > 0) {
        this.setTabById(1)
      }
    }
  }
}
