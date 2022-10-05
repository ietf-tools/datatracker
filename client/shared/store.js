import { defineStore } from 'pinia'

export const useSiteStore = defineStore('site', {
  state: () => ({
    criticalError: null,
    isMobile: /Mobi/i.test(navigator.userAgent),
    viewport: Math.round(window.innerWidth)
  })
})
