"""Estacionamiento DEMO: SQLite local + ESC/POS para CASHINO KP-347 vía CUPS.
Nunca marca pagos como realizados. QR contiene identificador opaco aleatorio.
"""
import os, sqlite3, secrets, datetime, subprocess, shutil, math, re, sys, threading, time, json
from contextlib import contextmanager
from pathlib import Path
DB=Path(os.environ.get('PARK_DB',str(Path(__file__).parent/'parking-demo.sqlite3')))
RATE=20
HOURS=8

@contextmanager
def connection():
    con=sqlite3.connect(DB,timeout=10)
    con.row_factory=sqlite3.Row
    con.execute('CREATE TABLE IF NOT EXISTS tickets (code TEXT PRIMARY KEY, issued_at TEXT NOT NULL, status TEXT NOT NULL DEFAULT \'OPEN\')')
    con.execute('CREATE TABLE IF NOT EXISTS ticket_requests (request_id TEXT PRIMARY KEY, code TEXT NOT NULL, created_at REAL NOT NULL, result TEXT)')
    con.execute('CREATE INDEX IF NOT EXISTS ticket_requests_time ON ticket_requests(created_at)')
    con.execute('CREATE TABLE IF NOT EXISTS print_attempts (document_key TEXT NOT NULL, attempted_at REAL NOT NULL)')
    con.execute('CREATE INDEX IF NOT EXISTS print_attempts_time ON print_attempts(attempted_at)')
    con.commit()
    try:
        yield con
        con.commit()
    except Exception:
        con.rollback()
        raise
    finally:
        con.close()

def create_ticket():
    code=secrets.token_hex(10).upper()  # 20 caracteres hexadecimales; sin prefijos ni guiones
    dt=datetime.datetime.now(datetime.timezone.utc).isoformat()
    with connection() as con: con.execute('INSERT INTO tickets(code,issued_at) VALUES (?,?)',(code,dt))
    return {'code':code,'issued_at':dt,'status':'OPEN'}


class PrintLimitError(RuntimeError):
    def __init__(self, message, retry_after, status=429):
        super().__init__(message)
        self.status = status
        self.retry_after = max(1, math.ceil(retry_after))


def issue_ticket(request_id):
    if not isinstance(request_id, str) or not re.fullmatch(r'[A-Za-z0-9_-]{16,80}', request_id):
        raise ValueError('Se requiere un identificador de operación de 16 a 80 caracteres.')
    with connection() as con:
        con.execute('BEGIN IMMEDIATE')
        previous = con.execute('SELECT * FROM ticket_requests WHERE request_id=?', (request_id,)).fetchone()
        if previous:
            ticket = dict(con.execute('SELECT * FROM tickets WHERE code=?', (previous['code'],)).fetchone())
            ticket.update(json.loads(previous['result']) if previous['result'] else {
                'printed': False, 'print_error': 'Folio recuperado. Verifica el papel antes de solicitar una reimpresión.'})
            return ticket, True
        now = time.time()
        recent = con.execute('SELECT created_at FROM ticket_requests WHERE created_at>? ORDER BY created_at', (now - 60,)).fetchall()
        if len(recent) >= 10:
            raise PrintLimitError('Límite de boletos alcanzado. Espera un minuto o pide ayuda.', recent[0][0] + 60 - now)
        ticket = {'code': secrets.token_hex(10).upper(), 'issued_at': datetime.datetime.now(datetime.timezone.utc).isoformat(), 'status': 'OPEN'}
        con.execute('INSERT INTO tickets(code,issued_at) VALUES (?,?)', (ticket['code'], ticket['issued_at']))
        con.execute('INSERT INTO ticket_requests(request_id,code,created_at) VALUES (?,?,?)', (request_id,ticket['code'],now))
        return ticket, False


def save_issue_result(request_id, ticket):
    result = {key: ticket[key] for key in ('printed', 'print', 'print_error', 'retry_after') if key in ticket}
    with connection() as con:
        con.execute('UPDATE ticket_requests SET result=? WHERE request_id=?', (json.dumps(result), request_id))

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
    if os.environ.get('PARK_DEVICE', '').strip():
        return os.environ['PARK_DEVICE'].strip()
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

