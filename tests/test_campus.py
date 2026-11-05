import concurrent.futures
import io
import os
from pathlib import Path
import sys
import tempfile
import unittest
import uuid
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'api'))
import campus
import payments
import server
import mail_delivery
from campus_pdf import make_constancia
from pypdf import PdfReader


class CampusTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.db=patch.object(payments,'DB',Path(self.temp.name)/'demo.sqlite3');self.db.start()
        self.student=server.STUDENTS['202210']

    def tearDown(self):
        self.db.stop();self.temp.cleanup()

    def act(self,action='procedure',item='estudios',matricula='202210',**extra):
        return campus.action(matricula,{'action':action,'item':item,'request_id':str(uuid.uuid4()),**extra},[])

    def pay(self):
        pending=payments.pending('202210',[])
        return payments.simulate(self.student,[],[c['id'] for c in pending],str(uuid.uuid4()))

    def transition(self,r,status):
        return campus.admin_action({'action':'transition','folio':r['folio'],'status':status},[])

    def test_charge_lifecycle_and_owned_records(self):
        r=self.act()
        self.assertEqual(payments.pending('202210',[])[0]['restante'],120)
        self.assertEqual(payments.pending('202211',[]),[])
        with self.assertRaises(ValueError): self.transition(r,'revision')
        with self.assertRaises(LookupError): self.act('cancel',folio=r['folio'],matricula='202211')
        with self.assertRaises(ValueError): campus.document('202210',r['folio'],self.student)
        self.pay()
        with self.assertRaises(ValueError): self.act('cancel',folio=r['folio'])
        self.transition(r,'revision');self.transition(r,'listo')
        doc=campus.document('202210',r['folio'],self.student)
        pdf=PdfReader(io.BytesIO(make_constancia(doc)))
        self.assertIn('SIN VALIDEZ',pdf.pages[0].extract_text())
        self.assertIn(r['folio'],pdf.pages[0].extract_text())
        self.assertEqual(campus.state('202211',[])['records'],[])

    def test_cancel_removes_charge_and_cannot_pay_stale_selection(self):
        r=self.act();ids=[c['id'] for c in payments.pending('202210',[])]
        self.act('cancel',folio=r['folio'])
        self.assertEqual(payments.pending('202210',[]),[])
        with self.assertRaises(ValueError):payments.simulate(self.student,[],ids,str(uuid.uuid4()))
        self.assertEqual(self.act('cancel',folio=r['folio'])['status'],'cancelado')

    def test_idempotent_and_duplicate_active_procedures(self):
        operation=str(uuid.uuid4())
        r=self.act(request_id=operation)
        self.assertEqual(self.act(request_id=operation)['folio'],r['folio'])
        with self.assertRaises(ValueError):self.act()
        with self.assertRaises(ValueError):self.act(item='credencial',request_id=operation)

    def test_concurrent_appointment_has_one_winner(self):
        slot=campus.state('202210',[])['slots']['caja'][0]
        def reserve(m):
            try:return self.act('appointment','caja',matricula=m,detail=slot)['folio']
            except ValueError:return None
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
            results=list(pool.map(reserve,['202210','202211']))
        self.assertEqual(sum(r is not None for r in results),1)
        record=campus.admin_state()['records'][0]
        self.act('cancel',matricula=record['matricula'],folio=record['folio'])
        self.assertIn(slot,campus.state('202210',[])['slots']['caja'])

    def test_capacity_atomic_and_admin_cannot_reduce_below_occupied(self):
        activities=campus.admin_state()['config']['activities'];activities[0]['capacity']=1
        campus.admin_action({'action':'config','section':'activities','value':activities},[])
        def enroll(m):
            try:return self.act('activity','robotica',matricula=m)
            except ValueError:return None
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
            results=list(pool.map(enroll,['202210','202211']))
        self.assertEqual(sum(r is not None for r in results),1)
        self.assertEqual(campus.state('202210',[])['activities'][0]['available'],0)

    def test_turn_fifo_and_one_at_a_time(self):
        first=self.act('turn','caja');second=self.act('turn','caja',matricula='202211')
        self.assertEqual(second['ahead'],1)
        with self.assertRaises(ValueError):self.transition(second,'llamado')
        self.transition(first,'llamado')
        self.assertEqual(campus.public()['called'][0]['folio'],first['folio'])
        with self.assertRaises(ValueError):self.transition(second,'llamado')
        self.transition(first,'completado');self.transition(second,'llamado')

    def test_expired_turn_does_not_block_new_turn(self):
        r=self.act('turn','caja')
        with campus.db(True) as con:con.execute("UPDATE campus_records SET created='2020-01-01T12:00:00+00:00' WHERE id=?",(r['id'],))
        self.assertNotEqual(self.act('turn','caja')['folio'],r['folio'])

    def test_renewal_ownership_limit_and_reservation_conversion(self):
        loan=campus.state('202210',[])['loans'][0]
        with self.assertRaises(LookupError):self.act('renew',matricula='202211',id=loan['id'])
        self.act('renew',id=loan['id'])
        with self.assertRaises(ValueError):self.act('renew',id=loan['id'])
        r=self.act('book','historia');before=campus.state('202210',[])['books'][1]['available']
        self.transition(r,'entregado')
        self.assertEqual(campus.state('202210',[])['books'][1]['available'],before)
        borrowed=next(l for l in campus.state('202210',[])['loans'] if l['book']=='historia')
        campus.admin_action({'action':'return_book','id':borrowed['id']},[])
        self.assertEqual(campus.state('202210',[])['books'][1]['available'],before+1)

    def test_reenrollment_requires_three_checks(self):
        campus.state('202210',[])
        with self.assertRaises(ValueError):self.act(item='reinscripcion')
        campus.admin_action({'action':'validate','matricula':'202210','documents':True,'academic':True},[])
        r=self.act(item='reinscripcion');self.transition(r,'revision');self.transition(r,'listo')
        self.assertEqual(r['fee'],0)

    def test_configuration_affects_new_requests_only(self):
        r=self.act();config=campus.admin_state()['config']['procedures'];config[0]['fee']=200
        campus.admin_action({'action':'config','section':'procedures','value':config},[])
        self.assertEqual(payments.pending('202210',[])[0]['restante'],120)
        self.assertEqual(self.act(matricula='202211')['fee'],200)
        campus.admin_action({'action':'config','section':'disabled','value':['credencial']},[])
        with self.assertRaises(ValueError):self.act(item='credencial')
        self.act('cancel',folio=r['folio'])

    def test_appointment_hours_configured(self):
        departments=campus.admin_state()['config']['departments'];departments[0]['start_hour']=15;departments[0]['end_hour']=17
        campus.admin_action({'action':'config','section':'departments','value':departments},[])
        slots=campus.state('202210',[])['slots']['caja']
        self.assertEqual({s[-5:] for s in slots},{'15:00','16:00'})

    def test_survey_and_metrics_no_identity_and_no_duplicate(self):
        data={'session':str(uuid.uuid4()),'module':'citas','event':'open'}
        campus.event(data);campus.event(data)
        campus.event({'session':data['session'],'score':5,'topic':'facilidad'},True)
        campus.event({'session':data['session'],'score':1,'topic':'facilidad'},True)
        result=campus.admin_state()
        self.assertEqual(result['metrics'][0]['total'],1)
        self.assertEqual(result['surveys']['average'],5)

    def test_constancia_email_is_authorized_and_idempotent(self):
        r=self.act();self.pay();self.transition(r,'revision');self.transition(r,'listo')
        doc=campus.document('202210',r['folio'],self.student)
        key=str(uuid.uuid4())
        with patch.object(mail_delivery,'config',return_value=mail_delivery.Config('test.invalid',587,'starttls','kiosco@example.invalid','','')),patch.object(mail_delivery,'smtp_send',return_value='accepted') as send:
            first=mail_delivery.send(r['folio'],'campus','test@example.invalid',key,doc)
            second=mail_delivery.send(r['folio'],'campus','test@example.invalid',key,doc)
            self.assertEqual(first['status'],'accepted');self.assertTrue(second['reused']);self.assertEqual(send.call_count,1)
            attachment=list(send.call_args.args[0].iter_attachments())[0]
            self.assertEqual(attachment.get_content_type(),'application/pdf')

    def test_admin_password_not_plaintext(self):
        digest=campus.password_hash('test-only-admin-123')
        self.assertNotIn('test-only-admin-123',digest)
        with patch.dict(os.environ,{'ADMIN_PASSWORD_HASH':digest}):
            self.assertTrue(campus.verify_admin('test-only-admin-123'))
            self.assertFalse(campus.verify_admin('1234'))


if __name__=='__main__':unittest.main()
