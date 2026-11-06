import {test} from 'node:test'
import assert from 'node:assert/strict'
import {blocksKioskShortcut,shouldLockKiosk} from '../src/kiosk-guards.js'

test('desktop is locked in development and production; operator web stays usable',()=>{
  assert.equal(shouldLockKiosk({desktop:true,production:false}),true)
  assert.equal(shouldLockKiosk({desktop:true,admin:true}),true)
  assert.equal(shouldLockKiosk({production:true}),true)
  assert.equal(shouldLockKiosk({production:true,admin:true}),false)
  assert.equal(shouldLockKiosk({production:false}),false)
})

test('blocks zoom, inspector and browser operations across keyboard layouts',()=>{
  for(const event of [
    ...['+','=','-','_','0'].map(key=>({key,ctrlKey:true})),
    {key:'Unidentified',code:'NumpadAdd',ctrlKey:true},
    {key:'Unidentified',code:'NumpadSubtract',metaKey:true},
    ...['I','J','C','K'].map(key=>({key,ctrlKey:true,shiftKey:true})),
    {key:'i',metaKey:true,altKey:true},
    ...['F5','F11','F12','ContextMenu'].map(key=>({key})),
    {key:'F10',shiftKey:true},
    ...['r','p','s','u','f','o','l'].map(key=>({key,ctrlKey:true})),
    {key:'ArrowLeft',altKey:true},{key:'ArrowRight',altKey:true},
    {key:'Backspace'},
  ])assert.equal(blocksKioskShortcut(event),true,JSON.stringify(event))
})

test('preserves input, scanners, text editing, dialogs and operator exit',()=>{
  for(const event of [
    ...['a','1','-','+','Enter','Tab','Escape','ArrowLeft','ArrowRight'].map(key=>({key})),
    ...['a','c','v','x','z','y'].map(key=>({key,ctrlKey:true})),
    {key:'F4',altKey:true},
    {key:'@',ctrlKey:true,altKey:true,getModifierState:()=>true},
    {key:'i',ctrlKey:true,shiftKey:true,isComposing:true},
    {key:'Backspace',target:{closest:()=>({tagName:'INPUT'})}},
  ])assert.equal(blocksKioskShortcut(event),false,JSON.stringify(event))
})
