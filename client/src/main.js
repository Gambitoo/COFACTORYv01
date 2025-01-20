import { createApp } from 'vue'
import App from './App.vue'
import router from './router'
import 'bootstrap/dist/css/bootstrap.css'
import { library } from '@fortawesome/fontawesome-svg-core';
import { FontAwesomeIcon } from '@fortawesome/vue-fontawesome';
import { faArrowLeft, faArrowRight, faFilter } from '@fortawesome/free-solid-svg-icons';

library.add(faArrowLeft, faArrowRight, faFilter);

const app = createApp(App)

app.component('FontAwesomeIcon', FontAwesomeIcon);
app.use(router)

app.mount('#app')
