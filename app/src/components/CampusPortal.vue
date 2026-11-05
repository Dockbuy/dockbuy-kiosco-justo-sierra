<script setup>
import {computed,onMounted,onUnmounted,ref,watch,nextTick} from 'vue'
import {ArrowLeft,ArrowRight,Search,CheckCircle2,Clock3,RefreshCw,MapPin,Info,Check,ChevronRight,ShieldCheck} from 'lucide-vue-next'
import {request} from '../api'
import {trapFocus} from '../modal-focus'
import {modules,statuses,money,formatDate} from '../campus-catalog'
import TouchInput from './TouchInput.vue'
import EmailDelivery from './EmailDelivery.vue'
const props=defineProps({token:String,initial:{type:String,default:'hub'},session:String})
const emit=defineEmits(['back','login','payments','updated','expired','locked'])
const page=ref(props.initial),category=ref('Todos'),search=ref(''),data=ref(null),info=ref(null),loading=ref(true),busy=ref(false),error=ref(''),notice=ref(''),confirmation=ref(null),details=ref(null),department=ref('escolares'),selectedDay=ref(''),slot=ref(''),notes=ref(''),rating=ref(0),topic=ref('facilidad'),surveyDone=ref(false),confirmButton=ref(null)
const controller=new AbortController();let poll,refreshSequence=0,completed=false
const current=computed(()=>modules.find(m=>m.id===page.value))
const filtered=computed(()=>modules.filter(m=>(category.value==='Todos'||m.category===category.value)&&(`${m.title} ${m.description}`).toLocaleLowerCase('es').includes(search.value.toLocaleLowerCase('es'))))
const disabled=computed(()=>info.value?.disabled.includes(page.value))
const slots=computed(()=>data.value?.slots[department.value]||[])
const days=computed(()=>[...new Set(slots.value.map(s=>s.slice(0,10)))])
const times=computed(()=>slots.value.filter(s=>s.startsWith(selectedDay.value)))
const records=computed(()=>data.value?.records.filter(r=>{
 if(page.value==='seguimiento')return true
 if(page.value==='tramites')return r.kind==='procedure'&&['estudios','calificaciones'].includes(r.item)
 const mapping={turnos:'turn',citas:'appointment',biblioteca:'book',actividades:'activity'}
 return mapping[page.value]?r.kind===mapping[page.value]:r.kind==='procedure'&&r.item===page.value
})||[])
const procedures=computed(()=>info.value?.procedures.filter(p=>page.value==='tramites'?['estudios','calificaciones'].includes(p.id):p.id===page.value)||[])
const checklist=computed(()=>data.value?.checklist||{})
const ready=computed(()=>checklist.value.payments&&checklist.value.documents&&checklist.value.academic)
function name(r){return [...(info.value?.procedures||[]),...(info.value?.departments||[]),...(data.value?.activities||[])].find(i=>i.id===r.item)?.name||data.value?.books.find(b=>b.id===r.item)?.title||r.item}
function canCancel(r){return ({procedure:['recibido'],turn:['espera'],appointment:['reservado'],book:['reservado'],activity:['inscrito']}[r.kind]||[]).includes(r.status)&&!(r.fee>0&&r.paid)}
function active(kind,item){return data.value?.records.some(r=>r.kind===kind&&r.item===item&&!['cancelado','rechazado','completado','entregado'].includes(r.status))}
function track(event,module=page.value){if(module!=='hub')request('/campus/event',{method:'POST',body:{session:props.session,module,event},timeout:4000}).catch(()=>{})}
async function refresh(quiet=false){
 const seq=++refreshSequence
 if(!quiet)loading.value=true
 try{
  const values=await Promise.all([request('/campus/public',{signal:controller.signal}),props.token?request('/campus/state',{token:props.token,signal:controller.signal}):null])
  if(controller.signal.aborted||seq!==refreshSequence)return
  info.value=values[0];data.value=values[1]
  if(!days.value.includes(selectedDay.value))selectedDay.value=days.value[0]||''
 }catch(e){if(controller.signal.aborted)return;if(e.status===401)emit('expired');else if(!quiet)error.value=e.status===404?'Actualiza los cambios y reinicia la API para activar los servicios del campus.':e.message}
 finally{if(seq===refreshSequence&&!controller.signal.aborted)loading.value=false}
}
function go(id){if(busy.value)return;if(page.value!=='hub'&&!completed)track('abandon');completed=false;page.value=id;details.value=null;error.value='';notice.value='';slot.value='';notes.value='';track('open');window.scrollTo(0,0)}
function goBack(){if(confirmation.value){if(!busy.value)confirmation.value=null}else if(details.value)details.value=null;else if(page.value!=='hub')go('hub');else emit('back')}
defineExpose({goBack,open:go})
function ask(payload,title,body){confirmation.value={payload:{...payload,request_id:crypto.randomUUID()},title,body};error.value=''}
async function execute(){
 if(busy.value)return
 busy.value=true;emit('locked',true);error.value=''
 try{
  const result=await request('/campus/action',{method:'POST',token:props.token,body:confirmation.value.payload,signal:controller.signal})
  if(controller.signal.aborted)return
  notice.value=result.folio?`Solicitud registrada: ${result.folio}. Consulta el avance aquí o en Mis trámites.`:result.message||'Cambio guardado.'
  confirmation.value=null;completed=true;track('complete');await refresh(true);emit('updated')
 }catch(e){if(!controller.signal.aborted){error.value=e.message;if(e.status===401)emit('expired')}}
 finally{if(!controller.signal.aborted){busy.value=false;emit('locked',false)}}
}
async function printTurn(r){
 if(busy.value)return
 busy.value=true;error.value=''
 try{await request('/campus/print-turn',{method:'POST',token:props.token,body:{folio:r.folio},signal:controller.signal});if(!controller.signal.aborted)notice.value='Turno enviado a la impresora del kiosco.'}catch(e){if(!controller.signal.aborted)error.value=e.message}finally{if(!controller.signal.aborted)busy.value=false}
}
async function survey(){
 if(busy.value||!rating.value)return
 busy.value=true;error.value=''
 try{await request('/campus/survey',{method:'POST',body:{session:props.session,score:rating.value,topic:topic.value},signal:controller.signal});if(!controller.signal.aborted){surveyDone.value=true;completed=true;track('complete')}}catch(e){if(!controller.signal.aborted)error.value=e.message}finally{busy.value=false}
}
watch(()=>props.initial,id=>{if(id!==page.value)go(id)})
watch(department,()=>{selectedDay.value=days.value[0]||'';slot.value=''})
watch(selectedDay,()=>slot.value='')
watch(details,async value=>{if(value){await nextTick();document.querySelector('[aria-labelledby=tracking-title] button')?.focus()}})
watch(confirmation,async value=>{if(value){await nextTick();confirmButton.value?.focus()}})
onMounted(()=>{refresh();track('open');poll=setInterval(()=>{if(!busy.value&&!confirmation.value&&!document.hidden)refresh(true)},15000)})
onUnmounted(()=>{if(!completed&&page.value!=='hub')track('abandon');controller.abort();clearInterval(poll);emit('locked',false)})
</script>
<template>
 <section class="campus-portal" :aria-busy="loading||busy">
  <div class="campus-heading"><div><span class="eyebrow red">CAMPUS · AUTOSERVICIO</span><h1>{{current?.title||'¿Qué necesitas hoy?'}}</h1><p>{{current?.description||'Tus servicios escolares, de atención y vida universitaria en un solo lugar.'}}</p></div><button class="campus-refresh" :disabled="busy||loading" @click="refresh()" aria-label="Actualizar servicios"><RefreshCw :size="20"/> Actualizar</button></div>
  <div class="campus-demo"><Info :size="18"/><span>Demostración: datos, horarios, costos y políticas ficticios. Las solicitudes se guardan para probar el flujo; no se envían a la institución.</span></div>
  <p v-if="error&&!confirmation" class="flow-error" role="alert">{{error}}</p><p v-if="notice" class="campus-success" role="status"><CheckCircle2 :size="22"/>{{notice}}</p>
  <div v-if="loading&&!info" class="campus-empty">Cargando servicios…</div>
  <template v-else-if="info">
   <div v-if="page==='hub'">
    <div class="campus-announcement" v-for="a in info.announcements" :key="a.title"><span class="announcement-dot"></span><div><b>{{a.title}}</b><p>{{a.text}}</p></div></div>
    <div class="campus-finder"><TouchInput v-model="search" label="Buscar un servicio" placeholder="Ej. constancia, biblioteca, cita…"/><div class="campus-tabs" aria-label="Categorías"><button v-for="c in ['Todos','Escolares','Atención','Campus']" :key="c" :aria-pressed="category===c" @click="category=c">{{c}}</button></div></div>
    <div class="campus-grid"><button v-for="m in filtered" :key="m.id" class="campus-service" @click="go(m.id)"><span class="campus-icon"><component :is="m.icon" :size="26"/></span><small>{{m.category}}</small><h2>{{m.title}}</h2><p>{{m.description}}</p><b>{{info.disabled.includes(m.id)?'Consultar disponibilidad':'Abrir servicio'}} <ArrowRight :size="18"/></b></button></div><p v-if="!filtered.length" class="campus-empty">No encontramos ese servicio. Prueba otra palabra o categoría.</p>
   </div>
   <template v-else>
    <button class="campus-back" @click="go('hub')" :disabled="busy"><ArrowLeft :size="18"/> Todos los servicios</button>
    <p v-if="disabled" class="campus-warning">Este servicio está temporalmente fuera de atención. Puedes consultar tus registros anteriores y el directorio.</p>
    <template v-if="page==='directorio'">
     <div class="campus-announcement" v-for="a in info.announcements" :key="a.title"><Info :size="24"/><div><b>{{a.title}}</b><p>{{a.text}}</p></div></div>
     <div class="campus-grid two"><article class="campus-panel" v-for="d in info.departments" :key="d.id"><span class="campus-tag">{{d.id}}</span><h2>{{d.name}}</h2><p><MapPin :size="18"/> {{d.location}}</p><p><Clock3 :size="18"/> {{d.hours}}</p><dl><dt>Antes de acudir</dt><dd>{{d.requirements}}</dd><dt>Contacto</dt><dd>{{d.contact}}</dd></dl><button class="btn-outline" @click="department=d.id;go('citas')">AGENDAR CITA</button></article></div>
     <div v-if="info.called.length" class="campus-panel"><h2>Turnos en atención</h2><p v-for="t in info.called" :key="t.folio"><b>{{t.folio}}</b> · {{info.departments.find(d=>d.id===t.department)?.name}}</p></div>
    </template>
    <template v-else-if="page==='encuesta'">
     <div class="campus-panel survey-panel"><template v-if="!surveyDone"><h2>¿Cómo fue tu experiencia?</h2><p>Una respuesta por sesión. No pedimos tu nombre ni tu matrícula.</p><div class="rating-buttons"><button v-for="n in 5" :key="n" :aria-pressed="rating===n" @click="rating=n"><b>{{n}}</b><small>{{['Muy difícil','Difícil','Regular','Buena','Excelente'][n-1]}}</small></button></div><p>¿Qué influyó más?</p><div class="campus-tabs"><button v-for="[id,label] in [['facilidad','Facilidad'],['rapidez','Rapidez'],['atencion','Atención']]" :key="id" :aria-pressed="topic===id" @click="topic=id">{{label}}</button></div><button class="btn-primary" :disabled="!rating||busy||disabled" @click="survey">{{busy?'GUARDANDO…':'ENVIAR OPINIÓN'}}</button></template><template v-else><CheckCircle2 :size="52"/><h2>Gracias por ayudarnos a mejorar</h2><p>Tu opinión quedó registrada.</p><button class="btn-outline" @click="go('hub')">VOLVER A SERVICIOS</button></template></div>
    </template>
    <div v-else-if="!token" class="campus-empty"><ShieldCheck :size="44"/><h2>Ingresa para usar este servicio</h2><p>Tu matrícula nos permite mostrar solamente tus solicitudes.</p><button class="btn-primary" @click="emit('login',page)">INGRESAR AL PORTAL</button></div>
    <template v-else-if="data">
     <template v-if="page==='tramites'||page==='credencial'"><div class="campus-grid two"><article v-for="p in procedures" :key="p.id" class="campus-panel"><span class="campus-tag">{{p.days}} días hábiles · referencia demo</span><h2>{{p.name}}</h2><p>{{p.requirements}}</p><strong class="campus-price">{{money(p.fee)}} <small>MXN · pago demo</small></strong><p>{{p.id==='credencial'?'Recoge en Servicios Escolares cuando el estado sea Listo.':'Entrega por correo después de la autorización administrativa.'}}</p><button class="btn-primary" :disabled="disabled||active('procedure',p.id)" @click="ask({action:'procedure',item:p.id},p.name,`Se generará un concepto de ${money(p.fee)} en Servicios y pagos. Los conceptos se pagan en orden de vencimiento. La autorización se revisa después del pago demo.`)">{{active('procedure',p.id)?'SOLICITUD ACTIVA':'SOLICITAR'}}</button></article></div><div class="campus-steps"><span>1. Solicita</span><ChevronRight/><span>2. Paga en orden</span><ChevronRight/><span>3. Revisión</span><ChevronRight/><span>4. Entrega</span></div></template>
     <template v-else-if="page==='reinscripcion'"><div class="campus-panel"><h2>Tu ruta para el próximo ciclo</h2><p>El personal valida tus documentos e historial. Aquí puedes revisar el avance.</p><div class="checklist-row" v-for="[key,title,description] in [['payments','Pagos al corriente',`Saldo pendiente demo: ${money(checklist.balance)}`],['documents','Documentación validada','El personal revisa los documentos entregados en ventanilla.'],['academic','Validación académica','Servicios Escolares revisa tu situación académica.']]" :key="key"><CheckCircle2 v-if="checklist[key]" :size="28"/><Clock3 v-else :size="28"/><div><h3>{{title}}</h3><p>{{description}}</p></div><span class="campus-status" :class="{done:checklist[key]}">{{checklist[key]?'Completo':'Pendiente'}}</span></div><div class="campus-actions"><button v-if="!checklist.payments" class="btn-outline" @click="emit('payments')">REVISAR PAGOS</button><button class="btn-primary" :disabled="!ready||disabled||active('procedure','reinscripcion')" @click="ask({action:'procedure',item:'reinscripcion'},'Solicitar reinscripción','Tus validaciones están completas. Registraremos la solicitud para revisión final del personal.')">SOLICITAR REINSCRIPCIÓN</button></div></div></template>
     <template v-else-if="page==='turnos'"><div class="campus-grid two"><article v-for="d in info.departments" :key="d.id" class="campus-panel"><h2>{{d.name}}</h2><p>{{d.location}}</p><p>{{d.hours}}</p><button class="btn-primary" :disabled="disabled||data.records.some(r=>r.kind==='turn'&&['espera','llamado'].includes(r.status))" @click="ask({action:'turn',item:d.id},`Turno para ${d.name}`,'Se asignará un folio de atención. Consérvalo en pantalla; la fila se atiende por orden de llegada. Los turnos son válidos hoy.')">TOMAR TURNO</button></article></div></template>
     <template v-else-if="page==='citas'"><div class="campus-panel"><h2>1. Elige el área</h2><div class="campus-tabs"><button v-for="d in info.departments" :key="d.id" :aria-pressed="department===d.id" @click="department=d.id">{{d.name}}</button></div><h2>2. Elige un día</h2><div class="campus-tabs date-tabs"><button v-for="day in days" :key="day" :aria-pressed="selectedDay===day" @click="selectedDay=day">{{formatDate(day)}}</button></div><h2>3. Elige un horario</h2><div class="campus-tabs"><button v-for="s in times" :key="s" :aria-pressed="slot===s" @click="slot=s">{{s.slice(11)}} h</button></div><p v-if="!times.length" class="campus-warning">No hay horarios disponibles para ese día.</p><p>Horario local del kiosco · una reserva activa por área · duración demo: 1 hora.</p><button class="btn-primary" :disabled="!slot||disabled||active('appointment',department)" @click="ask({action:'appointment',item:department,detail:slot},'Confirmar cita',`${info.departments.find(d=>d.id===department)?.name} · ${formatDate(slot)}. Puedes cancelarla desde esta pantalla.`)">RESERVAR CITA</button></div></template>
     <template v-else-if="page==='horario'"><div class="campus-grid two"><div class="campus-panel"><h2>Tu semana</h2><div class="schedule-row" v-for="s in data.schedule" :key="s.day"><span><b>{{s.day}}</b><small>{{s.time}}</small></span><div><h3>{{s.subject}}</h3><p>{{s.room}} · {{s.location}}</p></div></div></div><div class="campus-panel"><h2>Ubica tu salón</h2><p>Mapa esquemático de demostración. No representa la distribución real del plantel.</p><div class="campus-map"><div class="map-building a"><b>EDIFICIO A</b><span>Caja · Escolares<br>A-105 · A-201</span></div><div class="map-building b"><b>EDIFICIO B</b><span>Becas · Laboratorio B-102</span></div><div class="map-garden">PLAZA CENTRAL</div><div class="map-building c"><b>EDIFICIO C</b><span>Biblioteca</span></div><div class="map-field">CANCHA DEPORTIVA</div><div class="map-entry"><MapPin :size="20"/> Acceso · Kiosco</div></div></div></div></template>
     <template v-else-if="page==='biblioteca'"><div class="campus-panel"><h2>Mis préstamos</h2><p v-if="!data.loans.length">No tienes préstamos activos.</p><div class="loan-row" v-for="loan in data.loans" :key="loan.id"><div><h3>{{data.books.find(b=>b.id===loan.book)?.title}}</h3><p>Devolución: {{formatDate(loan.due)}} · {{loan.renewed?'Renovación utilizada':'Una renovación disponible de 7 días'}}</p></div><button class="btn-outline" :disabled="!!loan.renewed||disabled" @click="ask({action:'renew',id:loan.id},'Renovar préstamo','Se agregarán 7 días al vencimiento, si está vigente y no hay reservas.')">RENOVAR</button></div></div><h2 class="campus-section-title">Catálogo disponible</h2><div class="campus-grid"><article class="campus-panel" v-for="book in data.books" :key="book.id"><span class="campus-tag">{{book.available}} disponibles</span><h2>{{book.title}}</h2><p>{{book.author}}</p><button class="btn-primary" :disabled="disabled||!book.available||active('book',book.id)" @click="ask({action:'book',item:book.id},'Reservar libro',`${book.title}. Recoge en biblioteca; el personal registrará la entrega y el inicio del préstamo.`)">{{active('book',book.id)?'RESERVADO':'RESERVAR LIBRO'}}</button></article></div></template>
     <template v-else-if="page==='actividades'"><div class="campus-grid"><article v-for="a in data.activities" :key="a.id" class="campus-panel"><span class="campus-tag">{{a.enabled?`${a.available} lugares disponibles`:'Inscripciones cerradas'}}</span><h2>{{a.name}}</h2><p><Clock3 :size="18"/> {{a.schedule}}</p><p><MapPin :size="18"/> {{a.location}}</p><p>Sin costo en esta demostración.</p><button class="btn-primary" :disabled="disabled||!a.enabled||!a.available||active('activity',a.id)" @click="ask({action:'activity',item:a.id},'Confirmar inscripción',`${a.name} · ${a.schedule}. Revisa que no coincida con tus clases. Podrás cancelar desde aquí.`)">{{active('activity',a.id)?'YA ESTÁS INSCRITO':'INSCRIBIRME'}}</button></article></div></template>
     <template v-if="!['horario'].includes(page)"><div class="campus-section-head"><h2>{{page==='seguimiento'?'Tu actividad y solicitudes':'Mis registros'}}</h2><button v-if="page!=='seguimiento'" @click="go('seguimiento')">Ver todo <ArrowRight :size="18"/></button></div><div v-if="!records.length" class="campus-empty"><p>Aún no tienes registros en este servicio. Tus solicitudes aparecerán aquí.</p></div><div class="campus-records"><article class="campus-record" v-for="r in records" :key="r.folio"><div><span class="campus-folio">{{r.folio}}</span><h3>{{name(r)}}</h3><p>{{r.kind==='appointment'?formatDate(r.detail):formatDate(r.created)}}</p><p v-if="r.kind==='turn'&&r.status==='espera'">{{r.ahead}} turnos antes del tuyo en esta área.</p><p v-if="r.kind==='turn'&&r.status==='llamado'" class="turn-called">Es tu turno. Acude a {{name(r)}}.</p><p v-if="r.fee>0">{{money(r.fee)}} · {{r.paid?'Pago demo registrado':'Pendiente: paga en orden de vencimiento'}}</p><p v-if="r.item==='credencial'&&r.status==='listo'">Recoge en Servicios Escolares con tu identificación.</p><p v-if="r.status==='rechazado'">Acude al área responsable para aclarar el trámite{{r.paid&&r.fee?' y revisar el pago demo; no se generan devoluciones automáticas':''}}.</p></div><div class="record-actions"><span class="campus-status" :class="{done:['listo','entregado','completado','inscrito'].includes(r.status),called:r.status==='llamado'}">{{statuses[r.status]}}</span><button class="btn-outline" @click="details=r">VER SEGUIMIENTO</button><button v-if="r.fee&&!r.paid&&!['cancelado','rechazado'].includes(r.status)" class="btn-primary" @click="emit('payments')">IR A PAGOS</button><button v-if="canCancel(r)" class="campus-cancel" :disabled="busy" @click="ask({action:'cancel',folio:r.folio},'Cancelar solicitud',`Se cancelará ${r.folio}. Si hay un concepto pendiente de este trámite, se retirará de tus pagos.`)">Cancelar solicitud</button><button v-if="r.kind==='turn'&&['espera','llamado'].includes(r.status)" class="btn-outline" :disabled="busy" @click="printTurn(r)">IMPRIMIR TURNO</button><EmailDelivery v-if="r.kind==='procedure'&&['estudios','calificaciones'].includes(r.item)&&['listo','entregado'].includes(r.status)" :code="r.folio" :token="token" campus/></div></article></div></template>
    </template>
   </template>
  </template>
  <div v-if="confirmation" class="kiosk-modal-backdrop" @keydown="trapFocus" @keydown.esc="!busy&&(confirmation=null)"><section class="kiosk-modal" role="dialog" aria-modal="true" aria-labelledby="confirm-campus-title"><span class="campus-tag">CONFIRMA TU SOLICITUD · DEMO</span><h2 id="confirm-campus-title">{{confirmation.title}}</h2><p>{{confirmation.body}}</p><p v-if="error" class="flow-error" role="alert">{{error}}</p><div class="campus-actions"><button class="btn-outline" :disabled="busy" @click="confirmation=null">VOLVER</button><button ref="confirmButton" class="btn-primary" :disabled="busy" @click="execute">{{busy?'GUARDANDO…':'CONFIRMAR SOLICITUD'}}</button></div></section></div>
  <div v-if="details" class="kiosk-modal-backdrop" @keydown="trapFocus" @keydown.esc="details=null"><section class="kiosk-modal" role="dialog" aria-modal="true" aria-labelledby="tracking-title"><h2 id="tracking-title">Seguimiento de {{details.folio}}</h2><p>{{name(details)}}</p><ol class="campus-timeline"><li v-for="(h,i) in details.history" :key="i"><b>{{statuses[h.status]}}</b><small>{{formatDate(h.created)}}</small><p>{{h.note}}</p></li></ol><button class="btn-primary full" @click="details=null">CERRAR SEGUIMIENTO</button></section></div>
 </section>
</template>
