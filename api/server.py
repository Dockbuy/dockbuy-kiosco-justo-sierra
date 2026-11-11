#!/usr/bin/env python3
"""API local: consulta SIPAA o demostración aislada. No procesa dinero ni emite CFDI fiscal."""
from http.server import BaseHTTPRequestHandler
import json
import os
import secrets
import sqlite3
import subprocess
import threading
import time
import urllib.parse
from pathlib import Path
from dotenv import load_dotenv
load_dotenv(Path(__file__).parent / '.env')
import parking
import payments
import mail_delivery
import campus
import sipaa
from catalog import CONCEPTS
from http_guard import GuardedHTTPHandler, ThreadingHTTPServer, RequestError

HOST = os.getenv('MOCK_HOST', '127.0.0.1')
PORT = int(os.getenv('MOCK_PORT', '8787'))
TOKENS = {}
LOCK = threading.Lock()
ADMIN_ATTEMPTS = {}
TTL = 3600
DATA_SOURCE = os.getenv('KIOSCO_DATA_SOURCE', 'sipaa').lower()
if DATA_SOURCE not in ('demo', 'sipaa'):
    raise RuntimeError('KIOSCO_DATA_SOURCE debe ser demo o sipaa.')
SIPAA = sipaa.Gateway()
STUDENTS={
 '202210':{'id':'6019','matricula':'202210','nombre':'ALUMNO DEMOSTRACIÓN','nivel':'Preparatoria','grado':'Sexto','grupo':'A','ciclo':'2026/2027','email':'alumno.demo@ejemplo.invalid'},
 '202211':{'id':'6020','matricula':'202211','nombre':'ALUMNA PRUEBA','nivel':'Licenciatura','grado':'Tercero','grupo':'B','ciclo':'2026/2027','email':'alumna.demo@ejemplo.invalid'}
}

