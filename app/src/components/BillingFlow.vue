<script setup>
import {onUnmounted, ref, watch} from 'vue'
import {ArrowLeft, Check, FileText, ScanLine} from 'lucide-vue-next'
import {request} from '../api'
import ReceiptCard from './ReceiptCard.vue'
import PrintActions from './PrintActions.vue'
const props = defineProps({code:String, scanVersion:Number})
const emit = defineEmits(['home','back','completed'])
const code = ref(''), payment = ref(null), invoice = ref(null), result = ref(null), error = ref(''), busy = ref(false), keyboard = ref(false)
const keys = ['1234567890','QWERTYUIOP','ASDFGHJKL','ZXCVBNM-']
let controller = new AbortController(), generation = 0
onUnmounted(() => controller.abort())
async function lookup(value = code.value) {
  controller.abort(); controller = new AbortController()
  const current = ++generation, signal = controller.signal
  code.value = value.trim().toUpperCase(); keyboard.value = false
  error.value = ''; payment.value = null; invoice.value = null; result.value = null; busy.value = true
  try {
    const record = await request('/billing/lookup', {method:'POST',body:{code:code.value},signal})
    if (signal.aborted || current !== generation) return
    payment.value = record.payment; invoice.value = record.invoice
  } catch (e) { if (!signal.aborted && current === generation) error.value = e.message }
  finally { if (!signal.aborted && current === generation) busy.value = false }
}
async function generate() {
  if (busy.value || !payment.value) return
  const current = generation, signal = controller.signal
  busy.value = true; error.value = ''
  try {
    const response = await request('/billing/invoice', {method:'POST', body:{code:payment.value.code}, signal})
    if (signal.aborted || current !== generation) return
    invoice.value = response.invoice; result.value = response;emit('completed')
  } catch (e) { if (!signal.aborted && current === generation) error.value = e.message }
  finally { if (!signal.aborted && current === generation) busy.value = false }
}
function another() { controller.abort(); controller = new AbortController(); ++generation; code.value = ''; payment.value = null; invoice.value = null; result.value = null; error.value = ''; busy.value = false }
function key(value) { if (code.value.length < 80) code.value += value }
function goBack(){if(keyboard.value){keyboard.value=false;return}if(payment.value&&!props.code){another();return}emit('back')}
defineExpose({goBack})
watch(() => [props.code, props.scanVersion], ([value]) => { if (value) lookup(value) }, {immediate:true})
</script>
<template>
  <section class="billing-flow content">
    <div class="breadcrumb no-print"><span>Servicios del kiosco</span><span>›</span><span>Facturar</span></div>
    <div class="no-print"><span class="eyebrow red">AUTOSERVICIO · DOCUMENTOS DE PRUEBA</span><h1>FACTURAR</h1><p class="subtitle">Escanea el QR de tu comprobante de pago en este kiosco.</p></div>
    <p v-if="error" class="flow-error no-print" role="alert">{{error}}</p>
    <div v-if="!payment" class="billing-scan no-print">
      <ScanLine :size="70"/><h2>{{busy?'BUSCANDO COMPROBANTE…':'ESCANEA TU TICKET'}}</h2><p>Usa el lector USB o introduce el folio del comprobante de pago.</p>
      <label for="billing-code">FOLIO DEL COMPROBANTE</label><div class="billing-entry"><input id="billing-code" v-model="code" readonly inputmode="none" @click="keyboard=true" @focus="keyboard=true" placeholder="JS-PAY-…"><button class="btn-primary" :disabled="busy || !code.trim()" @click="lookup()">BUSCAR</button></div>
      <p class="demo-note">Esta pantalla utiliza los comprobantes de pago demo. El ticket de entrada al estacionamiento se consulta en Estacionamiento.</p>
    </div>
    <div v-else-if="!invoice" class="billing-confirm no-print"><div class="success-heading"><span><Check :size="30"/></span><div><h2>COMPROBANTE ENCONTRADO</h2><p>Pago simulado registrado · {{payment.conceptos.length}} concepto(s)</p></div></div><p class="receipt-code">{{payment.code}}</p><div class="invoice-test-data"><FileText :size="33"/><div><h3>DATOS FISCALES DE PRUEBA</h3><p>Emisor y receptor ficticios · RFC genérico XAXX010101000</p><p>Se generará una representación de CFDI 4.0 sin timbrado, certificado ni sello fiscal. No necesitas ingresar datos personales.</p></div></div><div class="cart-total"><span>TOTAL DEMO</span><strong>{{new Intl.NumberFormat('es-MX',{style:'currency',currency:'MXN'}).format(payment.total)}}</strong></div><button class="btn-primary full" :disabled="busy" @click="generate">{{busy?'GENERANDO FACTURA…':'GENERAR E IMPRIMIR FACTURA DE PRUEBA'}}</button><button class="btn-outline full" :disabled="busy" @click="another">ESCANEAR OTRO COMPROBANTE</button></div>
    <div v-else class="document-layout"><ReceiptCard :document="invoice" invoice/><div class="document-options no-print"><h2>FACTURA DE PRUEBA GENERADA</h2><p>Este comprobante conserva la misma factura al volver a escanearlo.</p><span class="demo-stamp">SIN VALIDEZ FISCAL</span><PrintActions :document="invoice" :result="result" invoice/><button class="btn-outline full" @click="another">ESCANEAR OTRO COMPROBANTE</button><button class="btn-primary full" @click="emit('home')">FINALIZAR</button></div></div>
    <template v-if="keyboard"><div class="keyboard-backdrop no-print" @click="keyboard=false"></div><section class="touch-keyboard no-print" aria-label="Teclado de folio"><div class="keyboard-header"><b>FOLIO DEL COMPROBANTE</b><button class="keyboard-close" @click="keyboard=false">CERRAR ✕</button></div><div class="billing-key-preview">{{code || 'JS-PAY-…'}}</div><div class="keyboard-rows"><div v-for="row in keys" :key="row" class="keyboard-row"><button v-for="letter in row" :key="letter" class="keyboard-key" @click="key(letter)">{{letter}}</button></div><div class="keyboard-row"><button class="keyboard-key keyboard-special" @click="code='JS-PAY-'">JS-PAY-</button><button class="keyboard-key keyboard-special" @click="code=code.slice(0,-1)">⌫</button><button class="keyboard-key keyboard-done" @click="keyboard=false">LISTO ✓</button></div></div></section></template>
  </section>
</template>
