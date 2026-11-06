"""Regresiones de admisión: impresora simulada y sockets exclusivamente locales."""
import concurrent.futures
import http.client
import json
import socket
import subprocess
import sys
import threading
import time
import unittest
from unittest.mock import patch
import test_api

parking = test_api.parking
server = test_api.server
payments = test_api.payments


class SecurityLimitsTests(unittest.TestCase):
    setUp = test_api.ApiTests.setUp
    tearDown = test_api.ApiTests.tearDown
    req = test_api.ApiTests.req
    login = test_api.ApiTests.login
    pay = test_api.ApiTests.pay

    def raw(self, headers, body=b''):
        with socket.create_connection(('127.0.0.1', self.http.server_port), timeout=3) as client:
            client.sendall(headers.encode() + b'\r\n\r\n' + body)
            response = http.client.HTTPResponse(client)
            response.begin()
            return response.status, response.read()

    def head(self, path='/api/parking/issue'):
        return f'POST {path} HTTP/1.1\r\nHost: 127.0.0.1:{self.http.server_port}\r\nContent-Type: application/json'

    def test_repeated_prints_and_normalized_codes_share_the_limit(self):
        ticket = parking.create_ticket()
        self.assertEqual(self.req('/api/parking/reprint', {'code':ticket['code']})[0], 200)
        for _ in range(24):
            status, body = self.req('/api/parking/reprint?retry=1', {'code':' '+ticket['code'].lower()+' '})
            self.assertEqual(status, 429)
            self.assertGreater(body['retry_after'], 0)
        self.assertEqual(self.printer.call_count, 1)

    def test_three_attempts_per_document_and_expiry(self):
        ticket = parking.create_ticket()
        start = time.time()
        for offset in (0, 6, 12):
            with patch.object(parking.time, 'time', return_value=start+offset):
                parking.print_ticket(ticket)
        with patch.object(parking.time, 'time', return_value=start+18):
            with self.assertRaises(parking.PrintLimitError): parking.print_ticket(ticket)
        with patch.object(parking.time, 'time', return_value=start+601):
            parking.print_ticket(ticket)
        self.assertEqual(self.printer.call_count, 4)

    def test_global_budget_covers_distinct_documents_and_routes(self):
        self.pay()
        code = payments.history('202210')[0]['code']
        self.req('/api/billing/invoice', {'code':code})
        for _ in range(18): parking.print_ticket(parking.create_ticket())
        status, body = self.req('/api/parking/reprint', {'code':parking.create_ticket()['code']})
        self.assertEqual(status, 429)
        # Incluso al guardar otro pago, jamás se pierde por agotar el presupuesto.
        status, body = self.pay([55], key='another-payment-0001')
        self.assertEqual(status, 200)
        self.assertFalse(body['printed'])
        self.assertIn('Límite', body['print_error'])
        self.assertIsNotNone(payments.lookup(body['payment']['code']))
        self.assertEqual(self.printer.call_count, 20)

    def test_hourly_and_daily_budgets_survive_minute_window(self):
        now = time.time()
        for count, age in ((200, 61), (500, 3601)):
            with self.subTest(count=count), parking.connection() as con:
                con.execute('DELETE FROM print_attempts')
                con.executemany('INSERT INTO print_attempts VALUES (?,?)', [(f'parking:{i}', now-age) for i in range(count)])
            with self.assertRaises(parking.PrintLimitError): parking.print_ticket(parking.create_ticket())
        self.printer.assert_not_called()

    def test_failed_transport_still_consumes_attempt_and_later_recovers(self):
        ticket = parking.create_ticket()
        self.printer.side_effect = subprocess.TimeoutExpired('lp',12)
        with self.assertRaises(subprocess.TimeoutExpired): parking.print_ticket(ticket)
        self.printer.side_effect = None
        with self.assertRaises(parking.PrintLimitError): parking.print_ticket(ticket)
        with patch.object(parking.time, 'time', return_value=time.time()+6): parking.print_ticket(ticket)
        self.assertEqual(self.printer.call_count, 2)

    def test_print_budget_is_persistent_across_processes(self):
        ticket = parking.create_ticket()
        parking.print_ticket(ticket)
        code = "import sys; sys.path.insert(0,sys.argv[1]); import parking; from pathlib import Path; parking.DB=Path(sys.argv[2]); parking._send_payload=lambda p: sys.exit(9)\ntry: parking.print_ticket({'code':sys.argv[3], 'issued_at':sys.argv[4]})\nexcept parking.PrintLimitError: print('limited')"
        result = subprocess.run([sys.executable, '-B', '-c', code, str(test_api.pathlib.Path(server.__file__).parent), str(parking.DB),ticket['code'],ticket['issued_at']], capture_output=True, text=True, timeout=5)
        self.assertEqual((result.returncode, result.stdout.strip()), (0,'limited'), result.stderr)

    def test_print_queue_is_bounded_and_releases_slots(self):
        entered, release = threading.Event(), threading.Event()
        def transport(_):
            entered.set()
            if not release.wait(5): raise RuntimeError('test timeout')
            return {'job':'mock'}
        self.printer.side_effect = transport
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
            first = pool.submit(parking.print_ticket, parking.create_ticket())
            self.assertTrue(entered.wait(2))
            second = pool.submit(parking.print_ticket, parking.create_ticket())
            # Esperar a que el segundo ocupe el único lugar en espera.
            until = time.monotonic()+1
            while time.monotonic()<until:
                if not parking.PRINT_SLOTS.acquire(blocking=False): break
                parking.PRINT_SLOTS.release(); time.sleep(.01)
            try:
                with self.assertRaises(parking.PrintLimitError) as caught: parking.print_ticket(parking.create_ticket())
                self.assertEqual(caught.exception.status, 503)
            finally:
                release.set()
            first.result(3); second.result(3)
        self.printer.side_effect = None
        parking.print_ticket(parking.create_ticket())
        self.assertEqual(self.printer.call_count, 3)

    def test_parking_retry_is_persistent_and_concurrent_safe(self):
        def issue(_): return self.req('/api/parking/issue', {'request_id':'parking-request-0001'})
        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
            results = list(pool.map(issue, range(4)))
        self.assertTrue(all(status == 200 for status, _ in results))
        self.assertEqual(len({body['ticket']['code'] for _,body in results}), 1)
        self.assertEqual(self.printer.call_count, 1)
        self.assertTrue(issue(0)[1]['reused'])
        self.assertEqual(self.req('/api/parking/issue', {})[0], 400)

    def test_new_request_ids_do_not_bypass_ticket_creation_budget(self):
        for i in range(10):
            self.assertEqual(self.req('/api/parking/issue', {'request_id':f'parking-request-{i:04d}'})[0], 200)
        self.assertEqual(self.req('/api/parking/issue', {'request_id':'parking-request-9999'})[0], 429)
        self.assertTrue(self.req('/api/parking/issue', {'request_id':'parking-request-0000'})[1]['reused'])
        with parking.connection() as con: self.assertEqual(con.execute('SELECT count(*) FROM tickets').fetchone()[0],10)

    def test_billing_payment_and_invoice_use_distinct_canonical_keys(self):
        code = self.pay()[1]['payment']['code']
        self.assertTrue(self.req('/api/billing/invoice', {'code':code})[1]['printed'])
        for kind in ('payment','invoice'):
            result = self.req('/api/billing/print', {'code':' '+code.lower()+' ', 'kind':kind})[1]
            self.assertFalse(result['printed'])
            self.assertEqual(result['print_status'], 429)
        self.assertEqual(self.printer.call_count, 2)

    def test_campus_turn_print_is_limited_and_ownership_preserved(self):
        record = server.campus.action('202210', {'action':'turn','item':'caja','request_id':'campus-turn-test-0001'}, server.CONCEPTS)
        folio = record['folio']
        self.assertEqual(self.req('/api/campus/print-turn', {'folio':folio}, self.token)[0], 200)
        self.assertEqual(self.req('/api/campus/print-turn', {'folio':' '+folio+' '}, self.token)[0], 429)
        self.assertEqual(self.req('/api/campus/print-turn', {'folio':folio}, self.login('202211'))[0], 404)
        self.printer.assert_called_once()

    def test_browser_origin_and_media_type_rejected_before_side_effects(self):
        for origin in ('https://evil.invalid','null','http://localhost:1420.evil.invalid'):
            self.assertEqual(self.req('/api/parking/issue', {'request_id':'origin-request-0001'}, headers={'Origin':origin})[0], 403)
            self.assertEqual(self.req('/api/health', method='GET', headers={'Origin':origin})[0], 403)
        for media in ('text/plain','application/x-www-form-urlencoded','multipart/form-data'):
            self.assertEqual(self.req('/api/parking/issue', {}, headers={'Content-Type':media})[0], 415)
        self.printer.assert_not_called()

    def test_native_and_browser_origins_and_preflight_remain_supported(self):
        for origin in self.http.allowed_origins:
            connection = http.client.HTTPConnection('127.0.0.1',self.http.server_port,timeout=3)
            connection.request('OPTIONS','/api/auth/login',headers={'Origin':origin,'Access-Control-Request-Method':'POST','Access-Control-Request-Headers':'authorization,content-type'})
            response = connection.getresponse()
            self.assertEqual(response.status,204)
            self.assertEqual(response.getheader('Access-Control-Allow-Origin'), origin)
            response.read(); connection.close()
            self.assertEqual(self.req('/api/auth/login', {'matricula':'202210','pin':'1234'}, headers={'Origin':origin})[0],200)
        self.assertEqual(self.req('/api/health',method='GET')[0],200)

    def test_host_absolute_authority_and_duplicate_headers_are_rejected(self):
        port = self.http.server_port
        for header in (self.head()+f'\r\nHost: localhost:{port}', self.head()+'\r\nOrigin: http://localhost:1420\r\nOrigin: https://evil.invalid'):
            self.assertEqual(self.raw(header)[0],403)
        self.assertEqual(self.req('/api/health',method='GET',headers={'Host':'evil.invalid'})[0],403)
        self.assertEqual(self.raw(self.head('http://evil.invalid/api/parking/issue'))[0],400)
        self.printer.assert_not_called()

    def test_ambiguous_framing_and_oversized_body_are_rejected(self):
        for extra in ('Content-Length: 2\r\nContent-Length: 2','Transfer-Encoding: chunked','Content-Length: -1','Content-Length: +2','Content-Length: 2,2'):
            self.assertEqual(self.raw(self.head()+'\r\n'+extra,b'{}')[0],400)
        self.assertEqual(self.raw(self.head()+'\r\nContent-Length: 8193')[0],413)
        self.printer.assert_not_called()

    def test_early_eof_does_not_accept_a_partial_json_body(self):
        with socket.create_connection(('127.0.0.1', self.http.server_port), timeout=3) as client:
            client.sendall((self.head()+'\r\nContent-Length: 50\r\n\r\n{}').encode())
            client.shutdown(socket.SHUT_WR)
            response=http.client.HTTPResponse(client); response.begin()
            self.assertEqual(response.status,400)
        self.printer.assert_not_called()

    def test_absolute_deadline_closes_slow_headers_and_body_even_with_drips(self):
        self.http.read_deadline = .35
        for initial in (b'POST /api/parking/issue HTTP/1.1\r\nX-Slow: ', (self.head()+'\r\nContent-Length: 100\r\n\r\n').encode()):
            with socket.create_connection(('127.0.0.1',self.http.server_port),timeout=2) as client:
                client.sendall(initial)
                started=time.monotonic()
                while time.monotonic()-started < .7:
                    try: client.sendall(b' ')
                    except OSError: break
                    time.sleep(.04)
                try: result=client.recv(1)
                except (ConnectionResetError,ConnectionAbortedError): result=b''
                self.assertEqual(result,b'')
                self.assertLess(time.monotonic()-started,1.5)
        self.assertEqual(self.req('/api/health',method='GET')[0],200)
        self.printer.assert_not_called()

    def test_worker_overflow_returns_503_and_service_recovers(self):
        self.http.read_deadline = .5
        clients=[]
        try:
            for _ in range(self.http.max_workers):
                client=socket.create_connection(('127.0.0.1',self.http.server_port),timeout=2)
                client.sendall(b'GET /api/health HTTP/1.1\r\nX-Slow: ')
                clients.append(client)
            status, body=self.req('/api/health',method='GET')
            self.assertEqual(status,503)
            self.assertIn('ocupada',body['error'])
        finally:
            for client in clients: client.close()
        time.sleep(.6)
        self.assertEqual(self.req('/api/health',method='GET')[0],200)

    def test_request_budget_and_session_cap(self):
        self.http.requests_per_minute=2 # La sesión del setup ya consumió una solicitud.
        self.assertEqual(self.req('/api/health',method='GET')[0],200)
        self.assertEqual(self.req('/api/health',method='GET')[0],429)
        self.http.requests_per_minute=240
        with server.LOCK:
            for i in range(256): server.TOKENS[str(i)]={'matricula':'202210','exp':time.time()+60}
        self.assertEqual(self.req('/api/auth/login',{'matricula':'202210','pin':'1234'})[0],429)

    def test_non_loopback_listener_is_refused(self):
        with self.assertRaises(ValueError): server.ThreadingHTTPServer(('0.0.0.0',0), server.Handler)

    def test_processing_after_body_is_not_subject_to_read_deadline(self):
        self.http.read_deadline=.15
        def transport(_):
            time.sleep(.3)
            return {'job':'mock'}
        self.printer.side_effect=transport
        self.assertTrue(self.req('/api/parking/issue',{'request_id':'long-print-test-0001'})[1]['ticket']['printed'])
