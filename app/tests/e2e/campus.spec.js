import {test,expect} from '@playwright/test'
const api='http://127.0.0.1:8878/api'
test.beforeEach(async({request})=>{await request.post('http://127.0.0.1:8878/__test/reset',{data:{}})})
async function enter(page){await page.goto('/');await page.getByRole('button',{name:'INGRESAR AL PORTAL',exact:true}).click();await page.getByRole('button',{name:'ENTRAR',exact:true}).click();await page.getByRole('button',{name:/EXPLORAR TODOS LOS SERVICIOS/}).click();await expect(page.getByRole('heading',{name:'¿Qué necesitas hoy?'})).toBeVisible()}
async function service(page,title){await page.locator('.campus-service').filter({has:page.getByRole('heading',{name:title,exact:true})}).click()}
async function confirm(page){await page.getByRole('button',{name:'CONFIRMAR SOLICITUD',exact:true}).click();await expect(page.getByRole('dialog')).toHaveCount(0)}
async function admin(page){await page.goto('/admin');await page.getByLabel('Contraseña administrativa').fill('test-only-admin-123');await page.getByRole('button',{name:'INGRESAR A ADMINISTRACIÓN'}).click();await expect(page.getByRole('heading',{name:'Atención y trámites',exact:true})).toBeVisible()}
async function token(request,matricula='202210'){return (await (await request.post(api+'/auth/login',{data:{matricula,pin:'1234'}})).json()).access_token}

test('campus directory, all modules, touch search and accessibility',async({page})=>{
 const errors=[];page.on('pageerror',e=>errors.push(e.message))
 await enter(page)
 await expect(page.locator('.campus-service')).toHaveCount(11)
 await page.screenshot({path:'test-results/campus-hub.png',fullPage:true})
 await page.getByLabel('Buscar un servicio').fill('biblioteca')
 await expect(page.locator('.campus-service')).toHaveCount(1)
 await page.getByRole('button',{name:'LISTO ✓',exact:true}).click()
 await service(page,'Biblioteca')
 await expect(page.getByRole('heading',{name:'Mis préstamos',exact:true})).toBeVisible()
 await page.getByRole('button',{name:'RENOVAR',exact:true}).click();await confirm(page)
 await expect(page.getByRole('button',{name:'RENOVAR',exact:true})).toBeDisabled()
 await page.getByRole('button',{name:'Todos los servicios',exact:true}).click()
 await page.getByLabel('Buscar un servicio').fill('');await page.getByRole('button',{name:'LISTO ✓',exact:true}).click()
 await service(page,'Horario y salones');await expect(page.locator('.schedule-row')).toHaveCount(5)
 await page.getByRole('button',{name:'Aa · Accesibilidad'}).click();await page.getByRole('button',{name:'Texto grande',exact:true}).click();await expect(page.locator('.screen')).toHaveClass(/large-text/)
 await page.getByRole('button',{name:'Alto contraste',exact:true}).click();await page.screenshot({path:'test-results/campus-accessible.png',fullPage:true})
 await page.getByRole('button',{name:'SALIR',exact:true}).click();await expect(page.locator('.screen')).not.toHaveClass(/large-text|high-contrast/)
 expect(errors).toEqual([])
})

test('procedure payment, admin approval, tracking and email attachment flow',async({page,context,request})=>{
 await enter(page);await service(page,'Constancias')
 await page.locator('.campus-panel').filter({has:page.getByRole('heading',{name:'Constancia de estudios',exact:true})}).getByRole('button',{name:'SOLICITAR',exact:true}).click();await confirm(page)
 await expect(page.locator('.campus-record')).toContainText('Pendiente: paga en orden')
 const folio=(await page.locator('.campus-folio').innerText()).trim()
 const studentToken=await token(request)
 const charges=await (await request.get(api+'/charges',{headers:{Authorization:'Bearer '+studentToken}})).json()
 expect(charges.conceptos.some(c=>c.nombre.includes(folio))).toBeTruthy()
 const payment=await request.post(api+'/payments/simulate',{headers:{Authorization:'Bearer '+studentToken},data:{concept_ids:charges.conceptos.map(c=>c.id),request_id:crypto.randomUUID()}})
 expect(payment.ok()).toBeTruthy()
 const operator=await context.newPage();await admin(operator)
 const row=operator.locator('.campus-record').filter({hasText:folio})
 await row.getByRole('button',{name:'En revisión',exact:true}).click();await operator.getByRole('button',{name:'Confirmar cambio',exact:true}).click();await expect(operator.getByRole('dialog')).toHaveCount(0)
 await row.getByRole('button',{name:'Listo',exact:true}).click();await operator.getByLabel('Nota para el alumno').fill('Constancia lista para entrega por correo.');await operator.getByRole('button',{name:'Confirmar cambio',exact:true}).click();await expect(operator.getByRole('dialog')).toHaveCount(0)
 await operator.screenshot({path:'test-results/campus-admin.png',fullPage:true})
 await page.getByRole('button',{name:'Actualizar servicios'}).click()
 await expect(page.locator('.campus-record .campus-status')).toHaveText('Listo')
 await page.getByRole('button',{name:'VER SEGUIMIENTO'}).click();await expect(page.locator('.campus-timeline li')).toHaveCount(3);await page.getByRole('button',{name:'CERRAR SEGUIMIENTO'}).click()
 await page.getByRole('button',{name:'ENVIAR POR CORREO'}).click();await page.getByLabel('Tu correo',{exact:true}).fill('prueba@example.invalid');await page.getByLabel('Confirma tu correo',{exact:true}).fill('prueba@example.invalid');await page.getByRole('button',{name:'REVISAR DESTINATARIO'}).click();await page.getByRole('button',{name:'CONFIRMAR Y ENVIAR'}).click();await expect(page.getByRole('heading',{name:'ENVÍO ACEPTADO'})).toBeVisible()
 await operator.close()
})

