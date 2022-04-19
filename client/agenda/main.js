import { createApp } from 'vue'
// import PrimeVue from 'primevue/config'
import App from './App.vue'

// import 'primevue/resources/themes/saga-blue/theme.css'
// import 'primevue/resources/primevue.min.css'
// import 'primeicons/primeicons.css'

const agendaData = JSON.parse(document.getElementById('agenda-data').textContent)

const app = createApp(App, agendaData)

// app.use(PrimeVue, { ripple: true })

app.mount('#app-agenda')
