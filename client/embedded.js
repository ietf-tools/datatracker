import { createApp } from 'vue'
import piniaPersist from 'pinia-plugin-persist'
import Embedded from './Embedded.vue'
import { createPiniaSingleton } from './shared/create-pinia-singleton'

// Initialize store (Pinia)

const pinia = createPiniaSingleton()
pinia.use(piniaPersist)

// Mount App

const mountEls = document.querySelectorAll('div.vue-embed')
for (const mnt of mountEls) {
  const app = createApp(Embedded, {
    componentName: mnt.dataset.component,
    componentId: mnt.dataset.componentId
  })
  app.use(pinia)
  app.mount(mnt)
}
