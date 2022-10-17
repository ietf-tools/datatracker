import { createApp } from 'vue'
import Embedded from './Embedded.vue'

// Mount App

const mountEls = document.querySelectorAll('div.vue-embed')
for (const mnt of mountEls) {
  const app = createApp(Embedded, {
    componentName: mnt.dataset.component,
    componentId: mnt.dataset.componentId
  })
  app.mount(mnt)
}
