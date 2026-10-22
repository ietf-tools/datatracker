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
      component: () => import('./agenda/Agenda.vue')
    },
    {
      name: 'floor-plan',
      path: '/meeting/:meetingNumber(\\d+)?/floor-plan',
      component: () => import('./agenda/FloorPlan.vue')
    },
    // -> Redirects
    {
      path: '/meeting/:meetingNumber(\\d+)?/agenda.html',
      redirect: to => {
        return { name: 'agenda' }
      }
    },
    {
      path: '/meeting/:meetingNumber(\\d+)?/agenda-utc',
      redirect: to => {
        return { name: 'agenda', query: { ...to.query, tz: 'UTC' } }
      }
    },
    {
      path: '/meeting/:meetingNumber(\\d+)?/agenda/personalize',
      redirect: to => {
        return { name: 'agenda', query: { ...to.query, pick: true } }
      }
    }
  ]
})