test('appointment cancellation, activity enrollment and survey',async({page})=>{
 await enter(page);await service(page,'Agendar una cita')
 await page.getByRole('button',{name:'09:00 h',exact:true}).click();await page.getByRole('button',{name:'RESERVAR CITA'}).click();await confirm(page)
 await expect(page.locator('.campus-record .campus-status')).toHaveText('Reservado')
 await page.screenshot({path:'test-results/campus-appointment.png',fullPage:true})
 await page.getByRole('button',{name:'Cancelar solicitud',exact:true}).click();await confirm(page);await expect(page.locator('.campus-record .campus-status')).toHaveText('Cancelado')
 await page.getByRole('button',{name:'Todos los servicios',exact:true}).click();await service(page,'Actividades y talleres')
 await page.locator('.campus-panel').filter({has:page.getByRole('heading',{name:'Club de robótica',exact:true})}).getByRole('button',{name:'INSCRIBIRME'}).click();await confirm(page);await expect(page.locator('.campus-record .campus-status')).toHaveText('Inscrito')
 await page.getByRole('button',{name:'Todos los servicios',exact:true}).click();await service(page,'Tu opinión');await page.getByRole('button',{name:'5 Excelente'}).click();await page.getByRole('button',{name:'ENVIAR OPINIÓN'}).click();await expect(page.getByRole('heading',{name:'Gracias por ayudarnos a mejorar'})).toBeVisible()
})

test('admin permissions, cross-student ownership and stale API handling',async({request,page})=>{
 const student=await token(request),other=await token(request,'202211')
 expect((await request.get(api+'/admin/state',{headers:{Authorization:'Bearer '+student}})).status()).toBe(403)
 const adminToken=(await (await request.post(api+'/admin/login',{data:{password:'test-only-admin-123'}})).json()).access_token
 expect((await request.get(api+'/charges',{headers:{Authorization:'Bearer '+adminToken}})).status()).toBe(401)
 const record=await (await request.post(api+'/campus/action',{headers:{Authorization:'Bearer '+student},data:{action:'procedure',item:'credencial',request_id:crypto.randomUUID()}})).json()
 expect((await request.post(api+'/campus/action',{headers:{Authorization:'Bearer '+other},data:{action:'cancel',folio:record.folio}})).status()).toBe(404)
 await page.route('**/api/campus/public',route=>route.fulfill({status:404,contentType:'application/json',body:JSON.stringify({error:'Ruta no encontrada'})}))
 await enter(page);await expect(page.getByRole('alert')).toContainText('reinicia la API')
})

test('admin configuration persists and kiosk follows service availability',async({page,context})=>{
 await admin(page);await page.getByRole('button',{name:'Servicios y avisos',exact:true}).click()
 await page.getByRole('button',{name:'Editar avisos del campus'}).click();await page.getByLabel('Título',{exact:true}).fill('Semana del campus');await page.getByLabel('Mensaje',{exact:true}).fill('Consulta las actividades disponibles.');await page.getByRole('button',{name:'Guardar configuración'}).click();await expect(page.getByRole('status')).toContainText('Cambios guardados')
 await page.getByRole('button',{name:'Editar disponibilidad de servicios'}).click();await page.getByLabel('Mi credencial',{exact:true}).check();await page.getByRole('button',{name:'Guardar configuración'}).click();await expect(page.getByRole('status')).toContainText('Cambios guardados')
 const kiosk=await context.newPage();await enter(kiosk);await expect(kiosk.getByText('Semana del campus',{exact:true})).toBeVisible();await service(kiosk,'Mi credencial');await expect(kiosk.getByRole('button',{name:'SOLICITAR',exact:true})).toBeDisabled();await expect(kiosk.getByText(/temporalmente fuera de atención/)).toBeVisible();await kiosk.close()
})

