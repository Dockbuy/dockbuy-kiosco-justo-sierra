import {test} from 'node:test'
import assert from 'node:assert/strict'
import {orderedCharges,addNext,removeLast} from '../src/payment-order.js'
const charges=[{id:36,fechaVencimiento:'2026-11-30'},{id:45,fechaVencimiento:'2026-11-01'},{id:55,fechaVencimiento:'2027-02-01'}]
test('sort by due date without mutating API data',()=>{
  assert.deepEqual(orderedCharges(charges).map(c=>c.id),[45,36,55])
  assert.equal(charges[0].id,36)
})
test('only next concept can be added; only last can be returned',()=>{
  assert.deepEqual(addNext(charges,[],36),[])
  const first=addNext(charges,[],45)
  assert.deepEqual(addNext(charges,first,55),[45])
  const second=addNext(charges,first,36)
  assert.deepEqual(removeLast(second,45),[45,36])
  assert.deepEqual(removeLast(second,36),[45])
  assert.deepEqual(addNext(charges,second,36),[45,36])
})

test('SIPAA scoped IDs keep authoritative tie order and ordered undo',()=>{
  const data=[{id:'sipaa:129:contract:9:10',fechaVencimiento:'2026-12-31',orden:1},
    {id:'sipaa:129:contract:9:2',fechaVencimiento:'2026-12-31',orden:0}]
  const ordered=orderedCharges(data)
  assert.equal(ordered[0].id,'sipaa:129:contract:9:2')
  assert.deepEqual(addNext(data,[],ordered[1].id),[])
  assert.deepEqual(removeLast(ordered.map(c=>c.id),ordered[0].id),ordered.map(c=>c.id))
})
