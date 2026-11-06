<script setup>
import {computed, nextTick, onMounted, onUnmounted, ref, watch} from 'vue'
import {ArrowLeft, ArrowRight, Check, Clock3, LoaderCircle, ReceiptText, RotateCcw, Trash2, Wallet} from 'lucide-vue-next'
import {request} from '../api'
import {interactionTrace as trace} from '../interaction-trace.js'
import {orderedCharges, addNext, removeLast} from '../payment-order'
import ReceiptCard from './ReceiptCard.vue'
import PrintActions from './PrintActions.vue'
const props = defineProps({token:String, charges:Array, selection:{type:Array,default:()=>[]}})
const emit = defineEmits(['expired', 'updated', 'billing', 'back', 'finish', 'selection', 'locked', 'completed'])
const selected = ref([...props.selection]), stage = ref('select'), error = ref(''), payment = ref(null), printResult = ref(null)
watch(stage,step=>trace.step('charges',step),{immediate:true})
const controller = new AbortController()
const operationId = ref('')
const loading = ref(true)
const cartList = ref(null)
const quote = ref(null)
const now = new Date()
const today = `${now.getFullYear()}-${String(now.getMonth()+1).padStart(2,'0')}-${String(now.getDate()).padStart(2,'0')}`
const overdue = computed(() => ordered.value.filter(c => c.fechaVencimiento < today).length)
const balance = computed(() => ordered.value.reduce((sum,c)=>sum+c.restante,0))
watch(selected, async value => { emit('selection',value);await nextTick(); if(cartList.value) cartList.value.scrollTop = cartList.value.scrollHeight })
watch(stage, value=>emit('locked',value==='processing'))
onUnmounted(() => {controller.abort();emit('locked',false)})
const ordered = computed(() => orderedCharges(props.charges))
const cart = computed(() => ordered.value.filter(c => selected.value.includes(c.id)))
const available = computed(() => ordered.value.filter(c => !selected.value.includes(c.id)))
const total = computed(() => cart.value.reduce((sum,c) => sum+c.restante,0))
const locked = computed(() => loading.value || stage.value === 'processing' || !!operationId.value)
const money = n => new Intl.NumberFormat('es-MX',{style:'currency',currency:'MXN'}).format(n)
watch(() => props.charges, () => {
  if(stage.value!=='select'||operationId.value)return
  let length=0
  while(length<selected.value.length&&selected.value[length]===ordered.value[length]?.id)length++
  if(length!==selected.value.length)selected.value=selected.value.slice(0,length)
})
function goBack(){if(stage.value==='processing')return;if(stage.value==='review')stage.value='select';else emit('back')}
defineExpose({goBack})
function add(id) { if (!locked.value) selected.value = addNext(ordered.value, selected.value, id) }
function remove(id) { if (!locked.value) selected.value = removeLast(selected.value, id) }
function clear() { if (!locked.value) { selected.value = []; error.value = '' } }
async function refreshCharges() {
  loading.value = true
  try {
    const response = await request('/charges', {token:props.token, signal:controller.signal})
    if (!controller.signal.aborted) emit('updated', response.conceptos)
  } catch (e) {
    if (controller.signal.aborted) return
    if (e.status === 401) emit('expired')
    else error.value = e.message
  } finally { if (!controller.signal.aborted) loading.value = false }
}
onMounted(refreshCharges)
async function review() {
  if(!selected.value.length || loading.value)return
  loading.value=true;error.value=''
  try {
    const response=await request('/payments/quote',{method:'POST',token:props.token,body:{concept_ids:selected.value},signal:controller.signal})
    if(!controller.signal.aborted){quote.value=response;stage.value='review';window.scrollTo(0,0)}
  }catch(e){if(controller.signal.aborted)return;if(e.status===401)emit('expired');else{error.value=e.message;if(e.status===400)await refreshCharges()}}
  finally{if(!controller.signal.aborted)loading.value=false}
}
async function pay() {
  if (!selected.value.length || loading.value || stage.value === 'processing') return
  operationId.value ||= crypto.randomUUID()
  error.value = ''; stage.value = 'processing'
  try {
    const response = await request('/payments/simulate', {method:'POST',token:props.token,body:{concept_ids:selected.value, request_id:operationId.value},signal:controller.signal})
    // Tiempo breve para que el estado de simulación sea perceptible, sin datos bancarios.
    await new Promise(resolve => setTimeout(resolve, 700))
    if (controller.signal.aborted) return
    payment.value = response.payment; printResult.value = response; stage.value = 'receipt'
    emit('updated', response.conceptos);emit('completed')
    selected.value = []; operationId.value = ''
  } catch (e) {
    if (controller.signal.aborted) return
    if (e.status === 401) { emit('expired'); return }
    error.value = e.message; stage.value = 'select'
    if (e.status === 400) { operationId.value = ''; await refreshCharges() }
  }
}
</script>
<template>
  <section class="payment-flow">
    <ol class="flow-steps" aria-label="Progreso del pago"><li :class="{active:stage==='select'}"><span>1</span> SELECCIONA</li><li :class="{active:['review','processing'].includes(stage)}"><span>2</span> REVISA Y CONFIRMA</li><li :class="{active:stage==='receipt'}"><span>3</span> RECIBE TU COMPROBANTE</li></ol>
    <template v-if="stage === 'select'">
      <p v-if="error" class="flow-error" role="alert">{{error}}</p>
      <p v-if="loading" class="muted" role="status">Actualizando conceptos pendientes…</p>
      <p v-if="operationId" class="notice">La respuesta quedó pendiente. Reintenta la misma operación para recuperar el comprobante sin duplicar el cobro demo.</p>
      <div class="payment-layout">
        <div class="available-charges">
          <div class="heading"><div><span class="eyebrow red">SERVICIOS Y PAGOS</span><h1>ELIGE TUS CONCEPTOS</h1><p class="subtitle">Agrega en orden de vencimiento, del más antiguo al más reciente.</p></div></div>
          <div class="balance-strip"><span><b>{{ordered.length}}</b> pendientes</span><span><b>{{overdue}}</b> vencidos</span><span>Saldo demo <b>{{money(balance)}}</b></span></div>
          <div class="section-label"><span>CONCEPTOS PENDIENTES</span><b>{{available.length}}</b></div>
          <div class="available-scroll">
          <article v-for="(c,index) in available" :key="c.id" class="pay-charge" :class="{'next-charge':index === 0, 'waiting-charge':index > 0}" :data-concept-id="c.id">
            <div class="pay-charge-head"><span class="pill">{{c.grupo}}</span><span class="charge-due" :class="{'is-overdue':c.fechaVencimiento<today}"><Clock3 :size="14"/> {{c.fechaVencimiento<today?'Venció':'Vence'}} {{c.fechaVencimiento}}</span></div>
            <h2>{{c.nombre}}</h2><p>Ciclo {{c.ciclo}} · Periodo {{c.periodo}}</p>
            <div class="pay-charge-bottom"><strong>{{money(c.restante)}}</strong><button data-trace-action="payment.add" class="btn-primary" :disabled="index !== 0 || locked" @click="add(c.id)" :aria-label="`Agregar concepto ${c.id}`">{{index === 0?'AGREGAR':'AGREGA EL ANTERIOR'}} <ArrowRight :size="18"/></button></div>
          </article>
          <div v-if="!available.length" class="empty-payments"><Check :size="42"/><h2>{{cart.length?'Todos los conceptos están en tu selección':'SIN CARGOS PENDIENTES'}}</h2><p>{{cart.length?'Revisa el resumen de la derecha para continuar.':'Los conceptos pagados en la demo ya están registrados.'}}</p></div>
          </div>
        </div>
        <aside class="payment-cart" aria-label="Conceptos seleccionados">
          <div class="cart-heading"><Wallet :size="23"/><h2>TU SELECCIÓN</h2><span>{{cart.length}}</span></div>
          <p class="cart-guidance">Para devolver conceptos, empieza por el último agregado.</p>
          <div v-if="!cart.length" class="cart-empty"><ReceiptText :size="43"/><p>Los conceptos que agregues aparecerán aquí.</p></div>
          <ol v-else ref="cartList" class="cart-items"><li v-for="(c,index) in cart" :key="c.id" :data-cart-id="c.id"><div><span class="cart-number">{{index+1}}</span><h3>{{c.nombre}}</h3></div><p>Vence {{c.fechaVencimiento}}</p><div class="cart-item-bottom"><b>{{money(c.restante)}}</b><button data-trace-action="payment.remove" @click="remove(c.id)" :disabled="index !== cart.length-1 || locked" :aria-label="`Devolver concepto ${c.id}`" :title="index === cart.length-1?'Regresar a pendientes':'Devuelve primero el último concepto'"><RotateCcw :size="16"/> Devolver</button></div></li></ol>
          <div class="cart-footer"><div class="cart-total"><span>TOTAL DEMO</span><strong>{{money(total)}}</strong><small>MXN · {{cart.length}} concepto(s)</small></div><button :data-trace-action="operationId?'payment.retry':'payment.review'" class="btn-primary full" @click="operationId?pay():review()" :disabled="!cart.length || loading">{{operationId?'REINTENTAR OPERACIÓN':'CONTINUAR'}} <ArrowRight :size="20"/></button><button data-trace-action="payment.clear" class="clear-cart" @click="clear" :disabled="!cart.length || locked"><Trash2 :size="16"/> Cancelar toda la selección</button><p class="demo-note">Primero revisarás el resumen. No se cobra dinero real.</p></div>
        </aside>
      </div>
    </template>
    <div v-else-if="stage==='review'" class="payment-review"><button data-trace-action="payment.edit" class="back" @click="stage='select'"><ArrowLeft :size="18"/> MODIFICAR SELECCIÓN</button><h1>REVISA TU PAGO</h1><p>Confirma los conceptos y el total antes de continuar.</p><div class="review-lines"><div v-for="c in quote.conceptos" :key="c.id"><span><b>{{c.nombre}}</b><small>Vencimiento {{c.fechaVencimiento}}</small></span><strong>{{money(c.restante)}}</strong></div></div><div class="review-total"><span>TOTAL DEMO · {{quote.conceptos.length}} CONCEPTOS</span><strong>{{money(quote.total)}}</strong></div><div class="notice">Operación de prueba. Se registrará un pago simulado y se generará un comprobante. No ingreses tarjeta ni datos bancarios.</div><button data-trace-action="payment.confirm" class="btn-primary full" @click="pay">CONFIRMAR PAGO DEMO <Check :size="20"/></button></div>
    <div v-else-if="stage === 'processing'" class="processing-payment" role="status" aria-live="polite"><div class="processing-icon"><LoaderCircle :size="54" class="spin"/></div><span class="eyebrow red">OPERACIÓN DE DEMOSTRACIÓN</span><h1>SIMULANDO EL COBRO</h1><p>Estamos registrando los conceptos y preparando tu comprobante.</p><span class="demo-stamp">SIN COBRO REAL</span><p class="muted">No necesitas tarjeta ni datos bancarios.</p></div>
    <div v-else class="payment-complete"><div class="success-heading no-print"><span><Check :size="30"/></span><div><h1>PAGO DEMO COMPLETADO</h1><p>Tu comprobante quedó guardado. También podrás recuperarlo en Mis comprobantes.</p></div></div><div class="document-layout"><ReceiptCard :document="payment"/><div class="document-options no-print"><h2>RECIBE TU COMPROBANTE</h2><p>Retira el ticket del kiosco o recíbelo por correo. Conserva el QR para facturar.</p><PrintActions :document="payment" :result="printResult"/><button data-trace-action="nav.billing" class="btn-primary full" @click="emit('billing', payment.code)">IR A FACTURAR <ArrowRight :size="18"/></button><button data-trace-action="session.exit" class="btn-outline full" @click="emit('finish')">FINALIZAR Y SALIR</button><button data-trace-action="payment.another" class="clear-cart" @click="stage = 'select'">HACER OTRO PAGO DEMO</button></div></div></div>
  </section>
</template>
