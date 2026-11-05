import concurrent.futures
import datetime
import http.client
import json
import pathlib
import sqlite3
import subprocess
import sys
import tempfile
import threading
import unittest
import xml.etree.ElementTree as ET
from unittest.mock import patch

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / 'api'))
import parking
import payments
import server


class ApiTests(unittest.TestCase):
    def setUp(self):
        # Estas pruebas de contrato usan el catálogo original de cuatro conceptos.
        self.catalog_mock = patch.object(server, 'CONCEPTS', [c for c in server.CONCEPTS if c['id'] in (36,45,55,56)])
        self.catalog_mock.start()
        self.temp = tempfile.TemporaryDirectory()
        parking.DB = pathlib.Path(self.temp.name) / 'parking.sqlite3'
        payments.DB = pathlib.Path(self.temp.name) / 'payments.sqlite3'
        server.TOKENS.clear()
        self.print_mock = patch.object(parking, 'print_payload', return_value={'printer':'TEST', 'job':'mock'})
        self.printer = self.print_mock.start()
        self.http = server.ThreadingHTTPServer(('127.0.0.1', 0), server.Handler)
        self.thread = threading.Thread(target=self.http.serve_forever, daemon=True)
        self.thread.start()
        self.token = self.login()

    def tearDown(self):
        self.http.shutdown(); self.http.server_close(); self.thread.join()
        self.print_mock.stop(); self.catalog_mock.stop(); self.temp.cleanup()

    def req(self, path, body=None, token=None, method='POST', headers=None):
        connection = http.client.HTTPConnection('127.0.0.1', self.http.server_port, timeout=5)
        request_headers = {'Content-Type':'application/json'}
        if token:
            request_headers['Authorization'] = 'Bearer ' + token
        request_headers.update(headers or {})
        try:
            connection.request(method, path, json.dumps(body) if body is not None else None, request_headers)
            result = connection.getresponse()
            return result.status, json.loads(result.read())
        finally:
            connection.close()

    def login(self, matricula='202210'):
        status, result = self.req('/api/auth/login', {'matricula':matricula,'pin':'1234'})
        self.assertEqual(status, 200)
        return result['access_token']

    def pay(self, ids=None, key='operation-test-0001', token=None):
        return self.req('/api/payments/simulate', {'concept_ids':ids or [45,36], 'request_id':key}, token or self.token)

    def test_pending_sorted_by_due_date(self):
        status, body = self.req('/api/charges', token=self.token, method='GET')
        self.assertEqual(status, 200)
        self.assertEqual([c['id'] for c in body['conceptos']], [45,36,55,56])

    def test_reject_skipped_reordered_and_duplicate_concepts(self):
        for ids in ([36], [36,45], [45,45], [45,999], [True], []):
            with self.subTest(ids=ids):
                self.assertEqual(self.req('/api/payments/quote', {'concept_ids':ids}, self.token)[0], 400)

    def test_quote_total_and_demo_flag(self):
        status, body = self.req('/api/payments/quote', {'concept_ids':[45,36]}, self.token)
        self.assertEqual((status,body['total'],body['cobroReal']), (200,5525,False))

    def test_payment_is_saved_and_removes_pending(self):
        status, body = self.pay()
        self.assertEqual(status, 200)
        self.assertTrue(body['printed'])
        self.assertEqual(body['payment']['total'], 5525)
        self.assertEqual([c['id'] for c in body['conceptos']], [55,56])
        self.assertEqual(payments.lookup(body['payment']['code'])['payment']['status'], 'PAGADO_DEMO')
        other = self.login('202211')
        self.assertEqual(len(self.req('/api/charges', token=other, method='GET')[1]['conceptos']), 4)

    def test_retry_reuses_payment_and_does_not_print_twice(self):
        first = self.pay()[1]
        second = self.pay()[1]
        self.assertEqual(first['payment']['code'], second['payment']['code'])
        self.assertTrue(second['reused'])
        self.assertEqual(self.printer.call_count, 1)

    def test_reused_key_rejects_changed_selection(self):
        self.pay()
        self.assertEqual(self.pay([55])[0], 400)

    def test_concurrent_retries_only_create_one_payment(self):
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
            responses = list(pool.map(lambda _: self.pay(), range(2)))
        self.assertEqual([r[0] for r in responses], [200,200])
        self.assertEqual(responses[0][1]['payment']['code'],responses[1][1]['payment']['code'])
        self.assertEqual(self.printer.call_count, 1)

    def test_concurrent_distinct_operations_cannot_pay_same_concepts(self):
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
            responses = list(pool.map(lambda key: self.pay(key=key), ['operation-test-0001','operation-test-0002']))
        self.assertEqual(sorted(r[0] for r in responses), [200,400])

    def test_invoice_is_idempotent_and_explicitly_non_fiscal(self):
        code = self.pay()[1]['payment']['code']
        status, first = self.req('/api/billing/invoice', {'code':code})
        second = self.req('/api/billing/invoice', {'code':code})[1]
        self.assertEqual(status, 200)
        self.assertEqual(first['invoice']['folio'], second['invoice']['folio'])
        self.assertTrue(second['reused'])
        self.assertFalse(first['invoice']['timbrado'])
        xml = payments.lookup(code)['invoice']['xml']
        self.assertNotIn('xml',first['invoice'])
        root = ET.fromstring(xml)
        self.assertTrue(root.tag.endswith('Comprobante'))
        self.assertIn('SIN VALIDEZ FISCAL', xml)
        self.assertNotIn('TimbreFiscalDigital', xml)
        self.assertEqual(self.printer.call_count, 2)

    def test_invoice_requires_existing_payment(self):
        self.assertEqual(self.req('/api/billing/invoice', {'code':'JS-PAY-'+'A'*32})[0], 404)
        self.assertEqual(self.req('/api/billing/invoice', {'code':'invalid'})[0], 400)

    def test_print_failure_does_not_lose_payment_or_invoice(self):
        self.printer.side_effect = subprocess.TimeoutExpired('lp',12)
        status, body = self.pay()
        self.assertEqual(status,200); self.assertFalse(body['printed'])
        code = body['payment']['code']
        status, result = self.req('/api/billing/invoice', {'code':code})
        self.assertEqual(status,200); self.assertFalse(result['printed'])
        self.assertIsNotNone(payments.lookup(code)['invoice'])
        self.printer.side_effect = None
        self.assertTrue(self.req('/api/billing/print', {'code':code,'kind':'invoice'})[1]['printed'])

    def test_receipt_encodes_the_same_qr_payload(self):
        payment = self.pay()[1]['payment']
        payload = payments.receipt(payment)
        self.assertIn(parking.qr_command(payment['code']), payload)
        self.assertIn(b'SIN VALIDEZ FISCAL', payload)

    def test_malformed_json_returns_json_error(self):
        for body in ([], 'text', 42):
            status, result = self.req('/api/auth/login', body)
            self.assertEqual(status, 400); self.assertIn('error', result)
        self.assertEqual(self.req('/api/health', method='GET')[0],200)

    def test_negative_content_length_is_rejected(self):
        self.assertEqual(self.req('/api/auth/login', headers={'Content-Length':'-1'})[0],400)

    def test_expired_and_revoked_tokens(self):
        server.TOKENS[self.token]['exp'] = 0
        self.assertEqual(self.pay()[0],401)
        token = self.login()
        self.assertEqual(self.req('/api/auth/logout', {}, token)[0],200)
        self.assertEqual(self.req('/api/charges', token=token, method='GET')[0],401)

    def test_parking_timeout_returns_structured_error(self):
        ticket = parking.create_ticket()
        self.printer.side_effect = subprocess.TimeoutExpired('lp',12)
        status, body = self.req('/api/parking/reprint', {'code':ticket['code']})
        self.assertEqual(status,503); self.assertIn('error',body)

    def test_parking_rate_boundaries(self):
        ticket = parking.create_ticket()
        fixed = datetime.datetime(2026,11,5,12,tzinfo=datetime.timezone.utc)
        class FixedDatetime(datetime.datetime):
            @classmethod
            def now(cls, tz=None): return fixed
        for seconds, expected in [(0,20),(28800,20),(28801,40),(57600,40)]:
            with parking.connection() as con:
                con.execute('UPDATE tickets SET issued_at=? WHERE code=?', ((fixed-datetime.timedelta(seconds=seconds)).isoformat(),ticket['code']))
            with patch.object(parking.datetime,'datetime',FixedDatetime):
                self.assertEqual(parking.quote_ticket(ticket['code'])['total'],expected)

    def test_database_failure_returns_json(self):
        with patch.object(payments,'simulate',side_effect=sqlite3.OperationalError('locked')):
            status, body = self.pay()
        self.assertEqual(status,503); self.assertIn('error',body)


if __name__ == '__main__':
    unittest.main(verbosity=2)
