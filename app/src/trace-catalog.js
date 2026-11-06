export const screens = {dashboard:'Mis servicios',charges:'Pagos',history:'Comprobantes',billing:'Facturar',parking:'Estacionamiento',student:'Mi información',campus:'Campus'}
export const defaultSteps = {dashboard:'main',charges:'select',history:'list',billing:'scan',parking:'menu',student:'main',campus:'hub'}
export const campusScreens = ['hub','turnos','tramites','seguimiento','reinscripcion','citas','horario','biblioteca','credencial','actividades','directorio','encuesta']
export const steps = new Set(['main','select','review','processing','receipt','scan','document','invoice','list','menu','issued','quote',...campusScreens])
export const overlays = new Set(['','help','accessibility','idle','campus.confirm','campus.tracking','email.edit','email.review','email.result'])
export const actions = {
  'surface.tap':'Toque en la pantalla', 'control.unmapped':'Control sin instrumentar',
  'nav.home':'Ir al inicio', 'nav.back':'Regresar', 'session.exit':'Finalizar y salir',
  'help.open':'Abrir ayuda', 'help.close':'Cerrar ayuda',
  'accessibility.open':'Abrir/cerrar accesibilidad', 'accessibility.text':'Cambiar tamaño de texto',
  'accessibility.contrast':'Cambiar contraste', 'accessibility.time':'Cambiar tiempo de sesión',
  'parking.issue':'Generar boleto', 'parking.scan':'Consultar otro boleto', 'parking.lookup':'Consultar importe', 'parking.reprint':'Reimprimir boleto',
  'payment.add':'Agregar concepto', 'payment.remove':'Devolver concepto', 'payment.review':'Continuar al resumen',
  'payment.retry':'Reintentar pago', 'payment.clear':'Cancelar selección', 'payment.edit':'Modificar selección',
  'payment.confirm':'Confirmar pago demo', 'payment.another':'Hacer otro pago',
  'billing.lookup':'Buscar comprobante', 'billing.generate':'Generar factura demo', 'billing.another':'Escanear otro comprobante',
  'history.retry':'Actualizar comprobantes', 'history.open':'Abrir comprobante', 'document.reprint':'Reimprimir documento',
  'email.open':'Abrir envío por correo', 'email.close':'Cerrar envío por correo', 'email.review':'Revisar destinatario',
  'email.send':'Confirmar/reintentar envío', 'email.edit':'Corregir destinatario', 'email.status':'Consultar estado del envío',
  'campus.refresh':'Actualizar servicios', 'campus.category':'Filtrar categoría', 'campus.appointment':'Agendar cita',
  'campus.rating':'Seleccionar valoración', 'campus.topic':'Seleccionar motivo de opinión', 'campus.survey':'Enviar opinión',
  'campus.procedure':'Solicitar constancia/credencial', 'campus.reenroll':'Solicitar reinscripción', 'campus.turn':'Solicitar turno',
  'campus.department':'Seleccionar área', 'campus.day':'Seleccionar día', 'campus.time':'Seleccionar horario', 'campus.reserve':'Reservar cita',
  'campus.renew':'Renovar préstamo', 'campus.book':'Reservar libro', 'campus.activity':'Inscribirse a actividad',
  'campus.tracking':'Ver seguimiento', 'campus.cancel':'Cancelar solicitud', 'campus.print':'Imprimir turno',
  'campus.dismiss':'Volver de confirmación', 'campus.confirm':'Confirmar solicitud', 'campus.close':'Cerrar seguimiento',
  'idle.resume':'Continuar sesión', 'scanner.read':'Leer un QR',
  ...Object.fromEntries(Object.entries(screens).map(([id,label])=>['nav.'+id,'Abrir '+label])),
  ...Object.fromEntries(campusScreens.map(id=>['campus.open.'+id,'Abrir campus: '+id])),
}
export const operationNames = new Set(['charges.load','history.load','payment.quote','payment.simulate','billing.lookup','billing.invoice','document.print','email.send','parking.issue','parking.quote','parking.print','campus.procedure','campus.turn','campus.appointment','campus.renew','campus.book','campus.activity','campus.cancel','campus.print','campus.survey'])