test('public directory and responsive kiosk keep navigation usable',async({page})=>{
 await page.setViewportSize({width:768,height:1024});await page.goto('/');await page.getByRole('button',{name:'Directorio y avisos',exact:true}).click();await expect(page.getByRole('heading',{name:'Directorio y avisos'})).toBeVisible();await expect(page.locator('.campus-grid.two .campus-panel')).toHaveCount(4)
 expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBeTruthy()
 await page.screenshot({path:'test-results/campus-tablet.png',fullPage:true})
})

test('turn ticket, operator call and persistent tracking after reopening',async({page,context})=>{
 await enter(page);await service(page,'Turnos de atención')
 await page.locator('.campus-panel').filter({has:page.getByRole('heading',{name:'Caja',exact:true})}).getByRole('button',{name:'TOMAR TURNO'}).click();await confirm(page)
 const folio=(await page.locator('.campus-folio').innerText()).trim()
 await page.getByRole('button',{name:'IMPRIMIR TURNO'}).click();await expect(page.getByRole('status')).toContainText('Turno enviado')
 const operator=await context.newPage();await admin(operator)
 await operator.locator('.campus-record').filter({hasText:folio}).getByRole('button',{name:'Pasa a ventanilla'}).click();await operator.getByRole('button',{name:'Confirmar cambio'}).click();await expect(operator.getByRole('dialog')).toHaveCount(0)
 await page.getByRole('button',{name:'Actualizar servicios'}).click();await expect(page.locator('.turn-called')).toContainText('Es tu turno')
 await page.reload();await enter(page);await service(page,'Mis trámites');await expect(page.locator('.campus-record')).toContainText(folio)
 await operator.close()
})

test('reenrollment checklist gates requests until operator validates and balance is clear',async({page,request})=>{
 await enter(page);await service(page,'Reinscripción');await expect(page.getByRole('button',{name:'SOLICITAR REINSCRIPCIÓN'})).toBeDisabled()
 const student=await token(request)
 const adminToken=(await (await request.post(api+'/admin/login',{data:{password:'test-only-admin-123'}})).json()).access_token
 await request.post(api+'/admin/action',{headers:{Authorization:'Bearer '+adminToken},data:{action:'validate',matricula:'202210',documents:true,academic:true}})
 const pending=await (await request.get(api+'/charges',{headers:{Authorization:'Bearer '+student}})).json()
 await request.post(api+'/payments/simulate',{headers:{Authorization:'Bearer '+student},data:{concept_ids:pending.conceptos.map(c=>c.id),request_id:crypto.randomUUID()}})
 await page.getByRole('button',{name:'Actualizar servicios'}).click();await expect(page.getByRole('button',{name:'SOLICITAR REINSCRIPCIÓN'})).toBeEnabled()
 await page.getByRole('button',{name:'SOLICITAR REINSCRIPCIÓN'}).click();await confirm(page);await expect(page.locator('.campus-record')).toContainText('Reinscripción')
 await page.screenshot({path:'test-results/campus-reenrollment.png',fullPage:true})
})

test('admin logout discards an in-flight response and campus survey shortcut navigates in place',async({page,request})=>{
 await enter(page);await service(page,'Biblioteca');await page.locator('.accessibility-bar').getByRole('button',{name:'Tu opinión',exact:true}).click();await expect(page.getByRole('heading',{name:'Tu opinión',exact:true})).toBeVisible()
 const issued=page.waitForResponse(response=>response.url().endsWith('/api/admin/login')&&response.status()===200)
 await admin(page)
 const token=(await (await issued).json()).access_token
 let release;const gate=new Promise(resolve=>release=resolve);let pending
 await page.route('**/api/admin/state',async route=>{pending=true;await gate;await route.fulfill({json:{demo:true,records:[],config:{},metrics:[],hours:[],surveys:{},incidents:[],deliveries:[],validations:[],loans:[]}}).catch(()=>{})})
 await page.getByRole('button',{name:'Actualizar',exact:true}).click();await expect.poll(()=>pending).toBeTruthy()
 const revoked=page.waitForResponse(response=>response.url().endsWith('/api/auth/logout'))
 await page.getByRole('button',{name:'Cerrar sesión',exact:true}).click();release();await expect(page.getByRole('heading',{name:'Acceso del personal'})).toBeVisible();await expect(page.locator('.admin-content')).toHaveCount(0)
 expect((await revoked).status()).toBe(200)
 expect((await request.get(api+'/admin/state',{headers:{Authorization:'Bearer '+token}})).status()).toBe(403)
})
