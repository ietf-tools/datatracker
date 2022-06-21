import { createApp } from 'vue'
import { createPinia } from 'pinia'
import piniaPersist from 'pinia-plugin-persist'
import App from './App.vue'

const app = createApp(App, {})

const pinia = createPinia()
pinia.use(piniaPersist)

app.use(pinia)

app.mount('#app-agenda')
