import {test,expect} from '@playwright/test'

test.beforeEach(async({request})=>{
  await request.post('http://127.0.0.1:8878/__test/reset',{data:{mode:'sipaa'}})
})
test.afterEach(async({request})=>{
  await request.post('http://127.0.0.1:8878/__test/reset',{data:{}})
})

async function login(page){
  await page.goto('/')
  await page.getByRole('button',{name:'INGRESAR AL PORTAL'}).click()
  await expect(page.getByRole('button',{name:'CONSULTAR ADEUDOS'})).toBeVisible()
  await expect(page.getByText('Contraseña / PIN demo')).toHaveCount(0)
  const field=page.getByPlaceholder('Ingresa tu matrícula')
  await expect(field).toHaveValue('')
  await field.click()
  for(const digit of '000042')await page.locator('.touch-keyboard').getByRole('button',{name:digit,exact:true}).click()
  await page.getByRole('button',{name:'LISTO ✓',exact:true}).click()
  await page.getByPlaceholder('Ingresa tu contraseña').click()
  for(const key of ['MAYÚS','T','MAYÚS','e','s','t','SÍMBOLOS','!','ABC','4','2']){
    await page.locator('.touch-keyboard').getByRole('button',{name:key,exact:true}).click()
  }
  await expect(page.getByPlaceholder('Ingresa tu contraseña')).toHaveValue('Test!42')
  await page.getByRole('button',{name:'LISTO ✓',exact:true}).click()
  await page.getByRole('button',{name:'CONSULTAR ADEUDOS',exact:true}).click()
  await expect(page.getByRole('heading',{name:'CONSULTA DE ADEUDOS',exact:true})).toBeVisible()
  await page.getByRole('button',{name:/Servicios y pagos/}).click()
}

test('institutional consultation keeps ordered cart and cannot simulate a payment',async({page})=>{
  const errors=[],posts=[]
  page.on('pageerror',e=>errors.push(e.message))
  page.on('request',r=>{if(r.method()==='POST')posts.push(r.url())})
  await login(page)
  await expect(page.getByRole('button',{name:'Comprobantes',exact:true})).toHaveCount(0)
  await expect(page.getByRole('button',{name:'Facturar',exact:true})).toHaveCount(0)
  const first='sipaa:128:single:10',second='sipaa:129:contract:9:255'
  await expect(page.getByRole('button',{name:'Agregar concepto '+first,exact:true})).toBeEnabled()
  await expect(page.getByRole('button',{name:'Agregar concepto '+second,exact:true})).toBeDisabled()
  await page.getByRole('button',{name:'Agregar concepto '+first,exact:true}).click()
  await page.getByRole('button',{name:'Agregar concepto '+second,exact:true}).click()
  await expect(page.getByRole('button',{name:'Devolver concepto '+first,exact:true})).toBeDisabled()
  await page.screenshot({path:'test-results/sipaa-cart.png',fullPage:true})
  await page.getByRole('button',{name:'CONTINUAR',exact:true}).click()
  await expect(page.getByRole('heading',{name:'REVISA TUS ADEUDOS'})).toBeVisible()
  await expect(page.locator('.review-total')).toContainText('$0.30')
  await expect(page.getByText(/COBRO NO DISPONIBLE/)).toBeVisible()
  await expect(page.getByRole('button',{name:'CONFIRMAR PAGO DEMO'})).toHaveCount(0)
  await page.screenshot({path:'test-results/sipaa-review.png',fullPage:true})
  await page.getByRole('button',{name:'FINALIZAR Y SALIR',exact:true}).click()
  await expect(page.getByRole('button',{name:'INGRESAR AL PORTAL'})).toBeVisible()
  expect(posts.some(url=>/simulate|billing|campus/.test(url))).toBe(false)
  expect(errors).toEqual([])
})

test('empty institutional response is a successful consultation',async({page,request})=>{
  await request.post('http://127.0.0.1:8878/__test/reset',{data:{mode:'sipaa',empty:true}})
  await login(page)
  await expect(page.getByRole('heading',{name:'SIN CARGOS PENDIENTES'})).toBeVisible()
  await expect(page.getByText('SIPAA no devolvió saldos pendientes para esta matrícula.')).toBeVisible()
  await expect(page.getByRole('button',{name:'CONTINUAR',exact:true})).toBeDisabled()
})

test('an upstream outage locks stale selections and can be retried',async({page})=>{
  await login(page)
  const add=page.getByRole('button',{name:'Agregar concepto sipaa:128:single:10',exact:true})
  await expect(add).toBeEnabled();await add.click()
  await page.route('**/api/charges',route=>route.fulfill({status:503,json:{error:'No se pudo consultar SIPAA.'}}))
  await page.getByRole('button',{name:'ACTUALIZAR SALDOS'}).click()
  await expect(page.getByRole('alert')).toContainText('No se pudo consultar SIPAA.')
  await expect(page.getByRole('button',{name:'CONTINUAR',exact:true})).toBeDisabled()
  await page.unroute('**/api/charges')
  await page.getByRole('button',{name:'ACTUALIZAR SALDOS'}).click()
  await expect(page.getByRole('button',{name:'CONTINUAR',exact:true})).toBeEnabled()
})

test('invalid integration configuration disables login',async({page})=>{
  await page.route('**/api/health',route=>route.fulfill({json:{status:'ok',modo:'SIPAA',consultaConfigurada:false}}))
  await page.goto('/')
  await page.getByRole('button',{name:'INGRESAR AL PORTAL'}).click()
  await expect(page.getByText(/La configuración de SIPAA no es válida/)).toBeVisible()
  await expect(page.getByRole('button',{name:'CONSULTAR ADEUDOS',exact:true})).toBeDisabled()
  await expect(page.getByText('Contraseña / PIN demo')).toHaveCount(0)
})
