<script setup>
import {computed,onMounted,onUnmounted,ref,watch,nextTick} from 'vue'
import {GraduationCap,ShieldCheck,Wallet,UserRound,LogOut,ArrowLeft,ChevronRight,Check,Wifi,WifiOff,Home,LockKeyhole,Eye,EyeOff,Printer,CarFront,ScanLine,Ticket,Clock3,FileText,ReceiptText,HelpCircle} from 'lucide-vue-next'
import {request} from './api'
import {trapFocus} from './modal-focus'
import PaymentFlow from './components/PaymentFlow.vue'
import BillingFlow from './components/BillingFlow.vue'
import IdleSession from './components/IdleSession.vue'
import PaymentHistory from './components/PaymentHistory.vue'
import KioskNavigation from './components/KioskNavigation.vue'
import './payments.css'
import './kiosk.css'
const view=ref('welcome'),matricula=ref('202210'),pin=ref('1234'),token=ref(''),student=ref(null),charges=ref([]),busy=ref(false),error=ref(''),online=ref(false),showPin=ref(false),clock=ref('')
const keyboardOpen=ref(false),activeField=ref('matricula'),keyboardShift=ref(false)
const billingCode=ref(''),billingScanVersion=ref(0),sessionNotice=ref(''),helpOpen=ref(false)
const draftSelection=ref([]),navigationLocked=ref(false),paymentFlow=ref(null),historyFlow=ref(null),billingFlow=ref(null),billingReturn=ref('welcome'),helpClose=ref(null)
const pendingTotal=computed(()=>charges.value.reduce((sum,c)=>sum+c.restante,0))
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
 billingCode.value='';scannerBuffer='';matricula.value='';helpOpen.value=false;sessionNotice.value='';draftSelection.value=[];navigationLocked.value=false;billingReturn.value='welcome'
}
function logout(){
 const previous=token.value;reset()
 if(previous)request('/auth/logout',{method:'POST',token:previous,timeout:4000}).catch(()=>{})
}
function idleExpired(){logout();sessionNotice.value='Sesión finalizada por inactividad. Tus datos se limpiaron de la pantalla.'}
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
 if(navigationLocked.value)return
 const previous=view.value
 if(!token.value)logout()
 if(previous!=='billing')billingReturn.value=previous
 closeKeyboard();helpOpen.value=false;scannerBuffer=''
 if(view.value==='parking')cancelParking()
 billingCode.value=typeof code==='string'?code:'';billingScanVersion.value++;view.value='billing'
}
function home(){if(token.value)navigate('dashboard');else logout()}
function navigate(target){
 if(navigationLocked.value||target===view.value)return
 closeKeyboard();helpOpen.value=false;scannerBuffer=''
 if(target==='welcome'){logout();return}
 if(target==='billing'){openBilling();return}
 if(view.value==='parking')cancelParking()
 if(target==='parking'){parkingHome();return}
 view.value=target
}
function back(){
 if(keyboardOpen.value){closeKeyboard();return}
 if(helpOpen.value){helpOpen.value=false;return}
 if(view.value==='charges'){paymentFlow.value?.goBack();return}
 if(view.value==='history'){historyFlow.value?.goBack();return}
 if(view.value==='billing'){billingFlow.value?.goBack();return}
 if(view.value==='parking'&&parkingStep.value!=='menu'){
  if(parkingStep.value==='quote'){beginScan();return}
  parkingHome();return
 }
 home()
}
function billingBack(){navigate(token.value&&['charges','history','dashboard','student'].includes(billingReturn.value)?billingReturn.value:token.value?'dashboard':'welcome')}
function closeTopLayer(e){if(e.key==='Escape'&&helpOpen.value){helpOpen.value=false;e.preventDefault()}}
watch(view,async()=>{await nextTick();window.scrollTo(0,0)})
watch(helpOpen,async opened=>{if(opened){await nextTick();helpClose.value?.focus()}})

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
 if(navigationLocked.value||keyboardOpen.value||document.querySelector('.touch-keyboard,.kiosk-modal-backdrop'))return
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
onMounted(()=>{window.addEventListener('keydown',scannerKey);window.addEventListener('keydown',closeTopLayer);health();tick();ticker=setInterval(()=>{tick();health()},30000)})
onUnmounted(()=>{window.removeEventListener('keydown',scannerKey);window.removeEventListener('keydown',closeTopLayer);clearInterval(ticker);clearTimeout(expiry);sessionController.abort();healthController.abort();parkingController.abort()})
</script>
<template>
<div class="screen" :class="{interior:!['welcome','login'].includes(view),'keyboard-visible':keyboardOpen}">
 <IdleSession :active="view!=='welcome'" @expired="idleExpired"/>
 <KioskNavigation v-if="!['welcome','login'].includes(view)" :view="view" :authenticated="!!token" :student="student" :online="online" :clock="clock" :draft-count="draftSelection.length" :locked="navigationLocked" @navigate="navigate" @home="home" @back="back" @exit="logout" @help="helpOpen=true"/>
 <BillingFlow ref="billingFlow" v-if="view==='billing'" :code="billingCode" :scan-version="billingScanVersion" @home="logout" @back="billingBack"/>
 <template v-else-if="view==='parking'">
 <div class="parking-page">

  <main class="parking-main">
   <div class="parking-badge"><CarFront :size="19"/> SERVICIO DE ESTACIONAMIENTO · DEMOSTRACIÓN</div>
   <template v-if="parkingStep==='menu'"><h1>ESTACIONAMIENTO</h1><p class="parking-lead">Obtén tu boleto de entrada o consulta el costo de tu estancia escaneando el código QR.</p>
    <div class="parking-cards"><button class="parking-card" @click="issueParking" :disabled="parkingBusy"><span class="parking-icon"><Ticket :size="54"/></span><strong>GENERAR TICKET</strong><span>Imprime tu boleto con código QR en la impresora térmica.</span><b>{{parkingBusy?'GENERANDO...':'OBTENER BOLETO →'}}</b></button>
    <button class="parking-card" @click="beginScan"><span class="parking-icon"><ScanLine :size="54"/></span><strong>CONSULTAR IMPORTE</strong><span>Escanea el QR del boleto para consultar el importe.</span><b>ESCANEAR TICKET →</b></button></div>
    <div class="parking-rate"><Clock3 :size="25"/><div><strong>$20.00 MXN</strong><span>Por cada bloque de 8 horas iniciado · tarifa demo</span></div></div></template>
   <template v-else-if="parkingStep==='issued'"><h1>TICKET GENERADO</h1><p class="parking-lead">Conserva tu boleto para consultar el importe a la salida.</p>
    <div class="parking-panel"><div class="parking-check"><Check :size="36"/></div><h2>{{parkingTicket?.printed?'BOLETO ENVIADO A IMPRESIÓN':'BOLETO GENERADO'}}</h2><p v-if="!parkingTicket?.printed" class="parking-alert">El boleto quedó guardado, pero no salió la impresión. Revisa la impresora o pide ayuda y vuelve a intentarlo.</p><span class="parking-label">FOLIO DE ENTRADA</span><div class="parking-code">{{parkingTicket?.code}}</div><span class="parking-label">FECHA DE ENTRADA</span><p>{{parkingTicket?.issued_at?new Date(parkingTicket.issued_at).toLocaleString('es-MX'):''}}</p><div class="parking-actions"><button class="btn-primary" @click="reprintParking" :disabled="parkingBusy"><Printer :size="19"/> {{parkingBusy?'ENVIANDO...':'REIMPRIMIR TICKET'}}</button><button class="btn-outline" @click="logout">FINALIZAR Y SALIR</button></div></div></template>
   <template v-else-if="parkingStep==='scan'"><h1>ESCANEAR TICKET</h1><p class="parking-lead">Acerca el código QR impreso al lector USB del kiosco. También puedes introducir el folio manualmente.</p>
    <div class="parking-panel"><div class="parking-scan"><ScanLine :size="86"/></div><h2>LECTOR DE CÓDIGOS QR</h2><p>Esperando lectura del escáner USB (modo teclado + Enter)</p><label class="parking-label" for="parking-code">FOLIO DEL TICKET</label><div class="parking-entry"><input id="parking-code" :value="parkingCode" readonly inputmode="none" @click="openKeyboard('parking')" @focus="openKeyboard('parking')" placeholder="TOCA PARA ESCRIBIR EL FOLIO"><button class="btn-primary" :disabled="parkingBusy || !parkingCode.trim()" @click="lookupParking()">CONSULTAR</button></div></div></template>
   <template v-else-if="parkingStep==='quote'"><h1>RESUMEN DE ESTACIONAMIENTO</h1><p class="parking-lead">Verifica los datos del boleto y el importe calculado.</p>
    <div class="parking-panel"><div class="parking-badge">COTIZACIÓN DEMO · SIN COBRO REAL</div><div class="parking-summary-row"><span>Folio</span><b>{{parkingQuote?.code}}</b></div><div class="parking-summary-row"><span>Entrada</span><b>{{parkingQuote?.issued_at?new Date(parkingQuote.issued_at).toLocaleString('es-MX'):''}}</b></div><div class="parking-summary-row"><span>Tiempo transcurrido</span><b>{{parkingQuote?.hours}} horas</b></div><div class="parking-summary-row"><span>Tarifa</span><b>$20 por bloque de 8 h</b></div><div class="parking-summary-row"><span>Bloques facturables</span><b>{{parkingQuote?.periods}}</b></div><div class="parking-due"><small>TOTAL A PAGAR</small><strong>{{currency(parkingQuote?.total||0)}}</strong></div><p class="parking-alert">COBRO NO DISPONIBLE: la terminal bancaria aún no está integrada. Este ticket permanece pendiente; no se registra ningún pago.</p><div class="parking-actions"><button class="btn-outline" @click="beginScan">OTRO TICKET</button><button class="btn-primary" @click="logout">FINALIZAR Y SALIR</button></div></div></template>
   <p v-if="parkingError" class="parking-alert parking-error">{{parkingError}}</p>
  </main>
  <div class="parking-bottom">JUSTO SIERRA · DOCKBUY · SISTEMA DE PRUEBAS · NO SE REALIZAN COBROS</div>
 </div>
 </template>
 <template v-else-if="view==='welcome'">
  <p v-if="sessionNotice" class="session-notice" role="status">{{sessionNotice}}</p>
  <div class="hero" style="background-image:linear-gradient(90deg,rgba(4,20,49,.32),rgba(4,20,49,.66)),url('/images/campus.jpg')"><div class="hero-copy"><span class="eyebrow">UNIVERSIDAD JUSTO SIERRA</span><h1>Bienvenido a tu<br><em>kiosco universitario</em></h1><p>Consulta información académica, conceptos de pago y servicios institucionales de manera sencilla.</p><button class="btn-primary hero-button" @click="view='login'">COMENZAR <ChevronRight :size="23"/></button><div class="hero-features"><span><ShieldCheck/> Acceso seguro</span><span><Wallet/> Consulta de pagos</span><span><GraduationCap/> Servicios escolares</span></div></div></div>
  <div class="welcome-brand"><button class="logo-home" aria-label="Justo Sierra — inicio" @click="home"><img src="/images/logo.jpg" alt="Justo Sierra"></button><h3>Educar para la vida</h3><p>PORTAL DE AUTOSERVICIO</p><div class="mini-bar"></div><button class="btn-outline" @click="view='login'">INGRESAR AL PORTAL</button><button class="btn-primary parking-welcome" @click="parkingHome"><CarFront :size="22"/> ESTACIONAMIENTO</button><button class="btn-outline parking-welcome" @click="openBilling()"><FileText :size="22"/> FACTURAR TICKET</button><small>Plataforma de demostración Dockbuy</small></div>
 </template>
 <template v-else-if="view==='login'">
  <section class="auth-left"><div class="auth-card"><button class="logo-home" aria-label="Justo Sierra — ir al inicio" @click="logout"><img class="brand-logo" src="/images/logo.jpg" alt="Justo Sierra"></button><h2>BIENVENIDO</h2><p class="muted upper">PORTAL DE ALUMNOS</p><div class="red-line"></div><p class="instruction">Ingresa tus credenciales para continuar</p><form @submit.prevent="login"><label>Matrícula del estudiante</label><div class="input-wrap"><UserRound :size="19"/><input v-model.trim="matricula" inputmode="none" readonly @click="openKeyboard('matricula')" @focus="openKeyboard('matricula')" autocomplete="off" placeholder="Ingresa tu matrícula" required></div><label>Contraseña / PIN demo</label><div class="input-wrap"><LockKeyhole :size="19"/><input v-model="pin" inputmode="none" readonly @click="openKeyboard('pin')" @focus="openKeyboard('pin')" :type="showPin?'text':'password'" placeholder="Ingresa tu PIN" required><button type="button" class="inline-btn" @click="showPin=!showPin"><EyeOff v-if="showPin" :size="19"/><Eye v-else :size="19"/></button></div><p v-if="error" class="error">{{error}}</p><button class="btn-primary full" :disabled="busy">{{busy?'VALIDANDO...':'ENTRAR'}} <ChevronRight :size="18"/></button></form><div class="auth-links"><button class="back" @click="logout"><ArrowLeft :size="18"/> REGRESAR AL INICIO</button><span>Recuperación de acceso: universidad</span></div><div class="auth-demo">DEMO · Matrícula 202210 o 202211 · PIN 1234</div></div></section>
  <section class="auth-image"><div class="auth-features"><div><span><ShieldCheck/></span><p><b>SEGURIDAD</b><small>Acceso protegido a tu información.</small></p></div><div><span><Wifi/></span><p><b>ACCESO 24/7</b><small>Consulta la información en un solo lugar.</small></p></div><div><span><GraduationCap/></span><p><b>TODO EN UN SOLO LUGAR</b><small>Servicios académicos y administrativos.</small></p></div></div></section>
 </template>
 <template v-else>

  <main class="content"><div class="breadcrumb"><button @click="home"><Home :size="16"/> Inicio</button><ChevronRight :size="14"/> <span>{{view==='dashboard'?'Mis servicios':view==='charges'?'Servicios y pagos':view==='history'?'Mis comprobantes':'Mi información'}}</span></div>
   <template v-if="view==='dashboard'">
    <section class="dashboard-welcome"><div><span class="eyebrow red">TU ESPACIO DE AUTOSERVICIO</span><h1>Hola, {{student?.nombre.split(' ')[0]}}</h1><p>Elige un servicio. Al terminar, pulsa Finalizar y salir.</p></div><button class="logo-home" aria-label="Logo Justo Sierra — inicio" @click="home"><img src="/images/logo.jpg" alt="Justo Sierra"></button></section>
    <div class="dashboard-stats"><div><span>SALDO PENDIENTE DEMO</span><strong>{{currency(pendingTotal)}}</strong></div><div><span>CONCEPTOS PENDIENTES</span><strong>{{charges.length}}</strong></div><div><span>PRÓXIMO PASO</span><b>{{charges.length?'Revisa tus conceptos por vencimiento':'Consulta tus comprobantes'}}</b></div></div>
    <div class="service-grid"><button class="service-card primary-service" @click="navigate('charges')"><Wallet :size="35"/><span>01 · PAGOS</span><h2>Servicios y pagos</h2><p>Colegiaturas, inscripción, transporte y servicios escolares.</p><b>CONSULTAR CONCEPTOS <ChevronRight :size="20"/></b></button><button class="service-card" @click="navigate('history')"><ReceiptText :size="35"/><span>02 · COMPROBANTES</span><h2>Mis comprobantes</h2><p>Recupera tu ticket, reimprime o envíalo por correo.</p><b>VER COMPROBANTES <ChevronRight :size="20"/></b></button><button class="service-card" @click="navigate('student')"><UserRound :size="35"/><span>03 · PERFIL</span><h2>Mi información</h2><p>Consulta tus datos académicos de demostración.</p><b>VER INFORMACIÓN <ChevronRight :size="20"/></b></button></div>
    <div class="secondary-services"><button @click="openBilling()"><FileText :size="28"/><span><b>Facturar un ticket</b><small>Escanea tu QR y recibe una factura de prueba.</small></span><ChevronRight :size="20"/></button><button @click="navigate('parking')"><CarFront :size="28"/><span><b>Estacionamiento</b><small>Genera un boleto o consulta tu estancia.</small></span><ChevronRight :size="20"/></button></div>
    <div class="kiosk-guidance"><ShieldCheck :size="22"/><p>Tu selección se conserva al cambiar de servicio durante esta sesión. Al salir se limpian tus datos de la pantalla.</p><button class="btn-outline" @click="helpOpen=true"><HelpCircle :size="18"/> AYUDA</button></div>
   </template>
   <template v-else-if="view==='student'"><h1>MI INFORMACIÓN</h1><p class="subtitle">INFORMACIÓN ACADÉMICA DEL ESTUDIANTE</p><div class="profile-card"><div class="avatar"><UserRound :size="46"/></div><div><h2>{{student?.nombre}}</h2><p>{{student?.matricula}}</p></div></div><div class="detail-grid"><div v-for="[key,val] in [['Matrícula',student?.matricula],['Nivel académico',student?.nivel],['Grado',student?.grado],['Grupo',student?.grupo],['Ciclo escolar',student?.ciclo],['Correo de prueba',student?.email]]" :key="key"><span>{{key}}</span><b>{{val}}</b></div></div><div class="notice">Información completamente ficticia, obtenida de la API local de demostración.</div></template>
   <PaymentHistory ref="historyFlow" v-else-if="view==='history'" :token="token" @back="home" @expired="expireSession" @billing="openBilling" @finish="logout"/>
   <PaymentFlow ref="paymentFlow" :selection="draftSelection" @selection="draftSelection=$event" @locked="navigationLocked=$event" v-else-if="view==='charges'" :token="token" :charges="charges" @expired="expireSession" @updated="charges=$event" @billing="openBilling" @back="home" @finish="logout"/>
  </main>
 </template>
 <div v-if="keyboardOpen && ['login','parking'].includes(view)" class="keyboard-backdrop" @click="closeKeyboard"></div>
 <section v-if="keyboardOpen && ['login','parking'].includes(view)" class="touch-keyboard" aria-label="Teclado táctil">
   <div class="keyboard-header"><div><span class="keyboard-dot"></span><b>TECLADO TÁCTIL</b><small>{{activeField==='matricula'?'MATRÍCULA':activeField==='parking'?'FOLIO DE ESTACIONAMIENTO':'CONTRASEÑA / PIN'}}</small></div><button type="button" class="keyboard-close" @click="closeKeyboard">CERRAR ✕</button></div>
   <div class="keyboard-input-preview"><span>{{activeField==='matricula'?matricula.replace(/./g,'•'):activeField==='parking'?parkingCode:pin.replace(/./g,'•')}}</span><span class="keyboard-cursor">▏</span></div>
   <div class="keyboard-rows" :class="{'numeric-layout':activeField==='matricula'||activeField==='pin'}"><div class="keyboard-row" v-for="(row,i) in keyboardRows" :key="i"><button v-for="key in row" :key="key" type="button" class="keyboard-key" :class="{'keyboard-special':['BORRAR','MAYÚS','ESPACIO'].includes(key),'keyboard-done':key==='LISTO'}" @click="pressKey(key)">{{key==='BORRAR'?'⌫':key==='LISTO'?'LISTO ✓':key}}</button></div></div>
   <p class="keyboard-help">Toca los números para escribir · pulsa LISTO para continuar</p>
 </section>
 <div v-if="helpOpen" class="kiosk-modal-backdrop" @click.self="helpOpen=false" @keydown="trapFocus"><section class="kiosk-modal" role="dialog" aria-modal="true" aria-labelledby="help-title"><button ref="helpClose" class="icon-close help-close" @click="helpOpen=false" aria-label="Cerrar ayuda">✕</button><h2 id="help-title">¿CÓMO USAR EL KIOSCO?</h2><ol class="help-steps"><li>Usa el menú superior para cambiar de servicio. El logo vuelve al inicio; Regresar vuelve al paso anterior y Salir termina la sesión.</li><li>Selecciona los conceptos en orden de vencimiento y revisa el resumen.</li><li>Confirma el pago demo. Retira tu ticket o solicita el envío por correo.</li><li>Escanea el QR en este kiosco para generar una factura de prueba.</li><li>Si no sale el ticket, recupéralo desde Mis comprobantes.</li></ol><p>No ingreses datos bancarios. Al terminar, cierra tu sesión.</p><button class="btn-primary full" @click="helpOpen=false">ENTENDIDO</button></section></div>
 <footer><div><button class="logo-home" :disabled="navigationLocked" @click="home" aria-label="Inicio desde el pie de página"><img src="/images/logo.jpg" alt="Logo Justo Sierra"></button><span><b>Justo Sierra</b><small>Educar para la vida</small></span></div><p>PLATAFORMA DE DEMOSTRACIÓN · DOCKBUY · 2026<br>Pagos y facturas de prueba · sin cobro real ni validez fiscal</p></footer>
</div>
</template>
