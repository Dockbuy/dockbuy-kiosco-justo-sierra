import {Ticket,FileCheck2,ClipboardList,GraduationCap,CalendarDays,Map,Library,ContactRound,Palette,Building2,MessageSquareHeart} from 'lucide-vue-next'
export const modules=[
 {id:'turnos',title:'Turnos de atención',description:'Elige un área y sigue tu lugar en la fila.',category:'Atención',icon:Ticket},
 {id:'tramites',title:'Constancias',description:'Solicita documentos y recíbelos por correo al autorizarse.',category:'Escolares',icon:FileCheck2},
 {id:'seguimiento',title:'Mis trámites',description:'Consulta folios, avances y próximos pasos.',category:'Escolares',icon:ClipboardList},
 {id:'reinscripcion',title:'Reinscripción',description:'Revisa pagos, documentos y validación académica.',category:'Escolares',icon:GraduationCap},
 {id:'citas',title:'Agendar una cita',description:'Reserva un horario disponible en tu área de atención.',category:'Atención',icon:CalendarDays},
 {id:'horario',title:'Horario y salones',description:'Ubica tu siguiente clase y explora el campus.',category:'Campus',icon:Map},
 {id:'biblioteca',title:'Biblioteca',description:'Consulta préstamos, renueva o reserva un libro.',category:'Campus',icon:Library},
 {id:'credencial',title:'Mi credencial',description:'Solicita una reposición y consulta cuándo recogerla.',category:'Escolares',icon:ContactRound},
 {id:'actividades',title:'Actividades y talleres',description:'Encuentra una actividad y aparta tu lugar.',category:'Campus',icon:Palette},
 {id:'directorio',title:'Directorio y avisos',description:'Áreas, ubicaciones, horarios y requisitos de atención.',category:'Atención',icon:Building2},
 {id:'encuesta',title:'Tu opinión',description:'Cuéntanos cómo fue tu experiencia en el kiosco.',category:'Atención',icon:MessageSquareHeart},
]
export const statuses={recibido:'Recibido',revision:'En revisión',listo:'Listo',entregado:'Entregado',rechazado:'Requiere atención',cancelado:'Cancelado',reservado:'Reservado',espera:'En espera',llamado:'Pasa a ventanilla',completado:'Completado',inscrito:'Inscrito'}
export const money=n=>new Intl.NumberFormat('es-MX',{style:'currency',currency:'MXN'}).format(n||0)
export const formatDate=s=>s?new Date(s.length===10?s+'T12:00:00':s).toLocaleString('es-MX',{dateStyle:'medium',...(s.length>10?{timeStyle:'short'}:{})}):''
