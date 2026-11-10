<script setup>
import {computed} from 'vue'
import {Home,ArrowLeft,LogOut,Wallet,ReceiptText,FileText,CarFront,UserRound,HelpCircle,Wifi,WifiOff} from 'lucide-vue-next'
const props=defineProps({view:String,institutional:Boolean,authenticated:Boolean,student:Object,online:Boolean,clock:String,draftCount:Number,locked:Boolean})
const emit=defineEmits(['navigate','back','home','exit','help','accessibility'])
const services=computed(()=>props.institutional?[{id:'dashboard',label:'Mi consulta',icon:Home},{id:'charges',label:'Adeudos',icon:Wallet}]:props.authenticated?[
  {id:'dashboard',label:'Mis servicios',icon:Home},
  {id:'campus',label:'Campus',icon:UserRound},
  {id:'charges',label:'Pagos',icon:Wallet},
  {id:'history',label:'Comprobantes',icon:ReceiptText},
  {id:'billing',label:'Facturar',icon:FileText},
  {id:'parking',label:'Estacionamiento',icon:CarFront},
  {id:'student',label:'Mi información',icon:UserRound},
]:[{id:'welcome',label:'Inicio',icon:Home},{id:'campus',label:'Campus',icon:UserRound},{id:'login',label:'Portal de alumnos',icon:UserRound},{id:'billing',label:'Facturar ticket',icon:FileText},{id:'parking',label:'Estacionamiento',icon:CarFront}])
</script>
<template>
  <header class="kiosk-navigation no-print">
    <div class="navigation-main">
      <button data-trace-action="nav.home" class="navigation-brand" aria-label="Justo Sierra — ir al inicio" :disabled="locked" @click="emit('home')"><img src="/images/logo.jpg" alt=""><span><b>JUSTO SIERRA</b><small>KIOSCO DE AUTOSERVICIO</small></span></button>
      <div class="navigation-session"><b>{{authenticated?student?.nombre:'Bienvenido'}}</b><small>{{authenticated?'Matrícula '+student?.matricula:'Elige el servicio que necesitas'}}</small></div>
      <span class="navigation-connection" :class="{offline:!online}"><Wifi v-if="online" :size="16"/><WifiOff v-else :size="16"/> {{online?(institutional?'MODO SIPAA':'DEMO CONECTADA'):'API DESCONECTADA'}}</span>
      <div class="navigation-actions"><button data-trace-action="nav.back" :disabled="view==='dashboard'||locked" @click="emit('back')"><ArrowLeft :size="18"/> REGRESAR</button><button data-trace-action="accessibility.open" @click="emit('accessibility')" aria-label="Opciones de accesibilidad">Aa</button><button data-trace-action="help.open" @click="emit('help')" aria-label="Abrir ayuda"><HelpCircle :size="20"/></button><button data-trace-action="session.exit" class="navigation-exit" @click="emit('exit')"><LogOut :size="18"/> SALIR</button></div>
    </div>
    <nav class="service-navigation" aria-label="Servicios del kiosco"><button :data-trace-action="'nav.'+item.id" v-for="item in services" :key="item.id" :aria-current="view===item.id?'page':undefined" :disabled="locked" @click="emit('navigate',item.id)"><component :is="item.icon" :size="19"/><span>{{item.label}}</span><b v-if="item.id==='charges'&&draftCount" class="navigation-count">{{draftCount}}</b></button></nav>
  </header>
</template>
