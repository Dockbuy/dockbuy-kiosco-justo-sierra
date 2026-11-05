<script setup>
import {ref, watch} from 'vue'
import QRCode from 'qrcode'
const props = defineProps({document: {type: Object, required: true}, invoice: Boolean})
const qr = ref(''), qrError = ref('')
const money = n => new Intl.NumberFormat('es-MX', {style:'currency', currency:'MXN'}).format(n)
let generation = 0
watch(() => props.document.qr_payload, async payload => {
  const current = ++generation
  qr.value = ''; qrError.value = ''
  try {
    const data = await QRCode.toDataURL(payload, {errorCorrectionLevel:'M', width:240, margin:4})
    if (current === generation) qr.value = data
  } catch { if (current === generation) qrError.value = 'No se pudo dibujar el QR. Puedes introducir el folio manualmente.' }
}, {immediate:true})
</script>

<template>
  <article class="receipt-card print-document" aria-label="Documento de prueba">
    <img class="receipt-logo" src="/images/logo.jpg" alt="Justo Sierra">
    <h2>{{invoice ? 'FACTURA DE PRUEBA' : 'COMPROBANTE DE PAGO DEMO'}}</h2>
    <strong class="demo-stamp">DEMO · SIN VALIDEZ FISCAL</strong>
    <p class="receipt-caption">{{invoice ? 'CFDI 4.0 ilustrativo · sin timbrado ni sello SAT' : 'Operación simulada · no se realizó ningún cobro real'}}</p>
    <p>{{new Date(document.issued_at).toLocaleString('es-MX')}}</p>
    <template v-if="invoice">
      <p><b>Folio de prueba:</b> {{document.folio}}</p>
      <p class="receipt-fiscal"><b>{{document.emisor}}</b><br>RFC emisor: {{document.rfc_emisor}}<br><b>{{document.receptor}}</b><br>RFC receptor: {{document.rfc_receptor}}</p>
    </template>
    <p v-else>Matrícula demo: <b>{{document.estudiante.matricula}}</b></p>
    <div v-for="c in document.conceptos" :key="c.id" class="receipt-line"><span>{{c.nombre}}</span><b>{{money(c.restante)}}</b></div>
    <div class="receipt-total"><span>TOTAL DEMO</span><b>{{money(document.total)}} MXN</b></div>
    <p class="receipt-caption">Escanea en este kiosco para {{invoice ? 'consultar o reimprimir' : 'facturar'}}.</p>
    <img v-if="qr" :src="qr" class="receipt-qr" alt="QR del comprobante de prueba">
    <p v-if="qrError" role="alert">{{qrError}}</p>
    <p class="receipt-code">{{document.qr_payload}}</p>
    <strong class="receipt-caption">SIN COBRO REAL · SIN VALIDEZ FISCAL</strong>
  </article>
</template>
