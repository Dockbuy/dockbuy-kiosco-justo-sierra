import concurrent.futures
from io import BytesIO
import os
from pathlib import Path
import smtplib
import sys
import tempfile
import unittest
from unittest.mock import MagicMock,patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'api'))
import catalog
import payments
import mail_delivery as mail
from document_pdf import make_pdf


class MailTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.db=patch.object(payments,'DB',Path(self.temp.name)/'demo.sqlite3');self.db.start()
        self.settings=mail.Config('smtp.example.invalid',587,'starttls','kiosco@example.invalid','','')
        self.configuration=patch.object(mail,'config',return_value=self.settings);self.configuration.start()
        self.transport=patch.object(mail,'smtp_send',return_value='accepted');self.smtp=self.transport.start()
        self.payment=payments.simulate({'matricula':'202210'},catalog.CONCEPTS,[101,102],'payment-operation-1234')[0]
        self.code=self.payment['code']
        self.invoice=payments.create_invoice(self.code)[0]
    def tearDown(self):
        self.transport.stop();self.configuration.stop();self.db.stop();self.temp.cleanup()
    def send(self,kind='payment',key='email-operation-0001',email='alumno@example.invalid'):
        return mail.send(self.code,kind,email,key)
    def test_without_provider_never_claims_sent(self):
        with patch.object(mail,'config',return_value=None):
            self.assertFalse(mail.capabilities()['email_available'])
            with self.assertRaises(mail.DeliveryError) as error:self.send()
        self.assertEqual(error.exception.status,503);self.smtp.assert_not_called()
    def test_receipt_attaches_pdf_and_invoice_attaches_pdf_xml(self):
        self.send();message=self.smtp.call_args.args[0]
        self.assertEqual([a.get_content_type() for a in message.iter_attachments()],['application/pdf'])
        self.assertTrue(next(message.iter_attachments()).get_payload(decode=True).startswith(b'%PDF-'))
        self.send('invoice','invoice-email-0001');message=self.smtp.call_args.args[0]
        self.assertEqual([a.get_content_type() for a in message.iter_attachments()],['application/pdf','application/xml'])
        self.assertIn('SIN VALIDEZ FISCAL',message.get_body(preferencelist=('plain',)).get_content())
    def test_retry_does_not_send_duplicate(self):
        first=self.send();second=self.send()
        self.assertEqual(first['status'],'accepted');self.assertTrue(second['reused']);self.assertEqual(self.smtp.call_count,1)
    def test_concurrent_retry_sends_once(self):
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:results=list(pool.map(lambda _:self.send(),range(2)))
        self.assertEqual(self.smtp.call_count,1);self.assertTrue(all(r['status'] in ('sending','accepted') for r in results))
    def test_unknown_delivery_does_not_resend(self):
        self.smtp.return_value='unknown'
        self.assertEqual(self.send()['status'],'unknown');self.assertEqual(self.send()['status'],'unknown');self.assertEqual(self.smtp.call_count,1)
    def test_failed_delivery_is_not_success(self):
        self.smtp.return_value='failed';self.assertEqual(self.send()['status'],'failed')
    def test_invalid_email_and_header_injection_rejected(self):
        for email in ['wrong','a@example.com\r\nBcc: victim@example.com','a..b@example.com','a@-host.com','a@b','a'*65+'@example.com']:
            with self.subTest(email=email),self.assertRaises(mail.DeliveryError):self.send(email=email)
        self.smtp.assert_not_called()
    def test_request_id_cannot_change_recipient(self):
        self.send()
        with self.assertRaises(mail.DeliveryError) as error:self.send(email='other@example.invalid')
        self.assertEqual(error.exception.status,409)
    def test_rate_limit_for_new_send_keys(self):
        self.send()
        with self.assertRaises(mail.DeliveryError) as error:self.send(key='email-operation-0002')
        self.assertEqual(error.exception.status,429)
    def test_no_plaintext_recipient_in_database(self):
        result=self.send();self.assertEqual(result['recipient'],'a***@example.invalid')
        with payments.connection() as con:row=dict(con.execute('SELECT * FROM email_deliveries').fetchone())
        self.assertNotIn('alumno@example.invalid',str(row))
    def test_pdf_long_catalog_renders_multiple_pages(self):
        from pypdf import PdfReader
        document={**self.invoice,'conceptos':catalog.CONCEPTS,'total':payments.total(catalog.CONCEPTS)}
        reader=PdfReader(BytesIO(make_pdf(document,True)))
        text='\n'.join(p.extract_text() for p in reader.pages)
        self.assertGreaterEqual(len(reader.pages),2)
        self.assertIn('SIN VALIDEZ FISCAL',text)
        self.assertIn('COLEGIATURA SEPTIEMBRE',text)
        self.assertIn('Página 2',text)
    def test_catalog_contains_expected_services_and_keeps_ids(self):
        self.assertEqual(len(catalog.CONCEPTS),16)
        groups={c['grupo'] for c in catalog.CONCEPTS}
        self.assertTrue({'COLEGIATURA','INSCRIPCIÓN','TRANSPORTE','SEGURO ESCOLAR','LABORATORIO','BIBLIOTECA','ACTIVIDADES'}.issubset(groups))
        self.assertTrue({36,45,55,56}.issubset({c['id'] for c in catalog.CONCEPTS}))
    def test_history_is_scoped_to_student(self):
        self.assertEqual(len(payments.history('202210')),1);self.assertEqual(payments.history('202211'),[])


class SmtpTests(unittest.TestCase):
    def settings(self):return mail.Config('smtp.example.invalid',587,'starttls','k@example.invalid','user','password')
    def test_starttls_and_auth_before_acceptance(self):
        with patch.object(mail.smtplib,'SMTP') as smtp:
            smtp.return_value.send_message.return_value={}
            self.assertEqual(mail.smtp_send(MagicMock(),self.settings()),'accepted')
            smtp.return_value.starttls.assert_called_once();smtp.return_value.login.assert_called_once_with('user','password')
    def test_connection_failure_is_failed_and_data_disconnect_unknown(self):
        with patch.object(mail.smtplib,'SMTP',side_effect=OSError('offline')):
            self.assertEqual(mail.smtp_send(MagicMock(),self.settings()),'failed')
        with patch.object(mail.smtplib,'SMTP') as smtp:
            smtp.return_value.send_message.side_effect=smtplib.SMTPServerDisconnected('lost')
            self.assertEqual(mail.smtp_send(MagicMock(),self.settings()),'unknown')
    def test_incomplete_or_insecure_config_is_unavailable(self):
        with patch.dict(os.environ,{'SMTP_HOST':'smtp.invalid','SMTP_FROM':'k@example.invalid','SMTP_SECURITY':'none'},clear=True):self.assertIsNone(mail.config())
        with patch.dict(os.environ,{},clear=True):self.assertIsNone(mail.config())


if __name__=='__main__':unittest.main(verbosity=2)
