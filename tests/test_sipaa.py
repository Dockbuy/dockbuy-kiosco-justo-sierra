import http.client
import json
import os
import pathlib
import sys
import threading
import unittest
from unittest.mock import Mock, MagicMock, patch

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / 'api'))
import sipaa
import server
import payments
from sipaa_fixture import kardex, login_response


def gateway(transport=None, **kwargs):
    config = sipaa.Config(**kwargs)
    return sipaa.Gateway(config, transport or Mock(side_effect=lambda url, data, *args:
                        login_response() if url.endswith('/direct') else kardex(data['tuition'])))


class NormalizationTests(unittest.TestCase):
    def test_nested_cycles_and_authoritative_balance(self):
        result = sipaa.normalize(kardex(), '000042')
        self.assertEqual([c['sourceId'] for c in result['conceptos']], ['10', '255', '256'])
        self.assertEqual([c['orden'] for c in result['conceptos']], [0, 1, 2])
        self.assertEqual(result['conceptos'][-1]['restante'], 5710)
        self.assertEqual(result['matricula'], '000042')
        self.assertFalse(result['demo'])

    def test_empty_and_paid_balances(self):
        for empty in ({}, []):
            data = kardex(); data['concepts'] = empty
            self.assertEqual(sipaa.normalize(data, '000042')['conceptos'], [])
        data = kardex(); data['concepts']['129'][0]['payments'][0]['pending_amount'] = '0.00'
        self.assertEqual(len(sipaa.normalize(data, '000042')['conceptos']), 2)

    def test_rejects_wrong_student_currency_error_and_malformed_hierarchy(self):
        for key, value in [('tuition', '000043'), ('currency', 'USD'), ('success', False),
                           ('concepts', None), ('concepts', {'129': {}})]:
            data = kardex(); data[key] = value
            with self.subTest(key=key), self.assertRaises(sipaa.IntegrationError):
                sipaa.normalize(data, '000042')

    def test_invalid_balances_and_dates_never_become_zero_or_guessed(self):
        for value in (None, True, '-1', 'NaN', '1,200', '$50', '0.001', '1000000000'):
            data = kardex(); data['concepts']['129'][0]['payments'][0]['pending_amount'] = value
            with self.subTest(value=value), self.assertRaises(sipaa.IntegrationError):
                sipaa.normalize(data, '000042')
        for value in (None, '2026-02-30', '31/12/2026'):
            data = kardex(); data['concepts']['129'][0]['payments'][0]['date_expiration'] = value
            with self.subTest(value=value), self.assertRaises(sipaa.IntegrationError):
                sipaa.normalize(data, '000042')

    def test_duplicate_ids_rejected_and_contract_scope_preserved(self):
        data = kardex(); parent = data['concepts']['129'][0]
        parent['payments'].append(dict(parent['payments'][0]))
        with self.assertRaises(sipaa.IntegrationError): sipaa.normalize(data, '000042')
        data = kardex(); data['concepts']['128'][0]['id'] = 256
        ids = [c['id'] for c in sipaa.normalize(data, '000042')['conceptos']]
        self.assertEqual(len(set(ids)), 3)

    def test_quote_requeries_and_preserves_cent_precision(self):
        g = gateway(); snapshot = g.consult('000042', 'student-token'); ids = [c['id'] for c in snapshot['conceptos']]
        self.assertEqual(sipaa.quote(g, '000042', 'student-token', ids[:2])['total'], .30)
        self.assertEqual(g.transport.call_count, 2)  # two independent reads with the same session token
        for invalid in (ids[1:], ids[::-1], ids + ids[:1], [True], []):
            with self.subTest(ids=invalid), self.assertRaises((ValueError, sipaa.IntegrationError)):
                sipaa.quote(g, '000042', 'student-token', invalid)


