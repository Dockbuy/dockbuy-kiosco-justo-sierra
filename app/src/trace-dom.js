import {interactionTrace} from './interaction-trace.js'

export function installTraceCapture(root=document,trace=interactionTrace) {
  let pointer=null
  const privateSelector='[data-trace-private],[data-trace-ignore],input,textarea,select,[contenteditable],.touch-keyboard,.touch-keyboard-inline,.campus-keyboard,.keyboard-backdrop'
  function point(event){if(event.target?.closest?.('.screen')&&!event.target.closest(privateSelector))pointer={target:event.target,type:event.pointerType||'mouse',at:Date.now()};else pointer=null}
  function click(event){
    const target=event.target?.closest?.('.screen')&&event.target
    if(!target||target.closest(privateSelector))return
    const control=target.closest('button,a,[role="button"],[data-trace-action]')
    if(control?.disabled||control?.getAttribute('aria-disabled')==='true')return
    const action=control?.getAttribute('data-trace-action')||(control?'control.unmapped':'surface.tap')
    const pointerClick=event.detail>0
    const input=!event.isTrusted?'programmatic':!pointerClick?'keyboard':pointer&&Date.now()-pointer.at<1500&&(pointer.target===target||control?.contains(pointer.target))?pointer.type:event.pointerType||'mouse'
    const siblings=control?Array.from(root.querySelectorAll('[data-trace-action]')).filter(element=>element.getAttribute('data-trace-action')===action):[]
    const index=siblings.length>1?siblings.indexOf(control):undefined
    const viewport=root.defaultView||window
    trace.interaction(action,{input,x:pointerClick?event.clientX/viewport.innerWidth:undefined,y:pointerClick?event.clientY/viewport.innerHeight:undefined,index})
    pointer=null
  }
  const leaving=()=>trace.end('page_exit')
  root.addEventListener('pointerdown',point,{capture:true,passive:true})
  root.addEventListener('click',click,true)
  root.defaultView?.addEventListener('pagehide',leaving)
  return ()=>{root.removeEventListener('pointerdown',point,true);root.removeEventListener('click',click,true);root.defaultView?.removeEventListener('pagehide',leaving)}
}
