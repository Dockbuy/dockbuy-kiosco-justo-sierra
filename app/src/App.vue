<script setup>
import {computed,onMounted,onUnmounted,ref} from 'vue'
import {GraduationCap,ShieldCheck,Wallet,UserRound,LogOut,ArrowLeft,ChevronRight,Check,Wifi,WifiOff,Home,LockKeyhole,Eye,EyeOff,Printer,CarFront,ScanLine,Ticket,Clock3,FileText} from 'lucide-vue-next'
import {request} from './api'
import PaymentFlow from './components/PaymentFlow.vue'
import BillingFlow from './components/BillingFlow.vue'
import './payments.css'
const view=ref('welcome'),matricula=ref('202210'),pin=ref('1234'),token=ref(''),student=ref(null),charges=ref([]),busy=ref(false),error=ref(''),online=ref(false),showPin=ref(false),clock=ref('')
const keyboardOpen=ref(false),activeField=ref('matricula'),keyboardShift=ref(false)
const billingCode=ref(''),billingScanVersion=ref(0)
const keyboardRows=computed(()=>activeField.value==='matricula'||activeField.value==='pin' ? [['1','2','3'],['4','5','6'],['7','8','9'],['BORRAR','0','LISTO']] : [['1','2','3','4','5','6','7','8','9','0'],['Q','W','E','R','T','Y','U','I','O','P'],['A','S','D','F','G','H','J','K','L'],['MAYÚS','Z','X','C','V','B','N','M','BORRAR'],['ESPACIO','@','.','-','LISTO']])
function openKeyboard(field){activeField.value=field;keyboardShift.value=false;keyboardOpen.value=true}
function closeKeyboard(){keyboardOpen.value=false}
function pressKey(key){
 if(key==='LISTO'){closeKeyboard();return}
 if(key==='MAYÚS'){keyboardShift.value=!keyboardShift.value;return}
 const field=activeField.value,old=field==='pin'?pin.value:field==='parking'?parkingCode.value:matricula.value
 const next=key==='BORRAR'?old.slice(0,-1):(old+(key==='ESPACIO'?' ':keyboardShift.value?key:key.toLowerCase())).slice(0,80)
 if(field==='pin')pin.value=next;else if(field==='parking')parkingCode.value=next.toUpperCase();else matricula.value=next
}
const currency=n=>new Intl.NumberFormat('es-MX',{style:'currency',currency:'MXN'}).format(n)
let ticker,expiry,loginGeneration=0,sessionController=new AbortController(),healthController=new AbortController()
async function health(){try{const r=await request('/health',{timeout:4000,signal:healthController.signal});online.value=r.status==='ok'}catch{if(!healthController.signal.aborted)online.value=false}}
function reset(){
 sessionController.abort();sessionController=new AbortController();++loginGeneration;clearTimeout(expiry)
 cancelParking();closeKeyboard();token.value='';student.value=null;charges.value=[];view.value='welcome';error.value='';busy.value=false;showPin.value=false;pin.value=''
 billingCode.value='';scannerBuffer=''
}
function logout(){
 const previous=token.value;reset()
 if(previous)request('/auth/logout',{method:'POST',token:previous,timeout:4000}).catch(()=>{})
}
function expireSession(){logout();view.value='login';error.value='Tu sesión venció. Vuelve a ingresar.'}
async function login(){
 if(busy.value)return
 closeKeyboard();error.value='';busy.value=true
 const generation=++loginGeneration,signal=sessionController.signal
 let issuedToken='',accepted=false
 try{
  const r=await request('/auth/login',{method:'POST',body:{matricula:matricula.value,pin:pin.value},signal})
  issuedToken=r.access_token
  const d=await request('/charges',{token:issuedToken,signal})
  if(signal.aborted||generation!==loginGeneration)return
  token.value=issuedToken;student.value=r.estudiante;charges.value=d.conceptos;view.value='dashboard';accepted=true
  expiry=setTimeout(expireSession,r.expires_in*1000)
 }catch(e){if(!signal.aborted&&generation===loginGeneration){error.value=e.message;token.value=''}}
 finally{
  if(issuedToken&&!accepted)request('/auth/logout',{method:'POST',token:issuedToken,timeout:4000}).catch(()=>{})
  if(!signal.aborted&&generation===loginGeneration)busy.value=false
 }
}
function openBilling(code=''){
 logout();billingCode.value=typeof code==='string'?code:'';billingScanVersion.value++;view.value='billing'
}
const parkingStep=ref('menu'),parkingTicket=ref(null),parkingQuote=ref(null),parkingCode=ref(''),parkingError=ref(''),parkingBusy=ref(false)
let parkingController=new AbortController()
function cancelParking(){parkingController.abort();parkingController=new AbortController();parkingBusy.value=false;parkingTicket.value=null;parkingQuote.value=null;parkingError.value='';parkingCode.value='';parkingStep.value='menu'}
function parkingHome(){cancelParking();closeKeyboard();scannerBuffer='';view.value='parking'}
async function parkingAction(action){
 if(parkingBusy.value)return
 const signal=parkingController.signal;parkingBusy.value=true;parkingError.value=''
 try{await action(signal)}catch(e){if(!signal.aborted)parkingError.value=e.message}
 finally{if(!signal.aborted)parkingBusy.value=false}
}
async function issueParking(){await parkingAction(async signal=>{const r=await request('/parking/issue',{method:'POST',body:{},signal});if(!signal.aborted){parkingTicket.value=r.ticket;parkingStep.value='issued'}})}
function beginScan(){cancelParking();parkingStep.value='scan';scannerBuffer=''}
async function lookupParking(code=parkingCode.value){closeKeyboard();await parkingAction(async signal=>{const r=await request('/parking/quote',{method:'POST',body:{code:code.trim().toUpperCase()},signal});if(!signal.aborted){parkingQuote.value=r;parkingStep.value='quote'}})}
async function reprintParking(){if(!parkingTicket.value)return;await parkingAction(async signal=>{await request('/parking/reprint',{method:'POST',body:{code:parkingTicket.value.code},signal});if(!signal.aborted)parkingTicket.value.printed=true})}
let scannerBuffer='',scannerAt=0
function scannerKey(e){
 if(keyboardOpen.value||document.querySelector('.touch-keyboard'))return
 if(e.ctrlKey||e.altKey||e.metaKey)return
 if(e.target instanceof HTMLInputElement&&!e.target.readOnly)return
 if(e.key==='Enter'){
  const code=scannerBuffer.trim().toUpperCase();scannerBuffer=''
  if(/^JS-PAY-[A-F0-9]{32}$/.test(code)){e.preventDefault();openBilling(code);return}
  if(view.value==='parking'&&parkingStep.value==='scan'&&!parkingBusy.value){
   const value=code||parkingCode.value
   if(value){e.preventDefault();parkingCode.value=value;lookupParking(value)}
  }else if(view.value==='billing'&&code.length>=10){e.preventDefault();billingCode.value=code;billingScanVersion.value++}
  return
 }
 if(e.key.length===1){const now=Date.now();if(now-scannerAt>200)scannerBuffer='';scannerAt=now;scannerBuffer+=e.key;if(scannerBuffer.length>180)scannerBuffer=''}
}
function tick(){clock.value=new Date().toLocaleString('es-MX',{dateStyle:'medium',timeStyle:'short'})}
onMounted(()=>{window.addEventListener('keydown',scannerKey);health();tick();ticker=setInterval(()=>{tick();health()},30000)})
onUnmounted(()=>{window.removeEventListener('keydown',scannerKey);clearInterval(ticker);clearTimeout(expiry);sessionController.abort();healthController.abort();parkingController.abort()})
</script>
<template>
<div class="screen" :class="{interior:!['welcome','login'].includes(view),'keyboard-visible':keyboardOpen}">
 <BillingFlow v-if="view==='billing'" :code="billingCode" :scan-version="billingScanVersion" @home="reset"/>
 <template v-else-if="view==='parking'">
 <div class="parking-page">
  <header class="parking-header"><div class="parking-mark"><img src="/images/logo.jpg" alt="Justo Sierra"><span><b>JUSTO SIERRA</b><small>ESTACIONAMIENTO UNIVERSITARIO</small></span></div><button class="parking-exit" @click="reset"><Home :size="20"/> INICIO</button></header>
  <main class="parking-main">
   <div class="parking-badge"><CarFront :size="19"/> SERVICIO DE ESTACIONAMIENTO · DEMOSTRACIÓN</div>
   <template v-if="parkingStep==='menu'"><h1>ESTACIONAMIENTO</h1><p class="parking-lead">Obtén tu boleto de entrada o consulta el costo de tu estancia escaneando el código QR.</p>
    <div class="parking-cards"><button class="parking-card" @click="issueParking" :disabled="parkingBusy"><span class="parking-icon"><Ticket :size="54"/></span><strong>GENERAR TICKET</strong><span>Imprime tu boleto con código QR en la impresora térmica.</span><b>{{parkingBusy?'GENERANDO...':'OBTENER BOLETO →'}}</b></button>
    <button class="parking-card" @click="beginScan"><span class="parking-icon"><ScanLine :size="54"/></span><strong>CONSULTAR Y PAGAR</strong><span>Escanea el QR del boleto para consultar el importe.</span><b>ESCANEAR TICKET →</b></button></div>
    <div class="parking-rate"><Clock3 :size="25"/><div><strong>$20.00 MXN</strong><span>Por cada bloque de 8 horas iniciado · tarifa demo</span></div></div></template>
   <template v-else-if="parkingStep==='issued'"><h1>TICKET GENERADO</h1><p class="parking-lead">Conserva tu boleto para consultar el importe a la salida.</p>
    <div class="parking-panel"><div class="parking-check"><Check :size="36"/></div><h2>{{parkingTicket?.printed?'BOLETO ENVIADO A IMPRESIÓN':'BOLETO GENERADO'}}</h2><p v-if="!parkingTicket?.printed" class="parking-alert">No se pudo imprimir: {{parkingTicket?.print_error}}. Comprueba CUPS y vuelve a imprimir.</p><span class="parking-label">FOLIO DE ENTRADA</span><div class="parking-code">{{parkingTicket?.code}}</div><span class="parking-label">FECHA DE ENTRADA</span><p>{{parkingTicket?.issued_at?new Date(parkingTicket.issued_at).toLocaleString('es-MX'):''}}</p><div class="parking-actions"><button class="btn-primary" @click="reprintParking" :disabled="parkingBusy"><Printer :size="19"/> {{parkingBusy?'ENVIANDO...':'REIMPRIMIR TICKET'}}</button><button class="btn-outline" @click="parkingHome">FINALIZAR</button></div></div></template>
   <template v-else-if="parkingStep==='scan'"><h1>ESCANEAR TICKET</h1><p class="parking-lead">Acerca el código QR impreso al lector USB del kiosco. También puedes introducir el folio manualmente.</p>
    <div class="parking-panel"><div class="parking-scan"><ScanLine :size="86"/></div><h2>LECTOR DE CÓDIGOS QR</h2><p>Esperando lectura del escáner USB (modo teclado + Enter)</p><label class="parking-label" for="parking-code">FOLIO DEL TICKET</label><div class="parking-entry"><input id="parking-code" :value="parkingCode" readonly inputmode="none" @click="openKeyboard('parking')" @focus="openKeyboard('parking')" placeholder="TOCA PARA ESCRIBIR EL FOLIO"><button class="btn-primary" :disabled="parkingBusy || !parkingCode.trim()" @click="lookupParking()">CONSULTAR</button></div></div></template>
   <template v-else-if="parkingStep==='quote'"><h1>RESUMEN DE ESTACIONAMIENTO</h1><p class="parking-lead">Verifica los datos del boleto y el importe calculado.</p>
    <div class="parking-panel"><div class="parking-badge">COTIZACIÓN DEMO · SIN COBRO REAL</div><div class="parking-summary-row"><span>Folio</span><b>{{parkingQuote?.code}}</b></div><div class="parking-summary-row"><span>Entrada</span><b>{{parkingQuote?.issued_at?new Date(parkingQuote.issued_at).toLocaleString('es-MX'):''}}</b></div><div class="parking-summary-row"><span>Tiempo transcurrido</span><b>{{parkingQuote?.hours}} horas</b></div><div class="parking-summary-row"><span>Tarifa</span><b>$20 por bloque de 8 h</b></div><div class="parking-summary-row"><span>Bloques facturables</span><b>{{parkingQuote?.periods}}</b></div><div class="parking-due"><small>TOTAL A PAGAR</small><strong>{{currency(parkingQuote?.total||0)}}</strong></div><p class="parking-alert">COBRO NO DISPONIBLE: la terminal bancaria aún no está integrada. Este ticket permanece pendiente; no se registra ningún pago.</p><div class="parking-actions"><button class="btn-outline" @click="beginScan">OTRO TICKET</button><button class="btn-primary" @click="parkingHome">FINALIZAR CONSULTA</button></div></div></template>
   <p v-if="parkingError" class="parking-alert parking-error">{{parkingError}}</p>
  </main>
  <div class="parking-bottom">JUSTO SIERRA · DOCKBUY · SISTEMA DE PRUEBAS · NO SE REALIZAN COBROS</div>
 </div>
 </template>
 <template v-else-if="view==='welcome'">
  <div class="hero" style="background-image:linear-gradient(90deg,rgba(4,20,49,.32),rgba(4,20,49,.66)),url('/images/campus.jpg')"><div class="hero-copy"><span class="eyebrow">UNIVERSIDAD JUSTO SIERRA</span><h1>Bienvenido a tu<br><em>kiosco universitario</em></h1><p>Consulta información académica, conceptos de pago y servicios institucionales de manera sencilla.</p><button class="btn-primary hero-button" @click="view='login'">COMENZAR <ChevronRight :size="23"/></button><div class="hero-features"><span><ShieldCheck/> Acceso seguro</span><span><Wallet/> Consulta de pagos</span><span><GraduationCap/> Servicios escolares</span></div></div></div>
  <div class="welcome-brand"><img src="/images/logo.jpg" alt="Justo Sierra"><h3>Educar para la vida</h3><p>PORTAL DE AUTOSERVICIO</p><div class="mini-bar"></div><button class="btn-outline" @click="view='login'">INGRESAR AL PORTAL</button><button class="btn-primary parking-welcome" @click="parkingHome"><CarFront :size="22"/> ESTACIONAMIENTO</button><button class="btn-outline parking-welcome" @click="openBilling()"><FileText :size="22"/> FACTURAR TICKET</button><small>Plataforma de demostración Dockbuy</small></div>
 </template>
 <template v-else-if="view==='login'">
  <section class="auth-left"><div class="auth-card"><img class="brand-logo" src="/images/logo.jpg" alt="Justo Sierra"><h2>BIENVENIDO</h2><p class="muted upper">PORTAL DE ALUMNOS</p><div class="red-line"></div><p class="instruction">Ingresa tus credenciales para continuar</p><form @submit.prevent="login"><label>Matrícula del estudiante</label><div class="input-wrap"><UserRound :size="19"/><input v-model.trim="matricula" inputmode="none" readonly @click="openKeyboard('matricula')" @focus="openKeyboard('matricula')" autocomplete="off" placeholder="Ingresa tu matrícula" required></div><label>Contraseña / PIN demo</label><div class="input-wrap"><LockKeyhole :size="19"/><input v-model="pin" inputmode="none" readonly @click="openKeyboard('pin')" @focus="openKeyboard('pin')" :type="showPin?'text':'password'" placeholder="Ingresa tu PIN" required><button type="button" class="inline-btn" @click="showPin=!showPin"><EyeOff v-if="showPin" :size="19"/><Eye v-else :size="19"/></button></div><p v-if="error" class="error">{{error}}</p><button class="btn-primary full" :disabled="busy">{{busy?'VALIDANDO...':'ENTRAR'}} <ChevronRight :size="18"/></button></form><div class="auth-links"><button @click="reset">← Volver</button><span>Recuperación de acceso: universidad</span></div><div class="auth-demo">DEMO · Matrícula 202210 o 202211 · PIN 1234</div></div></section>
  <section class="auth-image"><div class="auth-features"><div><span><ShieldCheck/></span><p><b>SEGURIDAD</b><small>Acceso protegido a tu información.</small></p></div><div><span><Wifi/></span><p><b>ACCESO 24/7</b><small>Consulta la información en un solo lugar.</small></p></div><div><span><GraduationCap/></span><p><b>TODO EN UN SOLO LUGAR</b><small>Servicios académicos y administrativos.</small></p></div></div></section>
 </template>
 <template v-else>
  <header class="topbar"><button class="menu" @click="view='dashboard'"><Home :size="24"/></button><div class="topbrand"><b>Justo Sierra</b><span>{{student?.nombre}} <small>· MATRÍCULA {{student?.matricula}}</small></span></div><div class="topmeta"><span class="online"><Wifi v-if="online" :size="18"/><WifiOff v-else :size="18"/> {{online?'DEMO CONECTADA':'API DESCONECTADA'}}</span><span>{{clock}}</span><button @click="logout"><LogOut :size="19"/> SALIR</button></div></header>
  <main class="content"><div class="breadcrumb"><button @click="view='dashboard'"><Home :size="16"/> Inicio</button><ChevronRight :size="14"/> <span>{{view==='dashboard'?'Mis servicios':view==='charges'?'Talonarios y pago en línea':'Resumen de pago'}}</span></div>
   <template v-if="view==='dashboard'"><section class="intro"><div><span class="eyebrow red">PORTAL DE ALUMNOS</span><h1>Hola, {{student?.nombre.split(' ')[0]}}</h1><p>¿Qué deseas consultar hoy?</p></div><img src="/images/logo.jpg" alt="Logo institucional"></section><div class="quick-grid"><button class="quick-card" @click="view='charges'"><span class="quick-icon"><Wallet :size="36"/></span><h2>Servicios y pagos</h2><p>Consulta tus cargos pendientes y genera un resumen de pago.</p><strong>CONSULTAR <ChevronRight :size="20"/></strong></button><button class="quick-card" @click="view='student'"><span class="quick-icon"><UserRound :size="36"/></span><h2>Mi información</h2><p>Visualiza datos académicos y de identificación.</p><strong>VER INFORMACIÓN <ChevronRight :size="20"/></strong></button><div class="campus-card"><img src="/images/alumnos.jpg" alt="Estudiantes Justo Sierra"><div><b>JUSTO SIERRA</b><span>Educar para la vida</span></div></div></div></template>
   <template v-else-if="view==='student'"><button class="back" @click="view='dashboard'"><ArrowLeft :size="18"/> Volver</button><h1>MI INFORMACIÓN</h1><p class="subtitle">INFORMACIÓN ACADÉMICA DEL ESTUDIANTE</p><div class="profile-card"><div class="avatar"><UserRound :size="46"/></div><div><h2>{{student?.nombre}}</h2><p>{{student?.matricula}}</p></div></div><div class="detail-grid"><div v-for="[key,val] in [['Matrícula',student?.matricula],['Nivel académico',student?.nivel],['Grado',student?.grado],['Grupo',student?.grupo],['Ciclo escolar',student?.ciclo],['Correo de prueba',student?.email]]" :key="key"><span>{{key}}</span><b>{{val}}</b></div></div><div class="notice">Información completamente ficticia, obtenida de la API local de demostración.</div></template>
   <PaymentFlow v-else-if="view==='charges'" :token="token" :charges="charges" @expired="expireSession" @updated="charges=$event" @billing="openBilling" @back="view='dashboard'"/>
  </main>
 </template>
 <div v-if="keyboardOpen && ['login','parking'].includes(view)" class="keyboard-backdrop" @click="closeKeyboard"></div>
 <section v-if="keyboardOpen && ['login','parking'].includes(view)" class="touch-keyboard" aria-label="Teclado táctil">
   <div class="keyboard-header"><div><span class="keyboard-dot"></span><b>TECLADO TÁCTIL</b><small>{{activeField==='matricula'?'MATRÍCULA':activeField==='parking'?'FOLIO DE ESTACIONAMIENTO':'CONTRASEÑA / PIN'}}</small></div><button type="button" class="keyboard-close" @click="closeKeyboard">CERRAR ✕</button></div>
   <div class="keyboard-input-preview"><span>{{activeField==='matricula'?matricula.replace(/./g,'•'):activeField==='parking'?parkingCode:pin.replace(/./g,'•')}}</span><span class="keyboard-cursor">▏</span></div>
   <div class="keyboard-rows" :class="{'numeric-layout':activeField==='matricula'||activeField==='pin'}"><div class="keyboard-row" v-for="(row,i) in keyboardRows" :key="i"><button v-for="key in row" :key="key" type="button" class="keyboard-key" :class="{'keyboard-special':['BORRAR','MAYÚS','ESPACIO'].includes(key),'keyboard-done':key==='LISTO'}" @click="pressKey(key)">{{key==='BORRAR'?'⌫':key==='LISTO'?'LISTO ✓':key}}</button></div></div>
   <p class="keyboard-help">Toca los números para escribir · pulsa LISTO para continuar</p>
 </section>
 <footer><div><img src="/images/logo.jpg" alt="Logo Justo Sierra"><span><b>Justo Sierra</b><small>Educar para la vida</small></span></div><p>PLATAFORMA DE DEMOSTRACIÓN · DOCKBUY · 2026<br>Pagos y facturas de prueba · sin cobro real ni validez fiscal</p></footer>
</div>
</template>
