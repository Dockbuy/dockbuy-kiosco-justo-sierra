import {actions,screens,steps,overlays,operationNames,defaultSteps} from './trace-catalog.js'

const copy = value => JSON.parse(JSON.stringify(value))
const has = (object,key) => Object.hasOwn(object,key)
const outcomes = new Set(['ok','error','cancelled','timeout','network','print_limited','print_failed','accepted','sending','unknown','failed'])

// Solo RAM. El adaptador de transporte permanece desconectado hasta recibir la API.
export function createInteractionTrace({now=()=>Date.now(),id=()=>crypto.randomUUID(),maxSessions=10,maxEvents=500,transport=null,timeout=5000}={}) {
  const sessions=[],listeners=new Set(),pending=new Set()
  let active=null,context={screen:'dashboard',step:'main',overlay:''},batch=null,flight=null,generation=0,evicted=0
  const notify=()=>{for(const listener of listeners){try{listener()}catch{/* El diagnóstico no debe romper el kiosco. */}}}
  function append(session,type,details={},location=context) {
    if(!session)return null
    const event={schema_version:1,event_id:id(),session_id:session.id,sequence:++session.sequence,occurred_at:new Date(now()).toISOString(),elapsed_ms:Math.max(0,now()-session.started_ms),type,...location,...details}
    session.events.push(event);pending.add(event.event_id)
    if(session.events.length>maxEvents){const removed=session.events.shift();pending.delete(removed.event_id);session.dropped++}
    notify();return event
  }
  function end(reason='logout') {
    if(!active)return
    reason=['logout','inactivity','expired','page_exit','replaced'].includes(reason)?reason:'logout'
    const session=active
    append(session,'session.end',{reason})
    session.ended_at=new Date(now()).toISOString();session.reason=reason;active=null;notify()
  }
  function start(screen='dashboard',initialStep=defaultSteps[screen]||'main') {
    end('replaced')
    context={screen:has(screens,screen)?screen:'dashboard',step:steps.has(initialStep)?initialStep:'main',overlay:''}
    const session={id:id(),started_at:new Date(now()).toISOString(),started_ms:now(),ended_at:null,reason:null,sequence:0,dropped:0,events:[]}
    sessions.push(session);active=session
    while(sessions.length>maxSessions){const removed=sessions.shift();for(const event of removed.events)pending.delete(event.event_id);evicted++}
    append(session,'session.start');append(session,'screen.enter');return session.id
  }
  function screen(name,step=defaultSteps[name]||'main') {
    if(!active||!has(screens,name)||!steps.has(step))return
    if(context.screen===name&&context.step===step)return
    const previous={...context};context={screen:name,step,overlay:''}
    append(active,'screen.leave',{},previous);append(active,'screen.enter')
  }
  function step(name,value) {if(active&&context.screen===name)screen(name,value)}
  function overlay(value) {
    if(!active||!overlays.has(value)||context.overlay===value)return
    const previous=context.overlay;context={...context,overlay:value}
    append(active,'overlay.change',{previous_overlay:previous})
  }
  function interaction(action,{input='programmatic',x,y,index}={}) {
    if(!active)return
    const details={action:has(actions,action)?action:'control.unmapped',input:['touch','mouse','pen','keyboard','scanner','programmatic'].includes(input)?input:'programmatic'}
    if(['touch','mouse','pen'].includes(details.input)&&Number.isFinite(x)&&Number.isFinite(y))details.position={x:Math.round(Math.max(0,Math.min(1,x))*1000)/1000,y:Math.round(Math.max(0,Math.min(1,y))*1000)/1000}
    if(Number.isInteger(index)&&index>=0&&index<1000)details.item_index=index
    append(active,'interaction',details)
  }
  function beginOperation(name) {
    if(!active||!operationNames.has(name))return ()=>{}
    const session=active,location={...context},operation_id=id(),started=now()
    append(session,'operation.start',{operation:name,operation_id},location)
    let finished=false
    return (outcome,status=0)=>{
      if(finished||!sessions.includes(session))return
      finished=true
      append(session,'operation.end',{operation:name,operation_id,outcome:outcomes.has(outcome)?outcome:'error',http_status:Number.isInteger(status)&&status>=100&&status<=599?status:0,duration_ms:Math.max(0,now()-started),after_session_end:!!session.ended_at},location)
    }
  }
  function snapshot(){return copy({mode:transport?'adapter':'memory',active_session:active?.id||null,pending:pending.size,evicted_sessions:evicted,sessions})}
  function clear(){if(active)return false;generation++;sessions.length=0;pending.clear();batch=null;flight=null;evicted=0;notify();return true}
  function setTransport(adapter){if(flight)throw new Error('Hay un envío en curso.');if(adapter!==null&&typeof adapter!=='function')throw new TypeError('Se requiere una función de transporte.');transport=adapter;notify()}
  function flush() {
    if(!transport)return Promise.resolve({status:'disconnected'})
    if(flight)return flight
    if(!batch){const events=sessions.flatMap(s=>s.events).filter(e=>pending.has(e.event_id)).slice(0,10);if(!events.length)return Promise.resolve({status:'empty'});batch={schema_version:1,batch_id:id(),events:copy(events)}}
    const current=batch,epoch=generation,controller=new AbortController()
    let timer
    flight=(async()=>{
      try{
        const result=await Promise.race([
          Promise.resolve().then(()=>transport(copy(current),{signal:controller.signal})),
          new Promise((_,reject)=>{timer=setTimeout(()=>{controller.abort();reject(new Error('trace_timeout'))},timeout)}),
        ])
        const accepted=result?.accepted_event_ids
        if(!Array.isArray(accepted)||accepted.some(value=>!current.events.some(e=>e.event_id===value)))throw new Error('trace_invalid_ack')
        if(epoch!==generation)return {status:'cleared'}
        for(const value of accepted)pending.delete(value)
        if(accepted.length)batch=null
        return {status:'accepted',count:new Set(accepted).size}
      }catch{return {status:'pending'}}
      finally{clearTimeout(timer);if(epoch===generation){flight=null;notify()}}
    })()
    return flight
  }
  return {start,end,screen,step,overlay,interaction,beginOperation,snapshot,clear,setTransport,flush,subscribe(listener){listeners.add(listener);return()=>listeners.delete(listener)}}
}

export const interactionTrace=createInteractionTrace()

// Las rutas y resultados son etiquetas de catálogo; nunca se copian body, URL,
// Authorization, errores de servidor, folios, importes o destinatarios.
const routes={'/charges':'charges.load','/payments/history':'history.load','/payments/quote':'payment.quote','/payments/simulate':'payment.simulate','/billing/lookup':'billing.lookup','/billing/invoice':'billing.invoice','/billing/print':'document.print','/billing/email':'email.send','/parking/issue':'parking.issue','/parking/quote':'parking.quote','/parking/reprint':'parking.print','/campus/print-turn':'campus.print','/campus/email':'email.send','/campus/survey':'campus.survey'}
export function beginTraceRequest(path,body){
  const name=path==='/campus/action'&&['procedure','turn','appointment','renew','book','activity','cancel'].includes(body?.action)?'campus.'+body.action:routes[path]
  return interactionTrace.beginOperation(name)
}
export function traceResponseOutcome(data){
  if(data?.printed===false||data?.ticket?.printed===false)return data?.retry_after||data?.ticket?.retry_after?'print_limited':'print_failed'
  return ['accepted','sending','unknown','failed'].includes(data?.status)?data.status:'ok'
}
