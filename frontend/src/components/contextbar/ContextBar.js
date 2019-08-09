import RandomChart from '../charts/RandomChart'
import CircleChart from '../charts/CircleChart'
import BarChart from '../charts/BarChart.js'
import {mapGetters} from "vuex";

export default {
  name: 'ContextBar',
  components: { CircleChart, RandomChart, BarChart },
  data () {
    return {
      drawer: {
        open: true,
        mini: true
      },
      bar_data: {
        labels: ['Red', 'Blue', 'Yellow', 'Green', 'Purple', 'Orange'],
        datasets: [{
          label: '# of Votes',
          data: [12, 19, 3, 5, 2, 3],
          backgroundColor: [
            'rgba(255, 99, 132, 0.2)',
            'rgba(54, 162, 235, 0.2)',
            'rgba(255, 206, 86, 0.2)',
            'rgba(75, 192, 192, 0.2)',
            'rgba(153, 102, 255, 0.2)',
            'rgba(255, 159, 64, 0.2)'
          ],
          borderColor: [
            'rgba(255, 99, 132, 1)',
            'rgba(54, 162, 235, 1)',
            'rgba(255, 206, 86, 1)',
            'rgba(75, 192, 192, 1)',
            'rgba(153, 102, 255, 1)',
            'rgba(255, 159, 64, 1)'
          ],
          borderWidth: 1
        }]
      }
    }
  },
  computed: {
    ...mapGetters([
      'featureInfo',
      'featureLayers'
    ])
  },
  methods: {
    toggleContextBar () {
      this.drawer.mini = !this.drawer.mini
    }
  },
  watch: {
    featureInfo (value) {
      if (value && value.properties) {
        console.log(value)
      }
    },
    featureLayers (value) {
      if (value.length > 0) {
        console.log(value)
      }
    }
  }
}