class Handler(GuardedHTTPHandler, BaseHTTPRequestHandler):
    def respond(self, code, body):
        payload = json.dumps(body, ensure_ascii=False).encode()
        self.send_response(code)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Cache-Control', 'no-store')
        self.send_header('Connection', 'close')
        self.send_header('X-Content-Type-Options', 'nosniff')
        if body.get('retry_after'):
            self.send_header('Retry-After', str(body['retry_after']))
        self.cors()
        self.send_header('Content-Length', str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def cors(self):
        self.send_header('Vary', 'Origin')
        origins = self.headers.get_all('Origin', [])
        if len(origins) == 1 and origins[0] in self.server.allowed_origins:
            self.send_header('Access-Control-Allow-Origin', origins[0])
            self.send_header('Access-Control-Allow-Headers', 'Authorization,Content-Type')
            self.send_header('Access-Control-Allow-Methods', 'GET,POST,OPTIONS')

    def do_OPTIONS(self):
        method = self.headers.get('Access-Control-Request-Method', 'GET')
        headers = {h.strip().lower() for h in self.headers.get('Access-Control-Request-Headers', '').split(',') if h.strip()}
        if method not in ('GET', 'POST') or not headers <= {'authorization', 'content-type'}:
            return self.respond(403, {'error': 'Preflight no permitido.'})
        self.send_response(204)
        self.cors()
        self.end_headers()

    def body(self):
        try:
            raw = self.rfile.read(self.body_length)
            self.finish_reading()
            if len(raw) != self.body_length:
                raise ValueError()
            data = json.loads(raw or b'{}')
            if not isinstance(data, dict):
                raise ValueError()
            return data
        except (ValueError, UnicodeError):
            raise ValueError('Se requiere un objeto JSON válido de hasta 8 KB.')

    def auth(self):
        value = self.headers.get('Authorization', '')
        token = value[7:] if value.startswith('Bearer ') else ''
        with LOCK:
            record = TOKENS.get(token)
            if record and record['exp'] <= time.time():
                TOKENS.pop(token, None)
                record = None
        return record

    def require_session(self):
        session = self.auth()
        if not session or session.get('role')=='admin':
            self.respond(401, {'error': 'Tu sesión venció. Vuelve a ingresar.'})
            return None
        return session

    def require_admin(self):
        session=self.auth()
        if not session or session.get('role')!='admin':
            self.respond(403, {'error':'Se requiere acceso administrativo.'})
            return None
        return session

    def guarded(self, action):
        try:
            action()
        except sipaa.IntegrationError as exc:
            if exc.code == 'sipaa_expired':
                with LOCK:
                    TOKENS.pop(self.headers.get('Authorization', '')[7:], None)
            self.respond(exc.status, {'error': str(exc), 'code': exc.code})
        except (RequestError, parking.PrintLimitError) as exc:
            self.respond(exc.status, {'error': str(exc), 'retry_after': exc.retry_after})
        except mail_delivery.DeliveryError as exc:
            self.respond(exc.status, {'error':str(exc)})
        except LookupError as exc:
            self.respond(404, {'error': str(exc)})
        except ValueError as exc:
            self.respond(400, {'error': str(exc)})
        except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
            pass
        except TimeoutError:
            self.respond(408, {'error': 'Se agotó el tiempo para recibir la solicitud.'})
        except (subprocess.SubprocessError, OSError, RuntimeError) as exc:
            self.respond(503, {'error': 'No se pudo completar la impresión. Revisa la impresora y reintenta.', 'detail': str(exc)[:200]})
        except sqlite3.Error:
            self.respond(503, {'error': 'No se pudo guardar o consultar la operación. Reintenta con el mismo folio.'})
        except Exception as exc:
            print('[demo] Error interno:', type(exc).__name__)
            self.respond(500, {'error': 'Ocurrió un error interno en la demo.'})

    def do_GET(self):
        self.guarded(self.get_route)

    def do_POST(self):
        self.guarded(self.post_route)

    def get_route(self):
        path = urllib.parse.urlparse(self.path).path
        if path == '/api/health':
            real = DATA_SOURCE == 'sipaa'
            return self.respond(200, {'status': 'ok', 'modo': 'SIPAA' if real else 'DEMO',
                'integracionReal': real, 'consultaConfigurada': SIPAA.ready() if real else True,
                'cobroReal': False, 'version':'2.1', 'campus':not real})
        if DATA_SOURCE == 'sipaa':
            if path not in ('/api/me', '/api/charges'):
                return self.respond(409, {'error': 'Este servicio de demostración no está habilitado en modo SIPAA.'})
            session = self.require_session()
            if not session:
                return
            if path == '/api/me':
                return self.respond(200, {'estudiante': session['estudiante'], 'demo': False})
            return self.respond(200, SIPAA.consult(session['matricula'], session['upstream_token']))
        if path == '/api/campus/public':
            return self.respond(200, campus.public())
        if path == '/api/admin/state':
            if self.require_admin():
                return self.respond(200, campus.admin_state())
            return
        if path == '/api/services':
            return self.respond(200, mail_delivery.capabilities())
        if path == '/api/parking/printer':
            return self.respond(200, {'printer': parking.printer_name(), 'demo': True})
        session = self.require_session()
        if not session:
            return
        if path == '/api/campus/state':
            return self.respond(200, campus.state(session['matricula'], CONCEPTS))
        if path == '/api/me':
            return self.respond(200, {'estudiante': STUDENTS[session['matricula']]})
        if path == '/api/payments/history':
            return self.respond(200, {'payments':payments.history(session['matricula']), 'demo':True})
        if path == '/api/charges':
            return self.respond(200, {'matricula': session['matricula'], 'conceptos': payments.pending(session['matricula'], CONCEPTS), 'moneda': 'MXN', 'demo': True})
        return self.respond(404, {'error': 'Ruta no encontrada'})

    def print_document(self, document, invoice=False):
        try:
            key = ('invoice:' + document['payment_code']) if invoice else ('payment:' + document['code'])
            result = parking.print_payload(payments.receipt(document, invoice), key)
            return {'printed': True, 'print': result}
        except parking.PrintLimitError as exc:
            return {'printed': False, 'print_error': str(exc), 'retry_after': exc.retry_after, 'print_status': exc.status}
        except (OSError, RuntimeError, subprocess.SubprocessError, ValueError) as exc:
            campus.incident('impresora','Falló la impresión de un comprobante. Puede reintentarse desde Mis comprobantes.')
            return {'printed': False, 'print_error': str(exc)[:300]}

    def post_route(self):
        path = urllib.parse.urlparse(self.path).path
        data = self.body()
        if DATA_SOURCE == 'sipaa' and path not in ('/api/auth/login', '/api/auth/logout', '/api/payments/quote'):
            return self.respond(409, {'error': 'Servicio no integrado con SIPAA. No se registró ningún pago ni documento.'})
        if path == '/api/admin/login':
            address=self.client_address[0]
            with LOCK:
                attempts=[t for t in ADMIN_ATTEMPTS.get(address,[]) if time.time()-t<60]
                if len(attempts)>=5:
                    return self.respond(429, {'error':'Demasiados intentos. Espera un minuto.'})
                ADMIN_ATTEMPTS[address]=attempts+[time.time()]
            if not campus.verify_admin(data.get('password')):
                return self.respond(401, {'error':'Acceso no configurado o contraseña incorrecta.'})
            token=secrets.token_urlsafe(32)
            with LOCK:
                TOKENS[token]={'role':'admin','exp':time.time()+1800}
                ADMIN_ATTEMPTS.pop(address,None)
            return self.respond(200, {'access_token':token,'expires_in':1800})
        if path == '/api/admin/action':
            if self.require_admin():
                return self.respond(200, campus.admin_action(data, CONCEPTS))
            return
        if path == '/api/campus/event':
            return self.respond(200, campus.event(data))
        if path == '/api/campus/survey':
            return self.respond(200, campus.event(data, True))
        if path == '/api/auth/login':
            matricula = str(data.get('matricula', '')).strip()
            pin = str(data.get('pin', '')).strip()
            real = DATA_SOURCE == 'sipaa'
            if real:
                matricula = sipaa.tuition(data.get('matricula'))
                access = SIPAA.authenticate(matricula, data.get('password'))
                snapshot = SIPAA.consult(matricula, access.token)
                student = {'matricula': matricula, 'nombre': access.name or 'Consulta de adeudos'}
            elif matricula not in STUDENTS or pin != '1234':
                return self.respond(401, {'error': 'Matrícula o PIN demo incorrectos'})
            else:
                student = STUDENTS[matricula]
            ttl = min(access.expires_in, int(access.expires_at - time.time())) if real else TTL
            if ttl <= 0:
                raise sipaa.IntegrationError('Tu sesión en SIPAA venció. Vuelve a ingresar.', 401, 'sipaa_expired')
            token = secrets.token_urlsafe(32)
            with LOCK:
                for stale in [t for t, s in TOKENS.items() if s['exp'] <= time.time()]:
                    TOKENS.pop(stale, None)
                if len(TOKENS) >= 256:
                    return self.respond(429, {'error': 'Demasiadas sesiones activas. Pide ayuda al encargado.', 'retry_after': 60})
                TOKENS[token] = {'matricula': matricula, 'estudiante': student, 'exp': time.time() + ttl,
                    **({'upstream_token': access.token} if real else {})}
            return self.respond(200, {'access_token': token, 'token_type': 'Bearer', 'expires_in': ttl,
                'estudiante': student, 'demo': not real, **({'consulta': snapshot} if real else {})})
        if path == '/api/auth/logout':
            token = self.headers.get('Authorization', '')[7:]
            with LOCK:
                TOKENS.pop(token, None)
            return self.respond(200, {'ok': True})
        if path == '/api/parking/issue':
            ticket, reused = parking.issue_ticket(data.get('request_id'))
            if reused:
                return self.respond(200, {'ticket': ticket, 'demo': True, 'reused': True, 'print_skipped': True})
            try:
                ticket.update({'print': parking.print_ticket(ticket), 'printed': True})
            except parking.PrintLimitError as exc:
                ticket.update({'printed': False, 'print_error': str(exc), 'retry_after': exc.retry_after})
            except (OSError, RuntimeError, subprocess.SubprocessError, ValueError) as exc:
                campus.incident('impresora','Falló la impresión de un boleto de estacionamiento.')
                ticket.update({'printed': False, 'print_error': str(exc)[:300]})
            parking.save_issue_result(data['request_id'], ticket)
            return self.respond(200, {'ticket': ticket, 'demo': True, 'reused': False})
        if path == '/api/parking/reprint':
            quote = parking.quote_ticket(data.get('code', ''))
            return self.respond(200, {'printed': True, 'print': parking.print_ticket(quote)})
        if path == '/api/parking/quote':
            try:
                return self.respond(200, parking.quote_ticket(data.get('code', '')))
            except ValueError as exc:
                raise LookupError(str(exc))
        # El QR aleatorio es la llave del comprobante ficticio en este kiosco.
        if path == '/api/billing/lookup':
            record=payments.lookup(data.get('code', ''))
            if record['invoice']:
                record['invoice']={k:v for k,v in record['invoice'].items() if k!='xml'}
            return self.respond(200, record)
        if path == '/api/billing/email':
            result=mail_delivery.send(data.get('code',''), data.get('kind','payment'), data.get('email',''), data.get('request_id',''))
            return self.respond(202 if result['status']=='sending' else 200, result)
        if path == '/api/billing/invoice':
            invoice, reused = payments.create_invoice(data.get('code', ''))
            status = {'print_skipped': True} if reused else self.print_document(invoice, True)
            return self.respond(200, {'invoice': {k:v for k,v in invoice.items() if k!='xml'}, 'reused': reused, **status})
        if path == '/api/billing/print':
            record = payments.lookup(data.get('code', ''))
            kind = data.get('kind', 'payment')
            if kind not in ('payment', 'invoice'):
                raise ValueError('Tipo de documento inválido.')
            document = record[kind]
            if not document:
                raise ValueError('Primero genera la factura de prueba.')
            return self.respond(200, self.print_document(document, kind == 'invoice'))
        session = self.require_session()
        if not session:
            return
        matricula = session['matricula']
        if DATA_SOURCE == 'sipaa' and path == '/api/payments/quote':
            return self.respond(200, sipaa.quote(SIPAA, matricula, session['upstream_token'], data.get('concept_ids')))
        if path == '/api/campus/action':
            return self.respond(200, campus.action(matricula, data, CONCEPTS))
        if path == '/api/campus/print-turn':
            payload=campus.turn_ticket(matricula,data.get('folio'))
            try:
                result=parking.print_payload(payload, 'turn:' + str(data['folio']).strip())
                return self.respond(200, {'printed':True,'print':result})
            except parking.PrintLimitError:
                raise
            except (OSError,RuntimeError,subprocess.SubprocessError) as exc:
                campus.incident('impresora','Falló la impresión de un turno. El folio permanece registrado.')
                return self.respond(503, {'error':'El turno está guardado, pero no salió la impresión. Revisa la impresora y reintenta.'})
        if path == '/api/campus/email':
            document=campus.document(matricula,data.get('code'),STUDENTS[matricula])
            return self.respond(200,mail_delivery.send(document['folio'],'campus',data.get('email',''),data.get('request_id',''),document))
        if path == '/api/payments/quote':
            selected = payments.select_in_order(payments.pending(matricula, CONCEPTS), data.get('concept_ids'))
            return self.respond(200, {'conceptos': selected, 'total': payments.total(selected), 'moneda': 'MXN', 'modo': 'DEMO', 'cobroReal': False})
        if path == '/api/payments/simulate':
            payment, reused = payments.simulate(STUDENTS[matricula], CONCEPTS, data.get('concept_ids'), data.get('request_id'))
            status = {'print_skipped': True} if reused else self.print_document(payment)
            return self.respond(200, {'payment': payment, 'reused': reused, 'conceptos': payments.pending(matricula, CONCEPTS), **status})
        return self.respond(404, {'error': 'Ruta no encontrada'})

    def log_message(self, fmt, *args):
        print('[demo]', fmt % args)


if __name__ == '__main__':
    print(f'API {DATA_SOURCE.upper()} http://{HOST}:{PORT}/api/health | sin cobro real')
    if DATA_SOURCE == 'sipaa' and SIPAA.config.ignore_expires_at:
        print('[TEMPORAL] SIPAA_IGNORE_EXPIRES_AT=1: revisión local de fecha omitida; login y KardexStudent siguen siendo obligatorios. Sesión local máxima: 10 minutos.')
    ThreadingHTTPServer((HOST, PORT), Handler).serve_forever()