class GatewayTests(unittest.TestCase):
    def test_expiry_exception_is_explicit_and_disabled_by_default(self):
        self.assertFalse(sipaa.Config().ignore_expires_at)
        with patch.dict(os.environ,{},clear=True):
            self.assertFalse(sipaa.Config.from_env().ignore_expires_at)
        for value,enabled in [('1',True),('0',False),('',False),('true',False)]:
            with patch.dict(os.environ,{'SIPAA_IGNORE_EXPIRES_AT':value}):
                self.assertEqual(sipaa.Config.from_env().ignore_expires_at,enabled)

    def test_temporary_mode_ignores_only_expiry_and_keeps_bounded_local_session(self):
        import time
        for expiry in ('2026-10-12 13:14:08','invalid',None):
            data=login_response();data['data']['expires_at']=expiry
            access=gateway(Mock(return_value=data),ignore_expires_at=True).authenticate('000042','p')
            self.assertEqual(access.expires_in,600)
            self.assertGreater(access.expires_at-time.time(),590)
            self.assertLessEqual(access.expires_at-time.time(),600)
        for field,value in [('token',None),('token','bad\r\ntoken'),('token_type','Basic')]:
            data=login_response();data['data'][field]=value
            with self.subTest(field=field),self.assertRaises(sipaa.IntegrationError):
                gateway(Mock(return_value=data),ignore_expires_at=True).authenticate('000042','p')
        with self.assertRaises(sipaa.IntegrationError) as caught:
            gateway(Mock(side_effect=sipaa.UpstreamStatus(401)),ignore_expires_at=True).authenticate('000042','wrong')
        self.assertEqual(caught.exception.status,401)

    def test_disabling_exception_restores_expiry_validation(self):
        data=login_response();data['data']['expires_at']='2000-01-01 00:00:00'
        g=gateway(Mock(return_value=data),ignore_expires_at=True)
        self.assertEqual(g.authenticate('000042','p').expires_in,600)
        g.config=sipaa.Config(ignore_expires_at=False)
        with self.assertRaises(sipaa.IntegrationError) as caught:g.authenticate('000042','p')
        self.assertEqual(caught.exception.code,'sipaa_expired')

    def test_login_uses_form_credentials_and_fixed_ap_without_retaining_password(self):
        g = gateway()
        access = g.authenticate('000042', ' CaseSensitive$Password! ')
        self.assertEqual(g.transport.call_args.args[1], {
            'username': '000042', 'password': ' CaseSensitive$Password! ', 'system_code': 'AP'})
        result = g.consult('000042', access.token)
        self.assertEqual(g.transport.call_args.args[1:], ({'tuition': '000042'}, 'test-upstream-token'))
        self.assertNotIn('CaseSensitive', repr(vars(g)))
        self.assertNotIn('test-upstream-token', repr(access))
        self.assertNotIn('test-upstream-token', json.dumps(result))

    def test_documented_login_token_type_expiry_and_name(self):
        g=gateway(Mock(return_value=login_response()))
        access=g.authenticate('000042','p')
        self.assertEqual(access.token,'test-upstream-token')
        self.assertEqual(access.expires_in,600)
        self.assertEqual(access.name,'USUARIO DE PRUEBA')

    def test_missing_invalid_expired_or_wrong_type_tokens_fail_closed(self):
        for field,value in [('token',None),('token','bad\r\ntoken'),('token_type','Basic'),('expires_at','invalid'),('expires_at','2000-01-01 00:00:00')]:
            response=login_response();response['data'][field]=value
            with self.subTest(field=field),self.assertRaises(sipaa.IntegrationError):
                gateway(Mock(return_value=response)).authenticate('000042','p')
        for response in ({'access_token':'t'}, {'success':True,'data':None}):
            with self.assertRaises(sipaa.IntegrationError):gateway(Mock(return_value=response)).authenticate('000042','p')
        for config in (sipaa.Config(base_url='http://example.invalid'),sipaa.Config(timezone='invalid/timezone')):
            transport=Mock()
            with self.assertRaises(sipaa.IntegrationError):sipaa.Gateway(config,transport).authenticate('000042','p')
            transport.assert_not_called()

    def test_naive_expiry_uses_institution_timezone_and_short_expiry_is_respected(self):
        from datetime import datetime,timedelta
        from zoneinfo import ZoneInfo
        data=login_response()
        data['data']['expires_at']=(datetime.now(ZoneInfo('America/Mexico_City'))+timedelta(seconds=90)).strftime('%Y-%m-%d %H:%M:%S')
        access=gateway(Mock(return_value=data)).authenticate('000042','p')
        self.assertGreaterEqual(access.expires_in,87)
        self.assertLessEqual(access.expires_in,90)

    def test_wrong_password_does_not_retry_or_reveal_upstream_response(self):
        transport=Mock(side_effect=sipaa.UpstreamStatus(401))
        with self.assertRaises(sipaa.IntegrationError) as caught:gateway(transport).authenticate('000042','wrong')
        self.assertEqual(caught.exception.status,401)
        self.assertEqual(transport.call_count,1)

    def test_expired_student_token_is_not_refreshed_with_other_credentials(self):
        for upstream,local in ((401,401),(403,401),(404,404),(429,429),(500,503)):
            calls=Mock(side_effect=sipaa.UpstreamStatus(upstream))
            with self.subTest(upstream=upstream), self.assertRaises(sipaa.IntegrationError) as caught:
                gateway(calls).consult('000042','student-token')
            self.assertEqual(caught.exception.status,local)
            self.assertEqual(calls.call_count,1)

    def test_rate_limit_and_invalid_credentials(self):
        g=gateway()
        for _ in range(30):g.consult('000042','student-token')
        with self.assertRaises(sipaa.IntegrationError) as caught:g.consult('000042','student-token')
        self.assertEqual(caught.exception.status,429)
        for value in (None,42,'42abc','','1'*21):
            with self.assertRaises(ValueError):sipaa.tuition(value)
        for value in (None,'','p'*257):
            with self.assertRaises(ValueError):gateway().authenticate('000042',value)


