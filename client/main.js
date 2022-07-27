import { createApp } from 'vue'
import { createPinia } from 'pinia'
import piniaPersist from 'pinia-plugin-persist'
import App from './App.vue'
import router from './router'

const app = createApp(App, {})

// Initialize store (Pinia)

const pinia = createPinia()
pinia.use(piniaPersist)
app.use(pinia)

// Initialize router

router.beforeEach((to, from) => {
  // Route Flags
  // -> Remove Left Menu
  if (to.meta.hideLeftMenu) {
    const leftMenuRef = document.querySelector('.leftmenu')
    if (leftMenuRef) {
      leftMenuRef.remove()
    }
  }
})
app.use(router)

// Mount App

app.mount('#app')
