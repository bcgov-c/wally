import { mapGetters } from 'vuex'
import LegendItem from './LegendItem'
import FishObservationsLegendItem from './customLegendItems/FishObservationsLegendItem'
import WaterLicensedWorksLegendItem from './customLegendItems/WaterLicensedWorksLegendItem'
import WaterRightsLicencesLegendItem from './customLegendItems/WaterRightsLicencesLegendItem'
import WaterApprovalPointsLegendItem from './customLegendItems/WaterApprovalPointsLegendItem'
import StreamAllocationRestrictionsLegendItem from './customLegendItems/StreamAllocationRestrictionsLegendItem'
import { humanReadable } from '../../../common/helpers'

export default {
  name: 'MapLegend',
  components: {
    LegendItem,
    FishObservationsLegendItem,
    WaterLicensedWorksLegendItem,
    WaterRightsLicencesLegendItem,
    WaterApprovalPointsLegendItem,
    StreamAllocationRestrictionsLegendItem
  },
  data () {
    return {
      show: true,
      excludedLayers: [ // list of layers to ignore when rendering legend items
        'fish_observations_summaries',
        'water_licensed_works_dash1',
        'water_licensed_works_dash2',
        'water_licensed_works_dash3',
        'water_licensed_works_dash4'
      ]
    }
  },
  props: ['map'],
  methods: {
    getLegendItem (layer) {
      const type = this.map.getLayer(layer.display_data_name).type
      const paint = this.mapLayerPaint(type, layer.display_data_name)
      return {
        text: layer.display_name,
        type: type,
        ...paint
      }
    },
    mapLayerPaint (type, id) {
      let color = type !== 'symbol' && this.map.getPaintProperty(id, type + '-color')
      let strokeWidth = type === 'circle' && this.map.getPaintProperty(id, type + '-stroke-width')
      // let strokeColor = type === 'circle' && this.map.getPaintProperty(id, type + '-stroke-color')
      let radius = type === 'circle' && this.map.getPaintProperty(id, type + '-radius')
      let opacity = type === 'fill' && this.map.getPaintProperty(id, type + '-opacity')
      let outlineColor = type === 'fill' ? this.map.getPaintProperty(id, type + '-outline-color')
        : type === 'circle' && this.map.getPaintProperty(id, type + '-stroke-color')
      let width = type === 'line' && this.map.getPaintProperty(id, type + '-width')
      let image = type === 'symbol' && this.map.getLayoutProperty(id, 'icon-image')
      let rotation = type === 'symbol' && this.map.getLayoutProperty(id, 'icon-rotate')
      let size = type === 'symbol' && this.map.getLayoutProperty(id, 'icon-size')

      return {
        color,
        strokeWidth,
        radius,
        opacity,
        outlineColor,
        width,
        image,
        rotation,
        size
      }
    },
    getActiveCustomLayers () {
      return this.customLayers.children
        .filter((layer) => {
          return this.selectedCustomLayers.includes(layer.id) &&
            layer.id !== '_imported-map-layers'
        })
        .map((layer) => {
          return {
            display_data_name: layer.id,
            display_name: humanReadable(layer.name),
            name: layer.name
          }
        })
    },
    toggle () {
      this.show = !this.show
    }
  },
  computed: {
    ...mapGetters('map', [
      'activeMapLayers'
    ]),
    ...mapGetters('customLayers', [
      'selectedCustomLayers',
      'customLayers'
    ]),
    legend () {
      // merge together wally hosted layers
      // and any custom layers that a user uploads
      let activeCustomLayers = this.getActiveCustomLayers()
      return this.activeMapLayers.concat(activeCustomLayers)
    }
  }
}