PRINT_LOCK = threading.Lock()
# Un trabajo activo y uno en espera como máximo; ninguna cola ilimitada de hilos.
PRINT_SLOTS = threading.BoundedSemaphore(2)
PRINT_BUDGETS = ((60, 20), (3600, 200), (86400, 500))


def reserve_print(document_key):
    now = time.time()
    with connection() as con:
        con.execute('BEGIN IMMEDIATE')
        con.execute('DELETE FROM print_attempts WHERE attempted_at<=?', (now - 86400,))
        rows = con.execute('SELECT document_key,attempted_at FROM print_attempts ORDER BY attempted_at').fetchall()
        waits = []
        for window, limit in PRINT_BUDGETS:
            recent = [row['attempted_at'] for row in rows if row['attempted_at'] > now - window]
            if len(recent) >= limit:
                waits.append(recent[-limit] + window - now)
        same = [row['attempted_at'] for row in rows if row['document_key'] == document_key and row['attempted_at'] > now - 600]
        if same:
            waits.append(same[-1] + 5 - now)
        if len(same) >= 3:
            waits.append(same[-3] + 600 - now)
        wait = max(waits, default=0)
        if wait > 0:
            raise PrintLimitError(f'Límite de impresión. Espera {math.ceil(wait)} segundos o pide ayuda.', wait)
        # Registrar ANTES de enviar: un timeout no demuestra que no salió papel.
        con.execute('INSERT INTO print_attempts VALUES (?,?)', (document_key, now))

def print_ticket(ticket):
    return print_payload(receipt(ticket), 'parking:' + ticket['code'])

def print_payload(payload, document_key):
    if not PRINT_SLOTS.acquire(blocking=False):
        raise PrintLimitError('Impresora ocupada. Espera unos segundos y reintenta.', 5, 503)
    try:
        if not PRINT_LOCK.acquire(timeout=2):
            raise PrintLimitError('Impresora ocupada. Espera unos segundos y reintenta.', 5, 503)
        try:
            reserve_print(document_key)
            return _send_payload(payload)
        finally:
            PRINT_LOCK.release()
    finally:
        PRINT_SLOTS.release()

def _send_payload(payload):
    # Si CUPS alimenta papel sin imprimir, usar el dispositivo USB directo
    # que haya sido probado físicamente en el equipo. Nunca usar sudo.
    device=os.environ.get('PARK_DEVICE','').strip()
    if device:
        if not re.fullmatch(r'/dev/usb/lp[0-9]+',device):
            raise RuntimeError('PARK_DEVICE debe ser /dev/usb/lpN (ej. /dev/usb/lp0).')
        result = subprocess.run([sys.executable, str(Path(__file__).resolve()), '--print-usb', device], input=payload, capture_output=True, timeout=12)
        if result.returncode:
            raise RuntimeError('No se pudo imprimir por USB. Revisa conexión y permisos del grupo lp. ' + result.stderr.decode('utf-8', 'replace')[-180:])
        return {'printer':device,'job':'enviado por USB directo'}
    printer=printer_name()
    if not printer:raise RuntimeError('Sin cola CUPS predeterminada. Configura PARK_PRINTER=nombre_cola y revisa lpstat -p -d.')
    if not shutil.which('lp'):raise RuntimeError('Falta el comando lp (sudo apt install cups-client).')
    cmd=['lp','-d',printer,'-o','raw','-']
    result=subprocess.run(cmd,input=payload,capture_output=True,timeout=12)
    if result.returncode:raise RuntimeError((result.stderr or b'Error CUPS').decode('utf-8','replace')[:300])
    return {'printer':printer,'job':result.stdout.decode('utf-8','replace').strip()}

if __name__ == '__main__':
    if len(sys.argv) != 3 or sys.argv[1] != '--print-usb' or not re.fullmatch(r'/dev/usb/lp[0-9]+', sys.argv[2]):
        raise SystemExit('Uso interno: --print-usb /dev/usb/lpN')
    remaining = memoryview(sys.stdin.buffer.read())
    with open(sys.argv[2], 'wb', buffering=0) as output:
        while remaining:
            written = output.write(remaining)
            if not written:
                raise OSError('La impresora dejó de aceptar datos.')
            remaining = remaining[written:]
