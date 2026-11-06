import {createApp} from 'vue'
import {isTauri} from '@tauri-apps/api/core'
import App from './App.vue'
import {installKioskGuards,shouldLockKiosk} from './kiosk-guards'
import './style.css'
import './kiosk-guards.css'
import {installTraceCapture} from './trace-dom.js'
const admin=location.pathname.replace(/\/$/,'')==='/admin'
if(shouldLockKiosk({desktop:isTauri(),production:import.meta.env.PROD,admin})){
  const dispose=installKioskGuards()
  import.meta.hot?.dispose(dispose)
}
if(admin){
  import('./AdminApp.vue').then(({default:AdminApp})=>createApp(AdminApp).mount('#app'))
}else {
  const disposeTrace=installTraceCapture()
  import.meta.hot?.dispose(disposeTrace)
  createApp(App).mount('#app')
  if(import.meta.env.DEV&&import.meta.env.MODE==='trace'){
    import('./components/TraceInspector.vue').then(({default:Inspector})=>{
      const container=document.createElement('div');document.body.append(container)
      const inspector=createApp(Inspector);inspector.mount(container)
      import.meta.hot?.dispose(()=>{inspector.unmount();container.remove()})
    })
  }
}
