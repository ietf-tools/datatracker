import { createRouter, createWebHistory } from 'vue-router'

export default createRouter({
  history: createWebHistory(),
  routes: [
    // ---------------------------------------------------------
    // MEETING
    // ---------------------------------------------------------
    {
      name: 'agenda',
      path: '/meeting/:meetingNumber(\\d+)?/agenda',
      component: () => import('./agenda/Agenda.vue'),
      meta: {
        hideLeftMenu: true
      }
    },
    {
      name: 'floor-plan',
      path: '/meeting/:meetingNumber(\\d+)?/floor-plan',
      component: () => import('./agenda/FloorPlan.vue'),
      meta: {
        hideLeftMenu: true
      }
    },
    // -> Redirects
    {
      path: '/meeting/:meetingNumber(\\d+)?/agenda/personalize',
      redirect: to => {
        return { name: 'agenda', query: { ...to.query, pick: true } }
      }
    }
  ]
})
