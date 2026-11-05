<script setup>
import {computed, nextTick, onMounted, onUnmounted, ref, watch} from 'vue'
import {ArrowLeft, ArrowRight, Check, Clock3, LoaderCircle, ReceiptText, RotateCcw, Trash2, Wallet} from 'lucide-vue-next'
import {request} from '../api'
import {orderedCharges, addNext, removeLast} from '../payment-order'
import ReceiptCard from './ReceiptCard.vue'
import PrintActions from './PrintActions.vue'
const props = defineProps({token:String, charges:Array})
const emit = defineEmits(['expired', 'updated', 'billing', 'back'])
const selected = ref([]), stage = ref('select'), error = ref(''), payment = ref(null), printResult = ref(null)
const controller = new AbortController()
const operationId = ref('')
const loading = ref(true)
const cartList = ref(null)
watch(selected, async () => { await nextTick(); if(cartList.value) cartList.value.scrollTop = cartList.value.scrollHeight })
onUnmounted(() => controller.abort())
const ordered = computed(() => orderedCharges(props.charges))
const cart = computed(() => ordered.value.filter(c => selected.value.includes(c.id)))
const available = computed(() => ordered.value.filter(c => !selected.value.includes(c.id)))
const total = computed(() => cart.value.reduce((sum,c) => sum+c.restante,0))
const locked = computed(() => loading.value || stage.value === 'processing' || !!operationId.value)
const money = n => new Intl.NumberFormat('es-MX',{style:'currency',currency:'MXN'}).format(n)
watch(() => props.charges, () => { if (stage.value === 'select' && !operationId.value) selected.value = [] })
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
    emit('updated', response.conceptos)
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
    <template v-if="stage === 'select'">
      <p v-if="error" class="flow-error" role="alert">{{error}}</p>
      <p v-if="loading" class="muted" role="status">Actualizando conceptos pendientes…</p>
      <p v-if="operationId" class="notice">La respuesta quedó pendiente. Reintenta la misma operación para recuperar el comprobante sin duplicar el cobro demo.</p>
      <div class="payment-layout">
        <div class="available-charges">
          <div class="heading"><div><span class="eyebrow red">SERVICIOS Y PAGOS</span><h1>ELIGE TUS CONCEPTOS</h1><p class="subtitle">Agrega en orden de vencimiento, del más antiguo al más reciente.</p></div><button class="back" @click="emit('back')"><ArrowLeft :size="18"/> Volver</button></div>
          <div class="section-label"><span>CONCEPTOS PENDIENTES</span><b>{{available.length}}</b></div>
          <article v-for="(c,index) in available" :key="c.id" class="pay-charge" :class="{'next-charge':index === 0, 'waiting-charge':index > 0}" :data-concept-id="c.id">
            <div class="pay-charge-head"><span class="pill">{{c.grupo}}</span><span class="charge-due"><Clock3 :size="14"/> {{c.fechaVencimiento}}</span></div>
            <h2>{{c.nombre}}</h2><p>Ciclo {{c.ciclo}} · Periodo {{c.periodo}}</p>
            <div class="pay-charge-bottom"><strong>{{money(c.restante)}}</strong><button class="btn-primary" :disabled="index !== 0 || locked" @click="add(c.id)" :aria-label="`Agregar concepto ${c.id}`">{{index === 0?'AGREGAR':'AGREGA EL ANTERIOR'}} <ArrowRight :size="18"/></button></div>
          </article>
          <div v-if="!available.length" class="empty-payments"><Check :size="42"/><h2>{{cart.length?'Todos los conceptos están en tu selección':'SIN CARGOS PENDIENTES'}}</h2><p>{{cart.length?'Revisa el resumen de la derecha para continuar.':'Los conceptos pagados en la demo ya están registrados.'}}</p></div>
        </div>
        <aside class="payment-cart" aria-label="Conceptos seleccionados">
          <div class="cart-heading"><Wallet :size="23"/><h2>TU SELECCIÓN</h2><span>{{cart.length}}</span></div>
          <p class="cart-guidance">Para devolver conceptos, empieza por el último agregado.</p>
          <div v-if="!cart.length" class="cart-empty"><ReceiptText :size="43"/><p>Los conceptos que agregues aparecerán aquí.</p></div>
          <ol v-else ref="cartList" class="cart-items"><li v-for="(c,index) in cart" :key="c.id" :data-cart-id="c.id"><div><span class="cart-number">{{index+1}}</span><h3>{{c.nombre}}</h3></div><p>Vence {{c.fechaVencimiento}}</p><div class="cart-item-bottom"><b>{{money(c.restante)}}</b><button @click="remove(c.id)" :disabled="index !== cart.length-1 || locked" :aria-label="`Devolver concepto ${c.id}`" :title="index === cart.length-1?'Regresar a pendientes':'Devuelve primero el último concepto'"><RotateCcw :size="16"/> Devolver</button></div></li></ol>
          <div class="cart-footer"><div class="cart-total"><span>TOTAL DEMO</span><strong>{{money(total)}}</strong><small>MXN · {{cart.length}} concepto(s)</small></div><button class="btn-primary full" @click="pay" :disabled="!cart.length || loading">{{operationId?'REINTENTAR OPERACIÓN':'CONTINUAR'}} <ArrowRight :size="20"/></button><button class="clear-cart" @click="clear" :disabled="!cart.length || locked"><Trash2 :size="16"/> Cancelar toda la selección</button><p class="demo-note">Se simulará el cobro y se generará un ticket con QR. No se cobra dinero real.</p></div>
        </aside>
      </div>
    </template>
    <div v-else-if="stage === 'processing'" class="processing-payment" role="status" aria-live="polite"><div class="processing-icon"><LoaderCircle :size="54" class="spin"/></div><span class="eyebrow red">OPERACIÓN DE DEMOSTRACIÓN</span><h1>SIMULANDO EL COBRO</h1><p>Estamos registrando los conceptos y preparando tu comprobante.</p><span class="demo-stamp">SIN COBRO REAL</span><p class="muted">No necesitas tarjeta ni datos bancarios.</p></div>
    <div v-else class="payment-complete"><div class="success-heading no-print"><span><Check :size="30"/></span><div><h1>PAGO DEMO COMPLETADO</h1><p>Tu comprobante quedó guardado. Conserva el QR para facturar en este kiosco.</p></div></div><div class="document-layout"><ReceiptCard :document="payment"/><div class="document-options no-print"><h2>¿QUÉ SIGUE?</h2><p>Escanea el QR del ticket con el lector del kiosco para abrir la pantalla de facturación de prueba.</p><PrintActions :document="payment" :result="printResult"/><button class="btn-primary full" @click="emit('billing', payment.code)">IR A FACTURAR <ArrowRight :size="18"/></button><button class="btn-outline full" @click="stage = 'select'">VOLVER A CONCEPTOS</button></div></div></div>
  </section>
</template>
