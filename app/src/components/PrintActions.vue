<script setup>
import {onUnmounted, ref, watch} from 'vue'
import {Printer, FileDown} from 'lucide-vue-next'
import {request} from '../api'
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
function printBrowser() { window.print() }
function downloadXml() {
  const url = URL.createObjectURL(new Blob([props.document.xml], {type:'application/xml;charset=utf-8'}))
  const link = document.createElement('a'); link.href = url; link.download = `${props.document.folio}-SIN-VALIDEZ-FISCAL.xml`
  link.click(); setTimeout(() => URL.revokeObjectURL(url), 1000)
}
</script>
<template>
  <div class="print-actions no-print">
    <p v-if="result?.printed" class="status-ok" role="status">Documento enviado a la impresora. Verifica que salió el papel.</p>
    <p v-else-if="result?.printed === false" class="notice" role="status">El documento quedó guardado, pero no se pudo imprimir. Revisa la impresora. Puedes reimprimirlo o usar la impresión del navegador.</p>
    <p v-if="error" class="flow-error" role="alert">{{error}}</p>
    <button class="btn-primary" @click="reprint" :disabled="busy"><Printer :size="18"/> {{busy?'ENVIANDO…':'REIMPRIMIR EN KIOSCO'}}</button>
    <button class="btn-outline" @click="printBrowser">IMPRIMIR / GUARDAR PDF</button>
    <button v-if="invoice" class="btn-outline" @click="downloadXml"><FileDown :size="18"/> XML DE PRUEBA</button>
  </div>
</template>
