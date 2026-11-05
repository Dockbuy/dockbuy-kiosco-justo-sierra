<script setup>
import {computed,onMounted,onUnmounted,ref,watch,nextTick} from 'vue'
import {Mail,CheckCircle2,AlertCircle,ArrowLeft,Send} from 'lucide-vue-next'
import {request} from '../api'
import {trapFocus} from '../modal-focus'
const props=defineProps({code:{type:String,required:true},invoice:Boolean,campus:Boolean,token:String})
const available=ref(null),open=ref(false),email=ref(''),confirm=ref(''),field=ref('email'),keyboard=ref(false),stage=ref('edit'),busy=ref(false),error=ref(''),result=ref(null)
const controller=new AbortController()
const rows=['1234567890','qwertyuiop','asdfghjkl','zxcvbnm']
const valid=computed(()=>/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email.value.trim()) && email.value.trim()===confirm.value.trim())
let requestId='',attemptEmail=''
onMounted(async()=>{try{const services=await request('/services',{signal:controller.signal});if(!controller.signal.aborted)available.value=services.email_available}catch{if(!controller.signal.aborted)available.value=false}})
onUnmounted(()=>{controller.abort();email.value='';confirm.value='';attemptEmail=''})
watch(()=>[props.code,props.invoice],()=>close())
watch(open,async value=>{if(value){await nextTick();document.getElementById('delivery-email')?.focus()}})
function close(){if(busy.value)return;open.value=false;email.value='';confirm.value='';keyboard.value=false;stage.value='edit';error.value='';result.value=null;requestId='';attemptEmail=''}
function edit(which){if(busy.value)return;field.value=which;keyboard.value=true}
function key(value){const current=field.value==='email'?email:confirm;if(value==='BORRAR')current.value=current.value.slice(0,-1);else if(current.value.length+value.length<=254)current.value+=value}
function review(){keyboard.value=false;if(!valid.value){error.value='Escribe el mismo correo en ambos campos.';return}error.value='';stage.value='review'}
async function send(){
  if(busy.value||!valid.value||!available.value)return
  busy.value=true;error.value='';keyboard.value=false
  requestId ||= crypto.randomUUID();attemptEmail ||= email.value.trim()
  try{
    const response=await request(props.campus?'/campus/email':'/billing/email',{method:'POST',token:props.campus?props.token:undefined,body:{code:props.code,kind:props.invoice?'invoice':'payment',email:attemptEmail,request_id:requestId},signal:controller.signal,timeout:45000})
    if(controller.signal.aborted)return
    result.value=response;stage.value='result'
    if(response.status==='accepted'){email.value='';confirm.value='';attemptEmail=''}
  }catch(e){if(!controller.signal.aborted){error.value=e.message;stage.value='review';if(e.status===400){requestId='';attemptEmail=''}}}
  finally{if(!controller.signal.aborted)busy.value=false}
}
</script>
<template>
  <div class="email-delivery">
    <button class="btn-outline email-trigger" :disabled="available!==true" @click="open=true"><Mail :size="20"/> ENVIAR POR CORREO</button>
    <p v-if="available===null" class="delivery-note">Consultando servicio de correo…</p>
    <p v-else-if="!available" class="delivery-note">El correo aún no está disponible en este kiosco. {{campus?'Tu constancia seguirá disponible en Mis trámites cuando se active el correo.':'Puedes imprimir tu ticket o consultarlo después.'}}</p>
    <p v-else class="delivery-note">Recibe {{campus?'tu constancia PDF de demostración':invoice?'PDF y XML de prueba':'tu comprobante PDF'}} en tu correo. No se descargan archivos en el kiosco.</p>
    <div v-if="open" class="kiosk-modal-backdrop" @keydown.esc.prevent="close" @keydown="trapFocus">
      <section class="kiosk-modal email-modal" role="dialog" aria-modal="true" aria-labelledby="email-title">
        <div class="modal-head"><span class="modal-icon"><Mail :size="25"/></span><div><h2 id="email-title">ENVÍO POR CORREO</h2><p>{{campus?'Constancia PDF de demostración':invoice?'Factura PDF + XML de prueba':'Comprobante PDF de prueba'}}</p></div><button class="icon-close" :disabled="busy" @click="close" aria-label="Cerrar correo">✕</button></div>
        <p v-if="error" class="flow-error" role="alert">{{error}}</p>
        <template v-if="stage==='edit'">
          <p>Escribe tu correo y confírmalo para evitar errores de entrega.</p>
          <label for="delivery-email">Tu correo</label><input id="delivery-email" v-model="email" type="email" inputmode="none" autocomplete="off" autocapitalize="none" :spellcheck="false" maxlength="254" placeholder="nombre@dominio.com" @focus="edit('email')">
          <label for="delivery-confirm">Confirma tu correo</label><input id="delivery-confirm" v-model="confirm" type="email" inputmode="none" autocomplete="off" autocapitalize="none" :spellcheck="false" maxlength="254" placeholder="Vuelve a escribirlo" @focus="edit('confirm')">
          <div v-if="keyboard" class="email-keyboard touch-keyboard-inline" aria-label="Teclado de correo"><div class="keyboard-row" v-for="row in rows" :key="row"><button class="keyboard-key" v-for="letter in row" :key="letter" @click.prevent="key(letter)">{{letter}}</button></div><div class="keyboard-row"><button class="keyboard-key" v-for="symbol in ['@','.','-','_','+']" :key="symbol" @click.prevent="key(symbol)">{{symbol}}</button><button class="keyboard-key keyboard-special" @click.prevent="key('BORRAR')">⌫</button><button class="keyboard-key keyboard-done" @click="keyboard=false">LISTO</button></div></div>
          <p class="privacy-note">Solo usaremos este correo para el documento solicitado. Se limpiará de la pantalla al finalizar.</p>
          <button class="btn-primary full" :disabled="!valid" @click="review">REVISAR DESTINATARIO</button>
        </template>
        <template v-else-if="stage==='review'">
          <p>Vamos a enviar el documento a:</p><div class="email-confirm-address">{{attemptEmail||email.trim()}}</div><p>Comprueba que esté bien escrito. El documento está marcado como demo y no tiene validez fiscal.</p>
          <button class="btn-primary full" :disabled="busy" @click="send"><Send :size="19"/> {{busy?'ENVIANDO…':requestId?'CONSULTAR / REINTENTAR ENVÍO':'CONFIRMAR Y ENVIAR'}}</button>
          <button class="btn-outline full" v-if="!requestId" :disabled="busy" @click="stage='edit'"><ArrowLeft :size="17"/> CORREGIR CORREO</button>
          <p v-if="requestId && !busy" class="delivery-note">Si la conexión se interrumpió, consulta el mismo envío antes de intentar uno nuevo.</p>
        </template>
        <template v-else>
          <div class="delivery-result" :class="result.status==='accepted'?'is-success':''"><CheckCircle2 v-if="result.status==='accepted'" :size="48"/><AlertCircle v-else :size="48"/><h3>{{result.status==='accepted'?'ENVÍO ACEPTADO':result.status==='sending'?'ENVÍO EN PROCESO':result.status==='unknown'?'ENTREGA SIN CONFIRMAR':'NO SE PUDO ENVIAR'}}</h3><p v-if="result.status==='accepted'">El servicio de correo recibió tu documento para {{result.recipient}}. Revisa tu bandeja y correo no deseado; la llegada a tu bandeja no se puede confirmar desde aquí.</p><p v-else-if="result.status==='sending'">El envío sigue procesándose. Puedes consultar su estado sin mandar otra copia.</p><p v-else-if="result.status==='unknown'">Se interrumpió la comunicación. Revisa tu correo antes de solicitar otro envío; no volveremos a enviarlo automáticamente.</p><p v-else>El servicio no aceptó el envío. Verifica el correo o solicita ayuda. Tu comprobante sigue guardado.</p></div>
          <button v-if="result.status==='sending'" class="btn-primary full" :disabled="busy" @click="send">CONSULTAR ESTADO</button><button class="btn-outline full" @click="close">LISTO</button>
        </template>
      </section>
    </div>
  </div>
</template>
