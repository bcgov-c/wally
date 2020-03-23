// import { createLocalVue, mount } from '@vue/test-utils'
// import MonthlyAllocationTable
//   from '../../../src/components/analysis/surface_water/watershed_demand/MonthlyAllocationTable.vue'
// import Vuex from 'vuex'
// import Vuetify from 'vuetify'
// import Vue from 'vue'

// const localVue = createLocalVue()
// localVue.use(Vuex)
// // localVue with Vuetify shows console warnings so we'll use Vue instead
// // https://github.com/vuetifyjs/vuetify/issues/4964
// // localVue.use(Vuetify)
// Vue.use(Vuetify)
// Vue.filter('formatNumber', () => 'foo')

// const vuetify = new Vuetify()

// describe('MonthlyAllocationTable Test', () => {
//   let wrapper
//   let store
//   let propsData

//   beforeEach(() => {
//     let surfaceWater = {
//       namespaced: true,
//       getters: {
//         allocationValues: () => {
//           return { 'test 1': [] }
//         }
//       },
//       mutations: {
//       },
//       actions: {
//         loadAllocationItemsFromStorage: jest.fn()
//       }
//     }

//     propsData = {
//       'allocationItems': [
//         { 'testKey': 'test 1' },
//         { 'testKey': 'test 2' },
//         { 'testKey': 'test 3' }
//       ],
//       'keyField': 'testKey'
//     }

//     store = new Vuex.Store({ modules: { surfaceWater } })
//     wrapper = mount(MonthlyAllocationTable, {
//       vuetify,
//       store,
//       localVue,
//       propsData
//     })
//   })

//   it('Show allocation table', () => {
//     let allocationCard = wrapper.findAll('div#editableModelCard')
//     expect(allocationCard.length).toBe(1)
//   })

//   it('Rows for each allocation item', () => {
//     let tableRows = wrapper.findAll('table tbody tr')
//     expect(tableRows.length).toBe(propsData.allocationItems.length)
//   })

//   it('Input text fields for each alloc item for each month', () => {
//     let inputTextFields = wrapper.findAll('input[type=text]')
//     expect(inputTextFields.length).toBe(propsData.allocationItems.length * 12)
//   })
// })
