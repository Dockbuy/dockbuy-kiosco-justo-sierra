import {test} from 'node:test'
import assert from 'node:assert/strict'
import {readFile} from 'node:fs/promises'
const source=await readFile(new URL('../src/api.js',import.meta.url),'utf8')
const {request}=await import('data:text/javascript;base64,'+Buffer.from(source.replaceAll('import.meta.env','({DEV:false})').replace("'./interaction-trace.js'",JSON.stringify(new URL('../src/interaction-trace.js',import.meta.url).href))).toString('base64'))
test('production API uses localhost and non-JSON is rejected',async()=>{
  const original=globalThis.fetch
  try{
    let called
    globalThis.fetch=async url=>{called=url;return new Response('<html>fallback</html>',{status:200})}
    await assert.rejects(request('/health'),/respuesta inválida/)
    assert.equal(called,'http://127.0.0.1:8787/api/health')
  }finally{globalThis.fetch=original}
})
test('HTTP errors retain status for session recovery',async()=>{
  const original=globalThis.fetch
  try{
    globalThis.fetch=async()=>new Response(JSON.stringify({error:'Sesión vencida'}),{status:401})
    await assert.rejects(request('/charges'),e=>e.status===401&&e.message==='Sesión vencida')
  }finally{globalThis.fetch=original}
})

test('body-less logout sends JSON and preserves the bearer token',async()=>{
  const original=globalThis.fetch
  try{
    let called
    globalThis.fetch=async(_url,options)=>{called=options;return new Response(JSON.stringify({ok:true}),{status:200})}
    await request('/auth/logout',{method:'POST',token:'session-test'})
    assert.equal(called.headers['Content-Type'],'application/json')
    assert.equal(called.headers.Authorization,'Bearer session-test')
    assert.equal(called.body,'{}')
  }finally{globalThis.fetch=original}
})
test('caller cancellation remains distinguishable from timeout',async()=>{
  const original=globalThis.fetch
  try{
    globalThis.fetch=async(_url,{signal})=>new Promise((_resolve,reject)=>{
      const cancel=()=>reject(new DOMException('Cancelled','AbortError'))
      if(signal.aborted)cancel();else signal.addEventListener('abort',cancel,{once:true})
    })
    const abort=new AbortController();abort.abort()
    await assert.rejects(request('/charges',{signal:abort.signal}),e=>e.name==='AbortError')
    await assert.rejects(request('/health',{timeout:5}),/tardó demasiado/)
  }finally{globalThis.fetch=original}
})
