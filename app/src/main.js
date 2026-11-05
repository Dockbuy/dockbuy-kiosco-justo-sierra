import {createApp} from 'vue'
import App from './App.vue'
import './style.css'
if(location.pathname.replace(/\/$/,'')==='/admin'){
  import('./AdminApp.vue').then(({default:AdminApp})=>createApp(AdminApp).mount('#app'))
}else createApp(App).mount('#app')
