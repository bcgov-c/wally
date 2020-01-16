import qs from 'querystring'
import ApiService from '../../services/ApiService'
import EventBus from '../../services/EventBus'
import { Plotly } from 'vue-plotly'
import PlotlyJS from 'plotly.js'
import mapboxgl from 'mapbox-gl'
import { mapGetters } from 'vuex'
import html2canvas from 'html2canvas'
import { saveAs } from 'file-saver'

export default {
  name: 'WellsCrossSection',
  components: {
    Plotly
  },
  mounted () {
    this.fetchWellsAlongLine()
  },
  props: ['record', 'coordinates', 'panelOpen'],
  data: () => ({
    radius: 200,
    wells: [],
    wellsLithology: [],
    elevations: [],
    surfacePoints: [],
    loading: false,
    ignoreButtons: [
      'toImage',
      'sendDataToCloud',
      'hoverCompareCartesian',
      'hoverClosestCartesian',
      'toggleSpikelines'
    ]
  }),
  computed: {
    ...mapGetters([
      'map'
    ]),
    chartLayout () {
      const opts = {
        shapes: [],
        title: 'Groundwater Wells',
        height: 800,
        legend: {
          x: -0.1,
          y: 1.2
        },
        yaxis: {
          title: {
            text: 'Elevation (masl)'
          }
        },
        xaxis: {
          title: {
            text: 'Distance (m)'
          }
        },
        annotations: [{
          xref: 'paper',
          yref: 'paper',
          x: 0,
          xanchor: 'right',
          y: -0.1,
          yanchor: 'bottom',
          text: 'A\'',
          showarrow: false,
          font: {
            size: 16,
            color: '#ffffff'
          },
          align: 'center',
          bordercolor: '#1A5A96',
          borderwidth: 4,
          borderpad: 4,
          bgcolor: '#1A5A96',
          opacity: 0.8
        }, {
          xref: 'paper',
          yref: 'paper',
          x: 1,
          xanchor: 'left',
          y: -0.1,
          yanchor: 'bottom',
          text: 'B\'',
          showarrow: false,
          font: {
            size: 16,
            color: '#ffffff'
          },
          align: 'center',
          bordercolor: '#1A5A96',
          borderwidth: 4,
          borderpad: 4,
          bgcolor: '#1A5A96',
          opacity: 0.8
        }]
      }
      this.wells.forEach(w => {
        const rect = {
          type: 'rect',
          xref: 'x',
          yref: 'y',
          x0: w.distance_from_origin,
          y0: w.ground_elevation_from_dem,
          x1: w.distance_from_origin,
          y1: w.finished_well_depth
            ? w.ground_elevation_from_dem - w.finished_well_depth
            : null,
          opacity: 0.5,
          line: {
            color: 'blue',
            width: 3
          }
        }
        opts.shapes.push(rect)
      })
      return opts
    },
    chartData () {
      const wells = {
        x: this.wells.map(w => w.distance_from_origin),
        y: this.wells.map(w =>
          w.finished_well_depth
            ? w.ground_elevation_from_dem - w.finished_well_depth
            : null
        ),
        text: this.wells.map(w => w.well_tag_number),
        textposition: 'bottom center',
        showlegend: false,
        hovertemplate:
          '<b>Well</b>: %{text}' + '<br>Bottom elev.: %{y:.1f} m<br>',
        type: 'scatter',
        marker: {
          color: 'rgb(252,141,98)'
        },
        hoverlabel: {
          namelength: 0
        },
        name: 'Finished well depth (reported)',
        mode: 'markers'
      }
      const waterDepth = {
        x: this.wells.map(w => w.distance_from_origin),
        y: this.wells.map(w =>
          w.water_depth ? w.ground_elevation_from_dem - w.water_depth : null
        ),
        mode: 'markers',
        marker: {
          color: 'blue',
          symbol: 'triangle-down',
          size: 12
        },
        name: 'Depth to water (reported)',
        hoverlabel: {
          namelength: 0
        },
        hovertemplate: 'Water elev.: %{y:.1f} m<br>',
        type: 'scatter'
      }

      const lithology = {
        x: this.wellsLithology.map(w => w.x),
        y: this.wellsLithology.map(w => w.y0),
        text: this.wellsLithology.map(w => w.data),
        mode: 'markers',
        type: 'scatter',
        textposition: 'middle right',
        marker: {
          color: this.wellsLithology.map(w => w.color)
        },
        name: 'Lithology',
        hoverlabel: {
          namelength: 0
        },
        // texttemplate: '%{text}',
        // hoverinfo: 'text',
        hovertemplate: '%{text} %{y} m'
      }
      const elevProfile = {
        x: this.elevations.map(e => e.distance_from_origin),
        y: this.elevations.map(e => e.elevation),
        mode: 'lines',
        name: 'Ground elevation',
        type: 'scatter',
        showlegend: false
      }
      const waterLevel = {
        x: this.wells.map(w => w.distance_from_origin ? w.distance_from_origin : null),
        y: this.wells.map(w => w.water_depth ? w.ground_elevation_from_dem - w.water_depth : null),
        mode: 'lines',
        name: 'Water Level',
        line: {
          color: 'blue',
          width: 2
        },
        hoverlabel: {
          namelength: 0
        },
        hoverinfo: 'none'
      }
      return [elevProfile, waterDepth, wells, lithology, waterLevel]
    },
    surfaceData () {
      var lines = this.surfacePoints
      var x = []
      var y = []
      var z = []
      // build our surface points layer
      for (let i = 0; i < lines.length; i++) {
        const line = lines[i]
        x.push(line.map(l => l[0]))
        y.push(line.map(l => l[1]))
        z.push(line.map(l => l[2]))
      }
      // add our lithology drop lines and markers
      var lithologyMarkers = []
      this.wellsLithology.forEach(lith => {
        const marker = {
          x: [lith.lon, lith.lon],
          y: [lith.lat, lith.lat],
          z: [lith.y0, lith.y1],
          text: [lith.data, lith.data],
          mode: 'lines+markers',
          type: 'scatter3d',
          showlegend: false,
          line: {
            width: 3,
            color: 'blue' // lith.color
          },
          marker: {
            size: 5,
            color: 'black' // lith.color,
          },
          hovertemplate: '%{text} %{z} m',
          // hoverinfo: 'skip',
          name: ''
        }
        lithologyMarkers.push(marker)
      })
      return [
        {
          x: x,
          y: y,
          z: z,
          type: 'surface',
          contours: {
            z: {
              show: true,
              usecolormap: true,
              highlightcolor: '#42f462',
              project: { z: true }
            }
          }
        },
        ...lithologyMarkers
      ]
    },
    surfaceLayout () {
      let a = this.surfacePoints[2][0]
      var b = this.surfacePoints[2][this.surfacePoints[2].length - 1]

      return {
        title: '',
        showlegend: false,
        scene: {
          xaxis: {
            title: 'Longitude'
          },
          yaxis: {
            title: 'Latitude'
          },
          zaxis: {
            title: 'Elevation (m)'
          },
          annotations: [{
            x: a[0],
            y: a[1],
            z: a[2],
            text: 'A\'',
            ay: -60,
            font: {
              color: 'black',
              size: 18
            }
          }, {
            x: b[0],
            y: b[1],
            z: b[2],
            text: 'B\'',
            ay: -60,
            font: {
              color: 'black',
              size: 18
            }
          }]
        },
        margin: {
          l: 1,
          r: 1,
          b: 1,
          t: 1
        }
      }
    }
  },
  methods: {
    fetchWellsAlongLine () {
      const params = {
        radius: parseFloat(this.radius),
        line: JSON.stringify(this.coordinates)
      }
      ApiService.query(`/api/v1/wells/section?${qs.stringify(params)}`)
        .then(r => {
          console.log(r.data)
          this.wells = r.data.wells
          this.elevations = r.data.elevation_profile
          this.surfacePoints = r.data.surface
          this.showBuffer(r.data.search_area)
          let wellIds = this.wells.map(w => w.well_tag_number).join()
          this.fetchWellsLithology(wellIds)
        })
        .catch(e => {
          console.error(e)
        })
        .finally(() => {
          this.loading = false
          this.setAnnotationMarkers()
        })
    },
    setAnnotationMarkers () {
      var annotationGeoJson = [
        {
          type: 'Feature',
          geometry: {
            type: 'Point',
            coordinates: this.coordinates[0]
          },
          properties: {
            'symbol': 'A\''
          }
        },
        {
          type: 'Feature',
          geometry: {
            type: 'Point',
            coordinates: this.coordinates[1]
          },
          properties: {
            'symbol': 'B\''
          }
        }
      ]
      var mapObj = this.map
      // delete any existing markers
      this.removeElementsByClass('annotationMarker')
      // add markers to map
      annotationGeoJson.forEach(function (marker) {
        // create a HTML element for each feature
        var el = document.createElement('div')
        el.className = 'annotationMarker'
        el.innerText = marker.properties.symbol

        // make a marker for each feature and add to the map
        new mapboxgl.Marker(el)
          .setLngLat(marker.geometry.coordinates)
          .addTo(mapObj)
      })
    },
    removeElementsByClass (className) {
      var elements = document.getElementsByClassName(className)
      while (elements.length > 0) {
        elements[0].parentNode.removeChild(elements[0])
      }
    },
    fetchWellsLithology (ids) {
      // https://gwells-dev-pr-1488.pathfinder.gov.bc.ca/gwells/api/v1/wells/lithology?wells=112316
      // ApiService.query(`/api/v1/wells/section?${qs.stringify(params)}`).then((r) => {
      // DEBUG
      // ids = '112316'
      // let result = `{"count":2,"next":null,"previous":null,"results":[{"well_tag_number":72177,"latitude":50.146298,"longitude":-122.953464,"lithologydescription_set":[{"start":"0.00","end":"8.00","lithology_raw_data":"COURSE GRAVEL SOME BOULDERS","lithology_observation":null,"water_bearing_estimated_flow":null},{"start":"8.00","end":"17.00","lithology_raw_data":"WATER BEARING GRAVEL SOME SMALL BOULDERS","lithology_observation":null,"water_bearing_estimated_flow":null},{"start":"17.00","end":"26.00","lithology_raw_data":"DIRTY WATER BEARING SAND & GRAVEL","lithology_observation":null,"water_bearing_estimated_flow":null},{"start":"26.00","end":"71.00","lithology_raw_data":"dirty silty water-bearing sand & gravel, some wood","lithology_observation":null,"water_bearing_estimated_flow":null},{"start":"71.00","end":"77.00","lithology_raw_data":"VERY SILTY FINE SAND CLAY & WOOD","lithology_observation":null,"water_bearing_estimated_flow":null},{"start":"77.00","end":"86.00","lithology_raw_data":"dirty silty water-bearing sand and layers of clay, some gravel","lithology_observation":null,"water_bearing_estimated_flow":null},{"start":"86.00","end":"92.00","lithology_raw_data":"very silty fine water-bearing sand & layers of clay","lithology_observation":null,"water_bearing_estimated_flow":null},{"start":"92.00","end":"172.00","lithology_raw_data":"GRAY CLAY WITH LAYERS OF SILT","lithology_observation":null,"water_bearing_estimated_flow":null},{"start":"172.00","end":"180.00","lithology_raw_data":"VERY COURSE SHARP WATER BEARING GRAVEL","lithology_observation":null,"water_bearing_estimated_flow":null}]},{"well_tag_number":80581,"latitude":50.143818,"longitude":-122.959162,"lithologydescription_set":[{"start":"0.00","end":"4.00","lithology_raw_data":"brown sand and fill containing stones","lithology_observation":null,"water_bearing_estimated_flow":null},{"start":"4.00","end":"9.00","lithology_raw_data":"brown silty sandy soil containing wood, peat and stones","lithology_observation":null,"water_bearing_estimated_flow":null},{"start":"9.00","end":"14.00","lithology_raw_data":"grey clay","lithology_observation":null,"water_bearing_estimated_flow":null},{"start":"14.00","end":"30.00","lithology_raw_data":"grey compact silt containing wood","lithology_observation":null,"water_bearing_estimated_flow":null},{"start":"30.00","end":"34.00","lithology_raw_data":"peat and wood with some grey silt","lithology_observation":null,"water_bearing_estimated_flow":null},{"start":"34.00","end":"48.00","lithology_raw_data":"grey silt containing peat and wood","lithology_observation":null,"water_bearing_estimated_flow":null},{"start":"48.00","end":"52.00","lithology_raw_data":"grey silt with traces of peat seams and some wood","lithology_observation":null,"water_bearing_estimated_flow":null},{"start":"52.00","end":"74.00","lithology_raw_data":"darker grey silt","lithology_observation":null,"water_bearing_estimated_flow":null},{"start":"74.00","end":"81.00","lithology_raw_data":"brown firm silt containing seams of brown sand and stones, water-bearing","lithology_observation":null,"water_bearing_estimated_flow":null},{"start":"81.00","end":"116.00","lithology_raw_data":"grey with seams of stones and sand and some wood below 92'","lithology_observation":null,"water_bearing_estimated_flow":null},{"start":"116.00","end":"117.00","lithology_raw_data":"fine compact silty sand, fairly tight","lithology_observation":null,"water_bearing_estimated_flow":null},{"start":"117.00","end":"134.00","lithology_raw_data":"grey silt with seams of compact silty fine sand & containing wood from 117' to 127'","lithology_observation":null,"water_bearing_estimated_flow":null},{"start":"134.00","end":"136.00","lithology_raw_data":"grey, silty coarse gravel, sharp, silty wash","lithology_observation":null,"water_bearing_estimated_flow":null},{"start":"136.00","end":"139.00","lithology_raw_data":"grey silty coarse sand and broken coarse gravel","lithology_observation":null,"water_bearing_estimated_flow":null},{"start":"139.00","end":"142.00","lithology_raw_data":"grey compact silt, broken gravel & cobbles, sharp and tight","lithology_observation":null,"water_bearing_estimated_flow":null},{"start":"142.00","end":"145.00","lithology_raw_data":"large broken rock, yielding more water","lithology_observation":null,"water_bearing_estimated_flow":null},{"start":"145.00","end":"147.00","lithology_raw_data":"green broken rock, very tight","lithology_observation":null,"water_bearing_estimated_flow":null},{"start":"147.00","end":"158.00","lithology_raw_data":"broken grey and brown-coloured rock","lithology_observation":null,"water_bearing_estimated_flow":null},{"start":"158.00","end":"164.00","lithology_raw_data":"solid bedrock","lithology_observation":null,"water_bearing_estimated_flow":null}]}]}`
      // let resultObj = JSON.parse(result)
      // let results = resultObj.results
      // this.wellsLithology = lithologyList
      // console.log(ids)
      ApiService.getRaw(`https://apps.nrs.gov.bc.ca/gwells/api/v2/wells/lithology?wells=${ids}`).then((r) => {
        console.log(r.data.results)
        let results = r.data.results
        var lithologyList = []
        for (let index = 0; index < results.length; index++) {
          const wellLithologySet = results[index]
          let well = this.wells.find(
            x => x.well_tag_number === wellLithologySet.well_tag_number
          )
          if (well) {
            wellLithologySet.lithologydescription_set.forEach(w => {
              lithologyList.push({
                x: well.distance_from_origin ? well.distance_from_origin : 0,
                y0: well.ground_elevation_from_dem - (w.start * 0.3048),
                y1: well.ground_elevation_from_dem - (w.end * 0.3048),
                lat: wellLithologySet.latitude,
                lon: wellLithologySet.longitude,
                data: w.lithology_raw_data,
                color: w.lithology_colour,
                hardness: w.lithology_hardness,
                observation: w.lithology_observation,
                flow: w.water_bearing_estimated_flow
              })
            })
          }
        }
        this.wellsLithology = lithologyList
      }).catch((e) => {
        console.error(e)
      }).finally(() => {
        this.loading = false
        this.initPlotly()
      })
    },
    showBuffer (polygon) {
      polygon.id = 'user_search_radius'
      // remove old shapes
      EventBus.$emit('shapes:reset')
      // add the new one
      EventBus.$emit('shapes:add', polygon)
    },
    initPlotly () {
      // Subscribe to plotly select and lasso tools
      this.$refs.crossPlot.$on('selected', this.setMarkerLabels)
      this.$refs.crossPlot.$on('deselect', this.resetMarkerLabels)
      this.$refs.crossPlot.$on('relayout', this.resetMarkerLabels)
    },
    resetMarkerLabels () {
      this.$refs.crossPlot.$el.removeEventListener('plotly_beforehover')
      this.$refs.crossPlot.$el.on('plotly_beforehover', () => { return true })
      PlotlyJS.Fx.hover('2dPlot', [])

      // var xy = document.getElementsByClassName("xy");
      // if(xy) {
      //   // var event = new Event('plotly_deselect', {bubbles: true});
      //   var event = new Event('plotly_doubleclick', {bubbles: true});
      //   for (let i = 0; i < xy.length; i++) {
      //     xy[i].dispatchEvent(event);
      //   }
      // }
      // var event = new Event('plotly_click', {bubbles: true})
      // this.$refs.crossPlot.$el.dispatchEvent(event)
      // this.$refs.crossPlot.$emit('plotly_click')
    },
    setMarkerLabels (e) {
      if (e && e.points.length > 0) {
      // This overrides hiding the hover labels
        this.$refs.crossPlot.$el.removeEventListener('plotly_beforehover')
        this.$refs.crossPlot.$el.on('plotly_beforehover', () => { return false })

        this.removeElementsByClass('select-outline')
        let points = e.points.map(p => {
          return { curveNumber: p.curveNumber, pointNumber: p.pointNumber }
        })
        this.markerLabels = points
        PlotlyJS.Fx.hover('2dPlot', points)
      }
    },
    downloadPlotImage () {
      var filename = 'plot--'.concat(new Date().toISOString()) + '.png'
      html2canvas(this.$refs.crossPlot.$el).then(canvas => {
        canvas.toBlob(function (blob) {
          saveAs(blob, filename)
        })
      })
    },
    downloadMapImage () {
      var filename = 'map--'.concat(new Date().toISOString()) + '.png'
      html2canvas(this.map._container).then(canvas => {
        canvas.toBlob(function (blob) {
          saveAs(blob, filename)
        })
      })
    },
    lassoTool () {
      // layout.dragmode = 'lasso'
      Plotly.relayout('myDiv', 'dragmode', 'lasso')
    }
  },
  watch: {
    panelOpen (value) {
      if (value) {
        this.setAnnotationMarkers()
      } else {
        this.removeElementsByClass('annotationMarker')
      }
    },
    record: {
      handler () {
        this.fetchWellsAlongLine()
      },
      deep: true
    },
    radius (value) {
      this.fetchWellsAlongLine()
    }
  },
  beforeDestroy () {
    // reset shapes when closing this component
    EventBus.$emit('shapes:reset')
  }
}
