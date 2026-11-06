<script setup>
import {onMounted,onUnmounted,ref,watch,nextTick} from 'vue'
import {Clock3} from 'lucide-vue-next'
import {idleState} from '../idle-session'
import {trapFocus} from '../modal-focus'
import {interactionTrace as trace} from '../interaction-trace.js'
const props=defineProps({active:Boolean,extended:Boolean})
const emit=defineEmits(['expired'])
const warning=ref(false),seconds=ref(30),continueButton=ref(null)
watch(warning,value=>trace.overlay(value?'idle':''))
let lastActivity=Date.now(),timer
function resume(){lastActivity=Date.now();warning.value=false}
function activity(){if(!warning.value)lastActivity=Date.now()}
watch(()=>props.active,()=>resume())
watch(warning,async visible=>{if(visible){await nextTick();continueButton.value?.focus()}})
onMounted(()=>{
  window.addEventListener('pointerdown',activity,{passive:true});window.addEventListener('keydown',activity)
  timer=setInterval(()=>{if(!props.active)return;const state=idleState(lastActivity,Date.now(),props.extended?300000:120000);seconds.value=state.seconds;warning.value=state.warning;if(state.expired){resume();emit('expired')}},1000)
})
onUnmounted(()=>{clearInterval(timer);window.removeEventListener('pointerdown',activity);window.removeEventListener('keydown',activity)})
</script>
<template><div v-if="warning" class="kiosk-modal-backdrop idle-backdrop" @keydown="trapFocus"><section class="kiosk-modal session-dialog" role="alertdialog" aria-modal="true" aria-labelledby="idle-title"><Clock3 :size="48"/><h2 id="idle-title">¿SIGUES AQUÍ?</h2><p>Por tu privacidad, volveremos al inicio en <strong>{{seconds}} segundos</strong> y limpiaremos tus datos de la pantalla.</p><button data-trace-action="idle.resume" ref="continueButton" class="btn-primary full" @click="resume">SEGUIR USANDO EL KIOSCO</button><button data-trace-action="session.exit" class="btn-outline full" @click="emit('expired');resume()">FINALIZAR AHORA</button></section></div></template>
