"""Estacionamiento DEMO: SQLite local + ESC/POS para CASHINO KP-347 vía CUPS.
Nunca marca pagos como realizados. QR contiene identificador opaco aleatorio.
"""
import os, sqlite3, secrets, datetime, subprocess, shutil, math, re
from pathlib import Path
DB=Path(os.environ.get('PARK_DB',str(Path(__file__).parent/'parking-demo.sqlite3')))
RATE=20
HOURS=8

def connection():
    con=sqlite3.connect(DB,timeout=10)
    con.row_factory=sqlite3.Row
    con.execute('CREATE TABLE IF NOT EXISTS tickets (code TEXT PRIMARY KEY, issued_at TEXT NOT NULL, status TEXT NOT NULL DEFAULT \'OPEN\')')
    con.commit()
    return con

def create_ticket():
    code=secrets.token_hex(10).upper()  # 20 caracteres hexadecimales; sin prefijos ni guiones
    dt=datetime.datetime.now(datetime.timezone.utc).isoformat()
    with connection() as con: con.execute('INSERT INTO tickets(code,issued_at) VALUES (?,?)',(code,dt))
    return {'code':code,'issued_at':dt,'status':'OPEN'}

def quote_ticket(code):
    code=str(code).strip().upper()
    with connection() as con: row=con.execute('SELECT * FROM tickets WHERE code=?',(code,)).fetchone()
    if not row:raise ValueError('Ticket no encontrado. Verifica el código QR.')
    now=datetime.datetime.now(datetime.timezone.utc)
    start=datetime.datetime.fromisoformat(row['issued_at'])
    seconds=max(0,(now-start).total_seconds())
    intervals=max(1,math.ceil(seconds/(HOURS*3600)))
    return {'code':code,'issued_at':row['issued_at'],'quoted_at':now.isoformat(),'hours':round(seconds/3600,2),
            'periods':intervals,'price_per_period':RATE,'period_hours':HOURS,'total':intervals*RATE,
            'currency':'MXN','status':row['status'],'payment_enabled':False,'demo':True}

def qr_command(payload):
    """Comandos ESC/POS QR Modelo 2; compatible con impresoras que implementan GS ( k."""
    data=payload.encode('ascii')
    n=len(data)+3
    return (b'\x1d\x28\x6b\x04\x00\x31\x41\x32\x00' +
            b'\x1d\x28\x6b\x03\x00\x31\x43\x06' +
            b'\x1d\x28\x6b\x03\x00\x31\x45\x31' +
            b'\x1d\x28\x6b'+bytes([n&255,n>>8])+b'\x31\x50\x30'+data+
            b'\x1d\x28\x6b\x03\x00\x31\x51\x30')

def receipt(ticket):
    """Ticket térmico de 80 mm: logo raster, espacios de corte y QR original."""
    code=ticket['code']
    local=datetime.datetime.fromisoformat(ticket['issued_at']).astimezone().strftime('%d/%m/%Y %H:%M:%S')
    esc=b'\x1b'; center=esc+b'a\x01'; left=esc+b'a\x00'
    normal=esc+b'!\x00'; bold=esc+b'E\x01'; unbold=esc+b'E\x00'
    # Imagen raster preparada previamente; sin dependencia de Pillow en el kiosco.
    logo_path=Path(__file__).parent/'assets'/'justo_sierra_logo_escpos.bin'
    logo=logo_path.read_bytes()
    return (esc+b'@'+ center + b'\n\n\n\n' +
            logo + b'\n\n' +
            bold + b'UNIVERSIDAD JUSTO SIERRA\n' + unbold +
            b'EDUCAR PARA LA VIDA\n\n' +
            b'================================\n' +
            bold + b'TICKET DE ESTACIONAMIENTO\n' + unbold +
            b'           DEMOSTRACION\n' +
            b'================================\n\n' + left +
            b'FECHA Y HORA DE ENTRADA\n' +
            local.encode('ascii') + b'\n\n' +
            b'FOLIO\n' + code.encode('ascii') + b'\n\n' +
            center + b'ESCANEA PARA CONSULTAR\n' +
            b'TU TIEMPO Y MONTO A PAGAR\n\n' +
            qr_command(code) + b'\n\n' +
            code.encode('ascii') + b'\n\n' +
            b'--------------------------------\n' +
            bold + b'TARIFA DEMO\n' + unbold +
            b'$20.00 MXN / 8 HORAS\n' +
            b'Cada bloque iniciado se cobra.\n' +
            b'--------------------------------\n\n' +
            b'CONSERVA ESTE TICKET\n' +
            b'Lo necesitaras para consultar\n' +
            b'el importe de estacionamiento.\n\n' +
            b'NO ES COMPROBANTE DE PAGO\n' +
            b'UNIVERSIDAD JUSTO SIERRA\n' +
            b'================================\n' +
            b'\n\n\n\n\n\n' + b'\x1d\x56\x01')

def printer_name():
    env=os.environ.get('PARK_PRINTER','').strip()
    if env:return env
    if not shutil.which('lpstat'):return None
    p=subprocess.run(['lpstat','-d'],capture_output=True,text=True,timeout=4)
    if p.returncode==0:
        match=re.search(r':\s*(\S+)',p.stdout)
        if match:return match.group(1)
    p=subprocess.run(['lpstat','-p'],capture_output=True,text=True,timeout=4)
    names=re.findall(r'^printer\s+(\S+)',p.stdout,re.M)
    match=next((n for n in names if any(t in n.lower() for t in ('cashino','kp347','kp-347'))),None)
    return match or (names[0] if len(names)==1 else None)

def print_ticket(ticket):
    # Si CUPS alimenta papel sin imprimir, usar el dispositivo USB directo
    # que haya sido probado físicamente en el equipo. Nunca usar sudo.
    device=os.environ.get('PARK_DEVICE','').strip()
    if device:
        if not re.fullmatch(r'/dev/usb/lp[0-9]+',device):
            raise RuntimeError('PARK_DEVICE debe ser /dev/usb/lpN (ej. /dev/usb/lp0).')
        try:
            with open(device,'wb',buffering=0) as output:
                output.write(receipt(ticket))
        except PermissionError:
            raise RuntimeError('Permiso denegado para '+device+'. Agrega el usuario dockbuy al grupo lp y vuelve a iniciar sesión.')
        except OSError as error:
            raise RuntimeError('No se pudo escribir en '+device+': '+str(error))
        return {'printer':device,'job':'enviado por USB directo'}
    printer=printer_name()
    if not printer:raise RuntimeError('Sin cola CUPS predeterminada. Configura PARK_PRINTER=nombre_cola y revisa lpstat -p -d.')
    if not shutil.which('lp'):raise RuntimeError('Falta el comando lp (sudo apt install cups-client).')
    cmd=['lp','-d',printer,'-o','raw','-']
    result=subprocess.run(cmd,input=receipt(ticket),capture_output=True,timeout=12)
    if result.returncode:raise RuntimeError((result.stderr or b'Error CUPS').decode('utf-8','replace')[:300])
    return {'printer':printer,'job':result.stdout.decode('utf-8','replace').strip()}
