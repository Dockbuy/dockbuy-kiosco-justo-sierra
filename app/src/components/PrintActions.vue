<script setup>
import {onUnmounted, ref, watch} from 'vue'
import {Printer} from 'lucide-vue-next'
import {request} from '../api'
import EmailDelivery from './EmailDelivery.vue'
const props = defineProps({document: {type:Object, required:true}, invoice:Boolean, result:Object})
const busy = ref(false), result = ref(props.result), error = ref('')
const controller = new AbortController()
onUnmounted(() => controller.abort())
watch(() => props.result, value => { result.value = value })
async function reprint() {
  if (busy.value) return
  busy.value = true; error.value = ''
  try {
    const response = await request('/billing/print', {method:'POST', body:{code:props.document.qr_payload, kind:props.invoice?'invoice':'payment'}, signal:controller.signal})
    if (!controller.signal.aborted) result.value = response
  } catch (e) { if (e.name !== 'AbortError') error.value = e.message }
  finally { if (!controller.signal.aborted) busy.value = false }
}
</script>
<template>
  <div class="print-actions no-print">
    <p v-if="result?.printed" class="status-ok" role="status">Documento enviado a la impresora. Verifica que salió el papel.</p>
    <p v-else-if="result?.printed === false" class="notice" role="status">Tu documento quedó guardado. {{result.print_error || 'Verifica la impresora antes de reintentar; también puedes enviarlo por correo cuando esté disponible o pedir ayuda.'}}</p>
    <p v-if="error" class="flow-error" role="alert">{{error}}</p>
    <button class="btn-primary" @click="reprint" :disabled="busy"><Printer :size="18"/> {{busy?'ENVIANDO…':'REIMPRIMIR EN KIOSCO'}}</button>
    <EmailDelivery :key="document.qr_payload + (invoice?'-invoice':'')" :code="document.qr_payload" :invoice="invoice"/>
  </div>
</template>
