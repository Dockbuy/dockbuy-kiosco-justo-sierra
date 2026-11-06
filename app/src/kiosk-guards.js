// Protección de interacción. El inspector nativo se desactiva en tauri.conf.json.
// Estas barreras no sustituyen los permisos de la API ni las políticas del SO.
export function shouldLockKiosk({desktop=false,production=false,admin=false}={}) {
  return desktop || (production && !admin)
}

export function blocksKioskShortcut(event) {
  // AltGr se usa para escribir @ y otros caracteres en teclados internacionales.
  if(event.isComposing || event.getModifierState?.('AltGraph')) return false
  const key=(event.key || '').toLowerCase()
  if(['f5','f11','f12','contextmenu'].includes(key)) return true
  if(event.shiftKey && key==='f10') return true
  const command=event.ctrlKey || event.metaKey
  if(command) {
    if(['+','=','-','_','0'].includes(key) || ['NumpadAdd','NumpadSubtract','Numpad0'].includes(event.code)) return true
    if(event.shiftKey && ['i','j','c','k'].includes(key)) return true
    if(event.metaKey && event.altKey && ['i','j','c'].includes(key)) return true
    if(!event.altKey && ['r','p','s','u','f','o','l'].includes(key)) return true
  }
  // Navegación del WebView: no abandonar una sesión con Alt+flecha.
  if(event.altKey && !command && ['arrowleft','arrowright','home'].includes(key)) return true
  if(key==='backspace' && !command && !event.altKey) {
    const editable=event.target?.closest?.('input,textarea,[contenteditable="true"],[contenteditable=""]')
    return !editable
  }
  return false
}

export function installKioskGuards(target=window) {
  const doc=target.document,root=doc.documentElement
  const previousLock=root.getAttribute('data-kiosk-lock')
  root.setAttribute('data-kiosk-lock','true')
  let viewport=doc.querySelector('meta[name="viewport"]')
  const createdViewport=!viewport,previousViewport=viewport?.getAttribute('content')
  if(!viewport){viewport=doc.createElement('meta');viewport.name='viewport';doc.head.appendChild(viewport)}
  viewport.setAttribute('content','width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no')
  const listeners=[]
  const listen=(name,handler)=>{
    const options={capture:true,passive:false}
    target.addEventListener(name,handler,options)
    listeners.push(()=>target.removeEventListener(name,handler,options))
  }
  const cancel=event=>{event.preventDefault();event.stopImmediatePropagation()}
  listen('keydown',event=>{if(blocksKioskShortcut(event))cancel(event)})
  listen('wheel',event=>{if(event.ctrlKey || event.metaKey)cancel(event)})
  // Un dedo sigue desplazando la página; dos dedos no cambian su escala.
  for(const type of ['touchstart','touchmove'])listen(type,event=>{if(event.touches.length>1)cancel(event)})
  for(const type of ['gesturestart','gesturechange','gestureend','contextmenu','dragstart','dragover','drop'])listen(type,cancel)
  return ()=>{
    listeners.forEach(remove=>remove())
    if(previousLock===null)root.removeAttribute('data-kiosk-lock');else root.setAttribute('data-kiosk-lock',previousLock)
    if(createdViewport)viewport.remove()
    else if(previousViewport===null)viewport.removeAttribute('content')
    else viewport.setAttribute('content',previousViewport)
  }
}
