import {createApp} from 'vue'
import {isTauri} from '@tauri-apps/api/core'
import App from './App.vue'
import {installKioskGuards,shouldLockKiosk} from './kiosk-guards'
import './style.css'
import './kiosk-guards.css'
const admin=location.pathname.replace(/\/$/,'')==='/admin'
if(shouldLockKiosk({desktop:isTauri(),production:import.meta.env.PROD,admin})){
  const dispose=installKioskGuards()
  import.meta.hot?.dispose(dispose)
}
if(admin){
  import('./AdminApp.vue').then(({default:AdminApp})=>createApp(AdminApp).mount('#app'))
}else createApp(App).mount('#app')
