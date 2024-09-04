import { createApp } from 'vue'
import piniaPersist from 'pinia-plugin-persist'
import App from './App.vue'
import router from './router'
import { createPiniaSingleton } from './shared/create-pinia-singleton'

const app = createApp(App, {})

// Initialize store (Pinia)

const pinia = createPiniaSingleton()
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
