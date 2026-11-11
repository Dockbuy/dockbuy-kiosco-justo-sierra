import {test,expect} from '@playwright/test'

test.use({hasTouch:true,viewport:{width:1366,height:768}})
test.beforeEach(async({page,request})=>{
  await request.post('http://127.0.0.1:8878/__test/reset',{data:{mode:'sipaa'}})
  await page.addInitScript(()=>{window.isTauri=true})
  await page.goto('/')
  await page.getByRole('button',{name:'INGRESAR AL PORTAL',exact:true}).tap()
  await expect(page.getByRole('button',{name:'CONSULTAR ADEUDOS',exact:true})).toBeVisible()
})

test('touch opens, types and closes the keyboard repeatedly without leaving a backdrop',async({page})=>{
  const field=page.getByPlaceholder('Ingresa tu matrícula')
  for(let index=0;index<4;index++){
    await field.tap()
    await expect(page.locator('.touch-keyboard')).toBeVisible()
    await page.locator('.touch-keyboard').getByRole('button',{name:'1',exact:true}).tap()
    await expect(field).toHaveValue('1'.repeat(index+1))
    await page.getByRole('button',{name:index%2?'CERRAR ✕':'LISTO ✓',exact:true}).tap()
    await expect(page.locator('.keyboard-backdrop')).toHaveCount(0)
  }
  await page.getByRole('button',{name:'REGRESAR AL INICIO',exact:true}).tap()
  await expect(page.getByRole('button',{name:'INGRESAR AL PORTAL',exact:true})).toBeVisible()
})

test('touch password keyboard survives symbol layout changes and submits a session',async({page})=>{
  await page.getByPlaceholder('Ingresa tu matrícula').tap()
  for(const digit of '000042')await page.locator('.touch-keyboard').getByRole('button',{name:digit,exact:true}).tap()
  await page.getByRole('button',{name:'LISTO ✓',exact:true}).tap()
  const password=page.getByPlaceholder('Ingresa tu contraseña')
  await password.tap()
  for(const key of ['MAYÚS','T','MAYÚS','e','s','t','SÍMBOLOS','!','ABC','4','2']){
    await page.locator('.touch-keyboard').getByRole('button',{name:key,exact:true}).tap()
  }
  await expect(password).toHaveValue('Test!42')
  await page.getByRole('button',{name:'LISTO ✓',exact:true}).tap()
  await page.getByRole('button',{name:'CONSULTAR ADEUDOS',exact:true}).tap()
  await expect(page.getByRole('heading',{name:'CONSULTA DE ADEUDOS',exact:true})).toBeVisible()
  await expect(page.locator('.keyboard-backdrop,.touch-keyboard')).toHaveCount(0)
  await page.getByRole('button',{name:'SALIR',exact:true}).tap()
  await expect(page.getByRole('button',{name:'INGRESAR AL PORTAL',exact:true})).toBeVisible()
})

test('touch closes the keyboard from its backdrop and after scanner input',async({page})=>{
  await page.getByPlaceholder('Ingresa tu matrícula').tap()
  await page.locator('.keyboard-backdrop').tap({position:{x:10,y:10}})
  await expect(page.locator('.touch-keyboard,.keyboard-backdrop')).toHaveCount(0)
  await page.getByPlaceholder('Ingresa tu matrícula').tap()
  await page.locator('.touch-keyboard').getByRole('button',{name:'1',exact:true}).tap()
  await page.keyboard.type('JS-PAY-'+'A'.repeat(32),{delay:8})
  await page.keyboard.press('Enter')
  await page.getByRole('button',{name:'CERRAR ✕',exact:true}).tap()
  await expect(page.locator('.touch-keyboard,.keyboard-backdrop')).toHaveCount(0)
  await page.getByRole('button',{name:'REGRESAR AL INICIO',exact:true}).tap()
  await expect(page.getByRole('button',{name:'INGRESAR AL PORTAL',exact:true})).toBeVisible()
})

