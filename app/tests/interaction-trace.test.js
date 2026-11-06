import {test} from 'node:test'
import assert from 'node:assert/strict'
import {readFile} from 'node:fs/promises'
import {parse} from '@vue/compiler-sfc'
import {parse as parseTemplate} from '@vue/compiler-dom'
import {createInteractionTrace,traceResponseOutcome} from '../src/interaction-trace.js'
import {actions} from '../src/trace-catalog.js'

function fixture(options={}){let clock=1700000000000,sequence=0;return {trace:createInteractionTrace({now:()=>clock,id:()=>`test-id-${++sequence}`,...options}),tick(ms=50){clock+=ms}}}

test('tracks only an authenticated session and gives events strict sequence numbers',()=>{
  const {trace,tick}=fixture()
  trace.interaction('nav.charges');assert.equal(trace.snapshot().sessions.length,0)
  const id=trace.start();trace.interaction('nav.charges',{input:'touch',x:.12345,y:.5});tick();trace.screen('charges','select');trace.interaction('payment.add');trace.end()
  const before=trace.snapshot();trace.interaction('nav.home');assert.deepEqual(trace.snapshot(),before)
  const events=before.sessions[0].events
  assert.equal(before.active_session,null)
  assert.deepEqual(events.map(e=>e.sequence),events.map((_,i)=>i+1))
  assert.ok(events.every(e=>e.session_id===id))
  assert.deepEqual(events[2].position,{x:.123,y:.5})
  assert.equal(events.at(-1).type,'session.end')
})

test('metadata is allowlisted and snapshots cannot mutate the retained trace',()=>{
  const {trace}=fixture();trace.start('202210')
  trace.interaction('secret@example.invalid',{input:'pin=1234',x:.4,y:.4,password:'1234',token:'secret',email:'secret@example.invalid',index:'folio-123'})
  trace.screen('secret-route');trace.overlay('secret@example.invalid');trace.end({password:'secret'})
  const json=JSON.stringify(trace.snapshot())
  for(const secret of ['202210','1234','secret','password','token','email'])assert.ok(!json.includes(secret),secret)
  const snapshot=trace.snapshot();snapshot.sessions[0].events[0].screen='mutated'
  assert.equal(trace.snapshot().sessions[0].events[0].screen,'dashboard')
  assert.equal(snapshot.sessions[0].events[2].action,'control.unmapped')
  assert.equal(snapshot.sessions[0].reason,'logout')
})

test('late operations remain in the originating session and record outcome once',()=>{
  const {trace,tick}=fixture();const first=trace.start();trace.screen('charges','review')
  const finish=trace.beginOperation('payment.simulate');tick();trace.end();const second=trace.start();tick();finish('ok',200);finish('error',500)
  const sessions=trace.snapshot().sessions
  const result=sessions[0].events.at(-1)
  assert.equal(result.session_id,first);assert.equal(result.after_session_end,true);assert.equal(result.screen,'charges');assert.equal(result.duration_ms,100)
  assert.equal(sessions[1].id,second);assert.equal(sessions[1].events.length,2)
})

test('unknown operations and duplicate screens are ignored; overlays carry no form values',()=>{
  const {trace}=fixture();trace.start();trace.screen('dashboard');trace.beginOperation('secret')('error',500)
  assert.equal(trace.snapshot().sessions[0].events.length,2)
  trace.overlay('email.review');trace.overlay('');trace.end('inactivity')
  assert.equal(trace.snapshot().sessions[0].events.at(-1).reason,'inactivity')
  assert.equal(trace.snapshot().sessions[0].events[3].previous_overlay,'email.review')
})

test('bounded memory reports dropped events and evicted sessions',()=>{
  const {trace}=fixture({maxSessions:2,maxEvents:4});trace.start();for(let i=0;i<8;i++)trace.interaction('payment.add');trace.end()
  assert.equal(trace.snapshot().sessions[0].events.length,4);assert.equal(trace.snapshot().sessions[0].dropped,7)
  trace.start();trace.end();trace.start()
  assert.equal(trace.snapshot().sessions.length,2);assert.equal(trace.snapshot().evicted_sessions,1);assert.ok(trace.snapshot().pending<=8)
  assert.equal(trace.clear(),false);trace.end();assert.equal(trace.clear(),true);assert.equal(trace.snapshot().sessions.length,0)
})

