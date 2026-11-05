"""Entrega SMTP con TLS, adjuntos en memoria y protección contra reintentos duplicados."""
from dataclasses import dataclass
from email.message import EmailMessage
from email.utils import formatdate, make_msgid
import hashlib
import importlib.util
import os
import re
import smtplib
import ssl
import time
import payments
from document_pdf import make_pdf


class DeliveryError(Exception):
    def __init__(self, message, status=503):
        super().__init__(message)
        self.status = status


def validate_email(value):
    if not isinstance(value,str) or len(value)>254 or any(c in value for c in '\r\n\x00'):
        raise DeliveryError('Escribe un correo válido.',400)
    value=value.strip()
    if not re.fullmatch(r"[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]+@[A-Za-z0-9](?:[A-Za-z0-9-]*[A-Za-z0-9])?(?:\.[A-Za-z0-9](?:[A-Za-z0-9-]*[A-Za-z0-9])?)+",value):
        raise DeliveryError('Escribe un correo válido, por ejemplo nombre@dominio.com.',400)
    local,domain=value.rsplit('@',1)
    if len(local)>64 or local.startswith('.') or local.endswith('.') or '..' in local or any(len(label)>63 for label in domain.split('.')):
        raise DeliveryError('Escribe un correo válido.',400)
    return local+'@'+domain.lower()


@dataclass
class Config:
    host: str
    port: int
    security: str
    sender: str
    user: str
    password: str


def config():
    try:
        host=os.environ.get('SMTP_HOST','').strip()
        sender=validate_email(os.environ.get('SMTP_FROM',''))
        security=os.environ.get('SMTP_SECURITY','starttls')
        port=int(os.environ.get('SMTP_PORT','465' if security=='ssl' else '587'))
        user=os.environ.get('SMTP_USER',''); password=os.environ.get('SMTP_PASSWORD','')
        if not host or security not in ('ssl','starttls') or not 1<=port<=65535 or bool(user)!=bool(password):
            return None
        if importlib.util.find_spec('reportlab') is None:
            return None
        return Config(host,port,security,sender,user,password)
    except (ValueError,DeliveryError):
        return None


def capabilities():
    return {'email_available':config() is not None,'attachments':{'payment':['PDF'],'invoice':['PDF','XML']}}


def initialize(con):
    con.execute('''CREATE TABLE IF NOT EXISTS email_deliveries (
        request_id TEXT PRIMARY KEY, payment_code TEXT NOT NULL, kind TEXT NOT NULL,
        fingerprint TEXT NOT NULL, masked_recipient TEXT NOT NULL,
        status TEXT NOT NULL, created_at REAL NOT NULL, updated_at REAL NOT NULL)''')


def build_message(document, kind, recipient, settings, request_id):
    message=EmailMessage()
    message['From']=settings.sender; message['To']=recipient
    message['Subject']='Justo Sierra - '+('factura de prueba' if kind=='invoice' else 'comprobante de pago demo')
    message['Date']=formatdate(localtime=False)
    message['Message-ID']=make_msgid(idstring=request_id,domain=settings.sender.rsplit('@',1)[1])
    message.set_content('Adjuntamos tu documento de demostración del kiosco Justo Sierra.\n\n'
                        'DEMO / SIN VALIDEZ FISCAL / SIN COBRO REAL.\n'
                        'No es una factura timbrada ni un comprobante de pago real.\n'
                        'Puedes consultar el documento escaneando su QR en el mismo kiosco.\n')
    filename=document.get('folio',document['code'] if 'code' in document else 'documento')
    message.add_attachment(make_pdf(document,kind=='invoice'),maintype='application',subtype='pdf',filename=filename+'-DEMO.pdf')
    if kind=='invoice':
        message.add_attachment(document['xml'].encode('utf-8'),maintype='application',subtype='xml',filename=filename+'-DEMO.xml')
    return message


