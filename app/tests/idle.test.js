import {test} from 'node:test'
import assert from 'node:assert/strict'
import {idleState} from '../src/idle-session.js'
test('idle warning precedes clearing and activity renews the session',()=>{
  assert.deepEqual(idleState(0,89999),{warning:false,expired:false,seconds:31})
  assert.deepEqual(idleState(0,90000),{warning:true,expired:false,seconds:30})
  assert.deepEqual(idleState(0,120000),{warning:false,expired:true,seconds:0})
  assert.equal(idleState(100000,120000).warning,false)
})
