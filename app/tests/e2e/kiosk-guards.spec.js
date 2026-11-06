import {test,expect} from '@playwright/test'

async function desktop(page){
  // Simula únicamente la detección de Tauri. No prueba WebKitGTK ni el inspector nativo.
  await page.addInitScript(()=>{window.isTauri=true})
  await page.goto('/')
  await expect(page.locator('html')).toHaveAttribute('data-kiosk-lock','true')
}

test('kiosk cancels zoom, inspector, context menu and file drop; permits normal scrolling',async({page})=>{
  await desktop(page)
  const events=await page.evaluate(()=>{
    const emit=event=>{document.body.dispatchEvent(event);return event.defaultPrevented}
    return {
      zoom:emit(new KeyboardEvent('keydown',{key:'+',ctrlKey:true,bubbles:true,cancelable:true})),
      inspector:emit(new KeyboardEvent('keydown',{key:'F12',bubbles:true,cancelable:true})),
      console:emit(new KeyboardEvent('keydown',{key:'I',ctrlKey:true,shiftKey:true,bubbles:true,cancelable:true})),
      wheelZoom:emit(new WheelEvent('wheel',{ctrlKey:true,deltaY:-100,bubbles:true,cancelable:true})),
      wheelScroll:emit(new WheelEvent('wheel',{deltaY:100,bubbles:true,cancelable:true})),
      context:emit(new MouseEvent('contextmenu',{bubbles:true,cancelable:true})),
      drop:emit(new Event('drop',{bubbles:true,cancelable:true})),
      gesture:emit(new Event('gesturechange',{bubbles:true,cancelable:true})),
    }
  })
  expect(events).toEqual({zoom:true,inspector:true,console:true,wheelZoom:true,wheelScroll:false,context:true,drop:true,gesture:true})
  const before=await page.evaluate(()=>devicePixelRatio)
  await page.keyboard.press('Control++');await page.keyboard.press('Control+-')
  expect(await page.evaluate(()=>devicePixelRatio)).toBe(before)
  await page.getByRole('button',{name:'Directorio y avisos',exact:true}).click()
  await page.mouse.move(650,650);await page.mouse.wheel(0,700)
  await expect.poll(()=>page.evaluate(()=>scrollY)).toBeGreaterThan(0)
})

test('multitouch is cancelled, single touch and large-text accessibility continue working',async({page})=>{
  await desktop(page)
  const result=await page.evaluate(()=>{
    const dispatch=count=>{
      const event=new Event('touchmove',{bubbles:true,cancelable:true})
      Object.defineProperty(event,'touches',{value:Array.from({length:count},()=>({}))})
      document.body.dispatchEvent(event)
      return event.defaultPrevented
    }
    return {single:dispatch(1),pinch:dispatch(2),action:getComputedStyle(document.documentElement).touchAction}
  })
  expect(result).toEqual({single:false,pinch:true,action:'pan-x pan-y'})
  await page.getByRole('button',{name:'Aa · Accesibilidad',exact:true}).click()
  await page.getByRole('button',{name:'Texto grande',exact:true}).click()
  await expect(page.locator('.screen')).toHaveClass(/large-text/)
  await page.getByRole('button',{name:'Aa · Accesibilidad',exact:true}).click()
  await page.getByRole('button',{name:'INGRESAR AL PORTAL',exact:true}).click()
  await page.locator('input[placeholder="Ingresa tu matrícula"]').click()
  await page.getByRole('button',{name:'LISTO ✓',exact:true}).click()
  await page.getByRole('button',{name:'ENTRAR',exact:true}).click()
  await expect(page.getByRole('button',{name:/EXPLORAR TODOS LOS SERVICIOS/})).toBeVisible()
})

test('locked kiosk preserves physical text entry, editing and QR scanning',async({page,request})=>{
  await request.post('http://127.0.0.1:8878/__test/reset')
  const auth=await (await request.post('http://127.0.0.1:8878/api/auth/login',{data:{matricula:'202210',pin:'1234'}})).json()
  const payment=await (await request.post('http://127.0.0.1:8878/api/payments/simulate',{headers:{Authorization:'Bearer '+auth.access_token},data:{concept_ids:[101],request_id:crypto.randomUUID()}})).json()
  await desktop(page)
  await page.keyboard.type(payment.payment.code,{delay:8});await page.keyboard.press('Enter')
  await expect(page.getByRole('heading',{name:'COMPROBANTE ENCONTRADO'})).toBeVisible()
  await page.getByRole('button',{name:'Campus',exact:true}).click()
  const search=page.getByLabel('Buscar un servicio')
  await search.fill('bibliotecas');await search.press('Backspace')
  await expect(search).toHaveValue('biblioteca')
  await search.press('Control+a');await search.press('Backspace');await search.press('Control+z')
  await expect(search).toHaveValue('biblioteca')
})

test('development browser and operator page do not inherit kiosk gesture restrictions',async({page})=>{
  await page.goto('/')
  await expect(page.locator('html')).not.toHaveAttribute('data-kiosk-lock','true')
  await page.goto('/admin')
  await expect(page.locator('html')).not.toHaveAttribute('data-kiosk-lock','true')
  await expect(page.locator('meta[name="viewport"]')).not.toHaveAttribute('content',/user-scalable=no/)
})

test('locked kiosk completes payment and email without browser print or download',async({page,request})=>{
  await request.post('http://127.0.0.1:8878/__test/reset')
  await desktop(page)
  await page.getByRole('button',{name:'INGRESAR AL PORTAL',exact:true}).click()
  await page.getByRole('button',{name:'ENTRAR',exact:true}).click()
  await page.getByRole('button',{name:/Servicios y pagos/}).click()
  await page.getByRole('button',{name:'Agregar concepto 101',exact:true}).click()
  await page.getByRole('button',{name:'CONTINUAR',exact:true}).click()
  await page.getByRole('button',{name:'CONFIRMAR PAGO DEMO'}).click()
  await expect(page.getByRole('heading',{name:'PAGO DEMO COMPLETADO'})).toBeVisible()
  await page.getByRole('button',{name:'ENVIAR POR CORREO',exact:true}).click()
  await page.getByLabel('Tu correo',{exact:true}).fill('test@example.invalid')
  await page.getByLabel('Confirma tu correo',{exact:true}).fill('test@example.invalid')
  await page.getByRole('button',{name:'REVISAR DESTINATARIO'}).click()
  await page.getByRole('button',{name:'CONFIRMAR Y ENVIAR'}).click()
  await expect(page.getByRole('heading',{name:'ENVÍO ACEPTADO'})).toBeVisible()
  await page.getByRole('button',{name:'LISTO',exact:true}).click()
  await page.getByRole('button',{name:'SALIR',exact:true}).click()
  await expect(page.getByRole('button',{name:'COMENZAR',exact:true})).toBeVisible()
  await expect(page.locator('html')).toHaveAttribute('data-kiosk-lock','true')
})