class TransportTests(unittest.TestCase):
    def transport(self, status=200, raw=b'{"success":true}', content_type='application/json'):
        connection=MagicMock()
        response=connection.getresponse.return_value.__enter__.return_value
        response.status=status
        response.headers.get_content_type.return_value=content_type
        response.read.return_value=raw
        return connection

    def test_tls_post_headers_and_connection_cleanup(self):
        connection=self.transport()
        with patch.object(sipaa.http.client,'HTTPSConnection',return_value=connection) as constructor:
            self.assertTrue(sipaa.post_json('https://example.invalid/api/kardexStudent',{'tuition':'000042'},'secret-token')['success'])
        self.assertEqual(connection.request.call_args.args,('POST','/api/kardexStudent'))
        self.assertEqual(connection.request.call_args.kwargs['headers']['Authorization'],'Bearer secret-token')
        self.assertEqual(constructor.call_args.kwargs['context'].verify_mode,sipaa.ssl.CERT_REQUIRED)
        connection.close.assert_called_once()

    def test_redirect_bad_json_html_and_oversized_response_are_rejected(self):
        for status,raw,kind in [(302,b'','application/json'),(200,b'invalid','application/json'),
                                (200,b'<html>','text/html'),(200,b'x'*(2*1024*1024+1),'application/json')]:
            connection=self.transport(status,raw,kind)
            with self.subTest(status=status,kind=kind),patch.object(sipaa.http.client,'HTTPSConnection',return_value=connection):
                with self.assertRaises((sipaa.IntegrationError,sipaa.UpstreamStatus)):
                    sipaa.post_json('https://example.invalid/api/loginApp/direct',{'password':'secret'})
            self.assertEqual(connection.request.call_count,1)
            connection.close.assert_called_once()

    def test_timeout_does_not_return_transport_secrets(self):
        connection=self.transport();connection.connect.side_effect=TimeoutError('sensitive upstream details')
        with patch.object(sipaa.http.client,'HTTPSConnection',return_value=connection):
            with self.assertRaises(sipaa.IntegrationError) as caught:
                sipaa.post_json('https://example.invalid/api/loginApp/direct',{'password':'secret'})
        self.assertEqual(caught.exception.status,503)
        self.assertNotIn('sensitive',str(caught.exception))
        connection.close.assert_called_once()


