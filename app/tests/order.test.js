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
