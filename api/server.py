#!/usr/bin/env python3
"""API local de demostración. No procesa dinero ni emite CFDI fiscal."""
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
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
from catalog import CONCEPTS

HOST = os.getenv('MOCK_HOST', '127.0.0.1')
PORT = int(os.getenv('MOCK_PORT', '8787'))
TOKENS = {}
LOCK = threading.Lock()
TTL = 3600
STUDENTS={
 '202210':{'id':'6019','matricula':'202210','nombre':'ALUMNO DEMOSTRACIÓN','nivel':'Preparatoria','grado':'Sexto','grupo':'A','ciclo':'2026/2027','email':'alumno.demo@ejemplo.invalid'},
 '202211':{'id':'6020','matricula':'202211','nombre':'ALUMNA PRUEBA','nivel':'Licenciatura','grado':'Tercero','grupo':'B','ciclo':'2026/2027','email':'alumna.demo@ejemplo.invalid'}
}

class Handler(BaseHTTPRequestHandler):
    def respond(self, code, body):
        payload = json.dumps(body, ensure_ascii=False).encode()
        self.send_response(code)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Cache-Control', 'no-store')
        self.cors()
        self.send_header('Content-Length', str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def cors(self):
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Headers', 'Authorization,Content-Type')
        self.send_header('Access-Control-Allow-Methods', 'GET,POST,OPTIONS')

    def do_OPTIONS(self):
        self.send_response(204)
        self.cors()
        self.end_headers()

    def body(self):
        try:
            size = int(self.headers.get('Content-Length', '0'))
            if not 0 <= size <= 8192:
                raise ValueError()
            data = json.loads(self.rfile.read(size) or b'{}')
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
        if not session:
            self.respond(401, {'error': 'Tu sesión venció. Vuelve a ingresar.'})
        return session

    def guarded(self, action):
        try:
            action()
        except mail_delivery.DeliveryError as exc:
            self.respond(exc.status, {'error':str(exc)})
        except LookupError as exc:
            self.respond(404, {'error': str(exc)})
        except ValueError as exc:
            self.respond(400, {'error': str(exc)})
        except (BrokenPipeError, ConnectionResetError):
            pass
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
            return self.respond(200, {'status': 'ok', 'modo': 'DEMO', 'integracionReal': False})
        if path == '/api/services':
            return self.respond(200, mail_delivery.capabilities())
        if path == '/api/parking/printer':
            return self.respond(200, {'printer': parking.printer_name(), 'demo': True})
        session = self.require_session()
        if not session:
            return
        if path == '/api/me':
            return self.respond(200, {'estudiante': STUDENTS[session['matricula']]})
        if path == '/api/payments/history':
            return self.respond(200, {'payments':payments.history(session['matricula']), 'demo':True})
        if path == '/api/charges':
            return self.respond(200, {'matricula': session['matricula'], 'conceptos': payments.pending(session['matricula'], CONCEPTS), 'moneda': 'MXN', 'demo': True})
        return self.respond(404, {'error': 'Ruta no encontrada'})

    def print_document(self, document, invoice=False):
        try:
            result = parking.print_payload(payments.receipt(document, invoice))
            return {'printed': True, 'print': result}
        except (OSError, RuntimeError, subprocess.SubprocessError, ValueError) as exc:
            return {'printed': False, 'print_error': str(exc)[:300]}

    def post_route(self):
        path = urllib.parse.urlparse(self.path).path
        data = self.body()
        if path == '/api/auth/login':
            matricula = str(data.get('matricula', '')).strip()
            pin = str(data.get('pin', '')).strip()
            if matricula not in STUDENTS or pin != '1234':
                return self.respond(401, {'error': 'Matrícula o PIN demo incorrectos'})
            token = secrets.token_urlsafe(32)
            with LOCK:
                for stale in [t for t, s in TOKENS.items() if s['exp'] <= time.time()]:
                    TOKENS.pop(stale, None)
                TOKENS[token] = {'matricula': matricula, 'exp': time.time() + TTL}
            return self.respond(200, {'access_token': token, 'token_type': 'Bearer', 'expires_in': TTL, 'estudiante': STUDENTS[matricula], 'demo': True})
        if path == '/api/auth/logout':
            token = self.headers.get('Authorization', '')[7:]
            with LOCK:
                TOKENS.pop(token, None)
            return self.respond(200, {'ok': True})
        if path == '/api/parking/issue':
            ticket = parking.create_ticket()
            try:
                ticket.update({'print': parking.print_ticket(ticket), 'printed': True})
            except (OSError, RuntimeError, subprocess.SubprocessError, ValueError) as exc:
                ticket.update({'printed': False, 'print_error': str(exc)[:300]})
            return self.respond(200, {'ticket': ticket, 'demo': True})
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
    print(f'API DEMO http://{HOST}:{PORT}/api/health | matrículas 202210 / 202211; PIN 1234')
    ThreadingHTTPServer((HOST, PORT), Handler).serve_forever()