def smtp_send(message,settings):
    """Return accepted/failed/unknown. Only DATA transport failures are ambiguous."""
    client=None
    try:
        context=ssl.create_default_context()
        if settings.security=='ssl':
            client=smtplib.SMTP_SSL(settings.host,settings.port,timeout=10,context=context)
        else:
            client=smtplib.SMTP(settings.host,settings.port,timeout=10)
            client.ehlo();client.starttls(context=context);client.ehlo()
        if settings.user:
            client.login(settings.user,settings.password)
    except (smtplib.SMTPException,OSError,TimeoutError):
        if client:
            try: client.close()
            except OSError: pass
        return 'failed'
    try:
        refused=client.send_message(message)
        return 'failed' if refused else 'accepted'
    except smtplib.SMTPResponseException:
        return 'failed'
    except smtplib.SMTPRecipientsRefused:
        return 'failed'
    except (smtplib.SMTPException,OSError,TimeoutError):
        return 'unknown'
    finally:
        try: client.close()
        except OSError: pass


def response(row,reused=False):
    return {'delivery_id':row['request_id'],'status':row['status'],'recipient':row['masked_recipient'],'reused':reused}


def send(code,kind,recipient,request_id):
    code=payments.normalize_code(code)
    if kind not in ('payment','invoice'):
        raise DeliveryError('Tipo de documento inválido.',400)
    recipient=validate_email(recipient)
    if not isinstance(request_id,str) or not re.fullmatch(r'[A-Za-z0-9_-]{16,80}',request_id):
        raise DeliveryError('Identificador de envío inválido.',400)
    fingerprint=hashlib.sha256((code+'\0'+kind+'\0'+recipient).encode()).hexdigest()
    now=time.time()
    with payments.connection() as con:
        initialize(con);con.commit();con.execute('BEGIN IMMEDIATE')
        old=con.execute('SELECT * FROM email_deliveries WHERE request_id=?',(request_id,)).fetchone()
        if old:
            if old['fingerprint']!=fingerprint:
                raise DeliveryError('Este envío ya corresponde a otro documento o destinatario.',409)
            if old['status']=='sending' and now-old['updated_at']>120:
                con.execute("UPDATE email_deliveries SET status='unknown',updated_at=? WHERE request_id=?",(now,request_id))
                old=con.execute('SELECT * FROM email_deliveries WHERE request_id=?',(request_id,)).fetchone()
            return response(old,True)
    settings=config()
    if not settings:
        raise DeliveryError('El envío por correo aún no está disponible en este kiosco. Puedes imprimir tu ticket.',503)
    record=payments.lookup(code)
    document=record[kind]
    if not document:
        raise DeliveryError('Primero genera la factura de prueba.',400)
    message=build_message(document,kind,recipient,settings,request_id)
    local,domain=recipient.rsplit('@',1);masked=local[:1]+'***@'+domain
    with payments.connection() as con:
        initialize(con);con.commit();con.execute('BEGIN IMMEDIATE')
        old=con.execute('SELECT * FROM email_deliveries WHERE request_id=?',(request_id,)).fetchone()
        if old:
            if old['fingerprint']!=fingerprint:
                raise DeliveryError('Este envío ya corresponde a otro destinatario.',409)
            return response(old,True)
        recent=con.execute('SELECT count(*) FROM email_deliveries WHERE payment_code=? AND created_at>?',(code,now-600)).fetchone()[0]
        last=con.execute('SELECT max(created_at) FROM email_deliveries WHERE payment_code=? AND kind=?',(code,kind)).fetchone()[0]
        if recent>=3 or (last is not None and now-last<30):
            raise DeliveryError('Espera antes de solicitar otro envío. Revisa también tu carpeta de correo no deseado.',429)
        con.execute('INSERT INTO email_deliveries VALUES (?,?,?,?,?,?,?,?)',(request_id,code,kind,fingerprint,masked,'sending',now,now))
    status=smtp_send(message,settings)
    with payments.connection() as con:
        con.execute('UPDATE email_deliveries SET status=?,updated_at=? WHERE request_id=?',(status,time.time(),request_id))
        row=con.execute('SELECT * FROM email_deliveries WHERE request_id=?',(request_id,)).fetchone()
        return response(row)