test('touch resumes from the idle dialog over the keyboard and expiry clears both overlays',async({page})=>{
  await page.clock.install()
  await page.reload()
  await page.getByRole('button',{name:'INGRESAR AL PORTAL',exact:true}).tap()
  await page.getByPlaceholder('Ingresa tu matrícula').tap()
  await page.clock.fastForward(91000)
  await expect(page.getByRole('alertdialog')).toBeVisible()
  await page.getByRole('button',{name:'SEGUIR USANDO EL KIOSCO',exact:true}).tap()
  await expect(page.getByRole('alertdialog')).toHaveCount(0)
  await page.locator('.touch-keyboard').getByRole('button',{name:'1',exact:true}).tap()
  await expect(page.getByPlaceholder('Ingresa tu matrícula')).toHaveValue('1')
  await page.clock.fastForward(121000)
  await expect(page.locator('.touch-keyboard,.keyboard-backdrop,.idle-backdrop')).toHaveCount(0)
  await page.getByRole('button',{name:'INGRESAR AL PORTAL',exact:true}).tap()
  await expect(page.getByRole('button',{name:'CONSULTAR ADEUDOS',exact:true})).toBeVisible()
})

test('overlapping fingers reach the keyboard and do not block later taps',async({page,context})=>{
  await page.getByPlaceholder('Ingresa tu matrícula').tap()
  await page.evaluate(()=>{
    window.touchObservations=[]
    document.querySelector('.touch-keyboard').addEventListener('touchstart',event=>{
      window.touchObservations.push({count:event.touches.length,cancelled:event.defaultPrevented})
    })
  })
  const points=[]
  for(const [index,key] of ['1','2','3'].entries()){
    const box=await page.locator('.touch-keyboard').getByRole('button',{name:key,exact:true}).boundingBox()
    points.push({id:index+1,x:box.x+box.width/2,y:box.y+box.height/2})
  }
  const cdp=await context.newCDPSession(page)
  for(let count=1;count<=3;count++)await cdp.send('Input.dispatchTouchEvent',{type:'touchStart',touchPoints:points.slice(0,count)})
  await cdp.send('Input.dispatchTouchEvent',{type:'touchEnd',touchPoints:[]})
  await expect.poll(()=>page.evaluate(()=>window.touchObservations)).toEqual([
    {count:1,cancelled:false},{count:2,cancelled:false},{count:3,cancelled:false},
  ])
  const field=page.getByPlaceholder('Ingresa tu matrícula')
  const before=await field.inputValue()
  await page.locator('.touch-keyboard').getByRole('button',{name:'4',exact:true}).tap()
  await expect(field).toHaveValue(before+'4')
  await page.getByRole('button',{name:'LISTO ✓',exact:true}).tap()
  await expect(page.locator('.keyboard-backdrop')).toHaveCount(0)
})

test('pinch stays at normal scale inside the scrollable keyboard and one-finger scrolling works',async({page,context})=>{
  await page.setViewportSize({width:1000,height:320})
  await page.getByPlaceholder('Ingresa tu contraseña').tap()
  const keyboard=page.locator('.touch-keyboard')
  expect(await keyboard.evaluate(element=>({
    action:getComputedStyle(element).touchAction,
    keyAction:getComputedStyle(element.querySelector('button')).touchAction,
    scrollable:element.scrollHeight>element.clientHeight,
  }))).toEqual({action:'pan-x pan-y',keyAction:'pan-x pan-y',scrollable:true})
  const box=await keyboard.boundingBox()
  const cdp=await context.newCDPSession(page)
  const x=box.x+box.width/2,y=box.y+box.height/2
  const scale=await page.evaluate(()=>visualViewport.scale)
  await cdp.send('Input.synthesizePinchGesture',{x,y,scaleFactor:1.7,gestureSourceType:'touch'})
  expect(await page.evaluate(()=>visualViewport.scale)).toBe(scale)
  const startY=box.y+box.height-40
  await cdp.send('Input.dispatchTouchEvent',{type:'touchStart',touchPoints:[{id:1,x,y:startY}]})
  for(let offset=15;offset<=150;offset+=15){
    await cdp.send('Input.dispatchTouchEvent',{type:'touchMove',touchPoints:[{id:1,x,y:startY-offset}]})
  }
  await cdp.send('Input.dispatchTouchEvent',{type:'touchEnd',touchPoints:[]})
  await expect.poll(()=>keyboard.evaluate(element=>element.scrollTop)).toBeGreaterThan(0)
  // En esta altura reducida, el botón de diagnóstico (modo trace) puede
  // cubrir LISTO. Cerrar por la parte descubierta del fondo del teclado.
  await page.locator('.keyboard-backdrop').tap({position:{x:10,y:10}})
  await expect(page.locator('.keyboard-backdrop')).toHaveCount(0)
})
