import { createRouter, createWebHistory } from 'vue-router'

export default createRouter({
  history: createWebHistory(),
  routes: [
    {
      name: 'agenda',
      path: '/meeting/:meetingNumber(\\d+)?/agenda-neue',
      component: () => import('./Agenda.vue'),
      meta: {
        hideLeftMenu: true
      }
    },
    {
      name: 'floor-plan',
      path: '/meeting/:meetingNumber(\\d+)?/floor-plan-neue',
      component: () => import('./FloorPlan.vue'),
      meta: {
        hideLeftMenu: true
      }
    }
  ]
})