test('no transport is contacted by default',async()=>{
  const {trace}=fixture();trace.start();assert.deepEqual(await trace.flush(),{status:'disconnected'});assert.equal(trace.snapshot().pending,2)
})

test('failed delivery reuses batch and event IDs and only explicit acknowledgements advance it',async()=>{
  const batches=[];let succeed=false
  const {trace}=fixture({transport:async batch=>{batches.push(batch);if(!succeed)throw new Error('offline');return {accepted_event_ids:batch.events.map(e=>e.event_id)}}})
  trace.start();trace.interaction('nav.charges');trace.end()
  assert.equal((await trace.flush()).status,'pending');succeed=true
  assert.equal((await trace.flush()).count,4);assert.deepEqual(batches[0],batches[1]);assert.equal(trace.snapshot().pending,0)
  assert.equal((await trace.flush()).status,'empty');assert.equal(trace.snapshot().sessions[0].events.length,4)
})

test('concurrent flushing shares one in-flight batch and partial acknowledgement preserves the rest',async()=>{
  let release,calls=0
  const {trace}=fixture({transport:batch=>{calls++;return new Promise(resolve=>release=()=>resolve({accepted_event_ids:[batch.events[0].event_id]}))}})
  trace.start();const a=trace.flush(),b=trace.flush();assert.equal(a,b)
  await Promise.resolve();release();await a;assert.equal(calls,1);assert.equal(trace.snapshot().pending,1)
})

test('invalid acknowledgements and timeout keep events pending',async()=>{
  const {trace}=fixture({timeout:5,transport:async()=>({accepted_event_ids:['not-in-batch']})});trace.start()
  assert.equal((await trace.flush()).status,'pending');assert.equal(trace.snapshot().pending,2)
  let signal
  trace.setTransport((_batch,options)=>{signal=options.signal;return new Promise(()=>{})})
  assert.equal((await trace.flush()).status,'pending');assert.equal(signal.aborted,true);assert.equal(trace.snapshot().pending,2)
})

test('clearing after logout cannot let an old acknowledgement affect a new session',async()=>{
  let release
  const {trace}=fixture({transport:batch=>new Promise(resolve=>release=()=>resolve({accepted_event_ids:batch.events.map(e=>e.event_id)}))})
  trace.start();trace.end();const flight=trace.flush();await Promise.resolve();trace.clear();trace.start();release()
  assert.equal((await flight).status,'cleared');assert.equal(trace.snapshot().pending,2)
})

test('successful HTTP can still mean print limited or uncertain email delivery',()=>{
  assert.equal(traceResponseOutcome({printed:false,retry_after:10}),'print_limited')
  assert.equal(traceResponseOutcome({ticket:{printed:false}}),'print_failed')
  assert.equal(traceResponseOutcome({status:'unknown'}),'unknown')
  assert.equal(traceResponseOutcome({status:'secret',email:'hidden'}),'ok')
})

test('all public interactive controls have a stable trace action or an explicit privacy exclusion',async()=>{
  for(const name of ['App','components/KioskNavigation','components/PaymentFlow','components/BillingFlow','components/PaymentHistory','components/CampusPortal','components/EmailDelivery','components/PrintActions','components/IdleSession','components/TouchInput']){
    const {descriptor}=parse(await readFile(new URL(`../src/${name}.vue`,import.meta.url),'utf8'))
    const ast=parseTemplate(descriptor.template.content)
    function walk(node){
      if(node.type===1&&['button','a','input','select','textarea'].includes(node.tag)){
        const privacy=node.props.some(p=>p.name==='data-trace-private')
        const action=node.props.find(p=>p.name==='data-trace-action'||p.type===7&&p.arg?.content==='data-trace-action')
        assert.ok(privacy||action,`${name}: ${node.loc.source.slice(0,90)}`)
        if(action?.type===6)assert.ok(Object.hasOwn(actions,action.value.content),action.value.content)
        if(['input','textarea','select'].includes(node.tag))assert.ok(privacy)
      }
      for(const child of node.children||[])walk(child)
    }walk(ast)
  }
})
