<script setup>
import {onMounted,onUnmounted,ref,watch} from 'vue'
import {ArrowLeft,ReceiptText,ArrowRight} from 'lucide-vue-next'
import {request} from '../api'
import {interactionTrace as trace} from '../interaction-trace.js'
import ReceiptCard from './ReceiptCard.vue'
import PrintActions from './PrintActions.vue'
const props=defineProps({token:String})
const emit=defineEmits(['back','expired','billing','finish'])
const items=ref([]),selected=ref(null),error=ref(''),busy=ref(true)
watch(selected,value=>trace.step('history',value?'document':'list'),{immediate:true})
const controller=new AbortController()
const money=n=>new Intl.NumberFormat('es-MX',{style:'currency',currency:'MXN'}).format(n)
async function load(){busy.value=true;error.value='';try{const response=await request('/payments/history',{token:props.token,signal:controller.signal});if(!controller.signal.aborted)items.value=response.payments}catch(e){if(controller.signal.aborted)return;if(e.status===401)emit('expired');else error.value=e.message}finally{if(!controller.signal.aborted)busy.value=false}}
onMounted(load);onUnmounted(()=>controller.abort())
function goBack(){if(selected.value)selected.value=null;else emit('back')}
defineExpose({goBack})
</script>
<template>
  <section class="history-flow"><span class="eyebrow red">TUS DOCUMENTOS</span><h1>MIS COMPROBANTES</h1><p class="subtitle">Recupera, imprime o envía por correo tus últimos 30 pagos demo.</p>
    <p v-if="error" class="flow-error" role="alert">{{error}} <button data-trace-action="history.retry" class="btn-outline" @click="load">REINTENTAR</button></p><p v-if="busy" role="status">Consultando comprobantes…</p>
    <div v-else-if="selected" class="document-layout"><ReceiptCard :document="selected"/><div class="document-options"><h2>RECUPERAR COMPROBANTE</h2><p>Este es el mismo documento guardado al realizar tu pago demo.</p><PrintActions :key="selected.code" :document="selected"/><button data-trace-action="nav.billing" class="btn-primary full" @click="emit('billing',selected.code)">FACTURAR ESTE COMPROBANTE <ArrowRight :size="18"/></button><button data-trace-action="session.exit" class="btn-outline full" @click="emit('finish')">FINALIZAR Y SALIR</button></div></div>
    <div v-else-if="!items.length&&!error" class="empty-payments"><ReceiptText :size="44"/><h2>AÚN NO HAY COMPROBANTES</h2><p>Después de un pago demo podrás consultarlo aquí, incluso si no salió el ticket.</p></div>
    <div v-else class="history-list"><button data-trace-action="history.open" v-for="item in items" :key="item.code" class="history-item" @click="selected=item"><span class="history-icon"><ReceiptText :size="28"/></span><span><b>{{new Date(item.issued_at).toLocaleString('es-MX')}}</b><small>{{item.conceptos.length}} conceptos · Pago demo</small><small class="history-code">{{item.code}}</small></span><strong>{{money(item.total)}}</strong><ArrowRight :size="23"/></button></div>
  </section>
</template>