class InstitutionalApiTests(unittest.TestCase):
    def setUp(self):
        self.mode = patch.object(server, 'DATA_SOURCE', 'sipaa'); self.mode.start()
        self.gateway = gateway()
        self.adapter = patch.object(server, 'SIPAA', self.gateway); self.adapter.start()
        # Una consulta real nunca debe tocar la base demo ni la impresora.
        self.db = patch.object(payments, 'connection', side_effect=AssertionError('Unexpected demo DB')); self.db.start()
        server.TOKENS.clear()
        self.http = server.ThreadingHTTPServer(('127.0.0.1', 0), server.Handler)
        self.thread = threading.Thread(target=self.http.serve_forever, daemon=True); self.thread.start()

    def tearDown(self):
        self.http.shutdown(); self.http.server_close(); self.thread.join()
        self.mode.stop(); self.adapter.stop(); self.db.stop(); server.TOKENS.clear()

    def req(self, path, data=None, token=None):
        c = http.client.HTTPConnection('127.0.0.1', self.http.server_port, timeout=5)
        headers = {'Content-Type': 'application/json'}
        if token: headers['Authorization'] = 'Bearer ' + token
        try:
            c.request('GET' if data is None else 'POST', '/api'+path, json.dumps(data) if data is not None else None, headers)
            response = c.getresponse()
            return response.status, json.loads(response.read())
        finally: c.close()

    def test_real_flow_is_scoped_to_session_and_cannot_pay_or_leak_demo_data(self):
        status, login = self.req('/auth/login', {'matricula':'000042','password':'test-password'})
        self.assertEqual(status, 200)
        token = login['access_token']
        self.assertNotIn('test-password', json.dumps(server.TOKENS))
        self.assertNotEqual(token, 'test-upstream-token')
        self.assertFalse(login['demo'])
        status, result = self.req('/charges?matricula=000043', token=token)
        self.assertEqual(result['matricula'], '000042')
        ids = [c['id'] for c in result['conceptos']]
        self.assertEqual(self.req('/payments/quote', {'concept_ids': ids[:2]}, token)[1]['total'], .30)
        for path in ('/payments/simulate', '/billing/invoice', '/billing/print', '/billing/email', '/campus/action', '/parking/issue'):
            self.assertEqual(self.req(path, {}, token)[0], 409)
        for path in ('/payments/history', '/campus/state', '/campus/public', '/admin/state'):
            self.assertEqual(self.req(path, token=token)[0], 409)
        self.assertEqual(self.req('/auth/logout', {}, token)[0], 200)
        self.assertEqual(self.req('/charges', token=token)[0], 401)

    def test_not_found_never_issues_a_session_or_uses_demo(self):
        with patch.object(self.gateway, 'consult', side_effect=sipaa.IntegrationError('No encontrado',404)):
            self.assertEqual(self.req('/auth/login', {'matricula':'202210','password':'test-password'})[0], 404)
        self.assertEqual(server.TOKENS, {})

    def test_temporary_exception_still_requires_protected_endpoint_acceptance(self):
        self.gateway.config=sipaa.Config(ignore_expires_at=True)
        data=login_response();data['data']['expires_at']='2000-01-01 00:00:00'
        self.gateway.transport=Mock(side_effect=[data,kardex()])
        status,result=self.req('/auth/login',{'matricula':'000042','password':'test-password'})
        self.assertEqual(status,200)
        self.assertGreater(result['expires_in'],590)
        self.assertLessEqual(result['expires_in'],600)
        self.assertEqual(self.gateway.transport.call_args.args[2],data['data']['token'])
        token=result['access_token']
        self.assertNotIn('test-password',json.dumps(server.TOKENS))
        # Si SIPAA rechaza el token después, también se revoca esta sesión local.
        self.gateway.transport=Mock(side_effect=sipaa.UpstreamStatus(401))
        self.assertEqual(self.req('/charges',token=token)[0],401)
        self.assertNotIn(token,server.TOKENS)
        for status in (401,403,500):
            self.gateway.transport=Mock(side_effect=[data,sipaa.UpstreamStatus(status)])
            code,result=self.req('/auth/login',{'matricula':'000042','password':'test-password'})
            self.assertEqual(code,401 if status in (401,403) else 503)
            self.assertNotIn('access_token',result)
            self.assertEqual(server.TOKENS,{})

    def test_client_cannot_enable_expiry_exception(self):
        data=login_response();data['data']['expires_at']='2000-01-01 00:00:00'
        self.gateway.transport=Mock(return_value=data)
        code,result=self.req('/auth/login',{'matricula':'000042','password':'p','ignore_expires_at':True})
        self.assertEqual(code,401)
        self.assertEqual(self.gateway.transport.call_count,1)
        self.assertNotIn('access_token',result)
        self.assertEqual(server.TOKENS,{})

    def test_changed_debt_refreshes_quote_and_rejects_removed_selection(self):
        token = self.req('/auth/login', {'matricula':'000042','password':'test-password'})[1]['access_token']
        result = self.req('/charges', token=token)[1]
        ids = [c['id'] for c in result['conceptos']]
        data = kardex(); data['concepts']['128'][0]['pending_amount'] = 900
        self.gateway.transport = Mock(return_value=data)
        self.assertEqual(self.req('/payments/quote', {'concept_ids':ids[:1]}, token)[1]['total'],900)
        data['concepts']['128'] = []
        self.assertEqual(self.req('/payments/quote', {'concept_ids':ids[:1]}, token)[0],409)

    def test_each_student_keeps_own_upstream_token_and_expiry_revokes_local_session(self):
        def transport(url,data,token=None):
            if url.endswith('/direct'):return login_response('upstream-'+data['username'])
            self.assertEqual(token,'upstream-'+data['tuition'])
            return kardex(data['tuition'])
        self.gateway.transport=Mock(side_effect=transport)
        a=self.req('/auth/login',{'matricula':'000042','password':'a'})[1]['access_token']
        b=self.req('/auth/login',{'matricula':'000043','password':'b'})[1]['access_token']
        self.assertEqual(self.req('/charges',token=a)[0],200)
        self.assertEqual(self.req('/charges',token=b)[0],200)
        with patch.object(self.gateway,'transport',side_effect=sipaa.UpstreamStatus(401)):
            self.assertEqual(self.req('/charges',token=a)[0],401)
        self.assertNotIn(a,server.TOKENS)
        self.assertIn(b,server.TOKENS)
