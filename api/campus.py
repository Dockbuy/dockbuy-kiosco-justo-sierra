"""Servicios escolares DEMO persistentes. No representa políticas oficiales del plantel."""
from contextlib import contextmanager
from datetime import date, datetime, timedelta, timezone
import hashlib
import hmac
import json
import os
import re
import secrets
import time
import payments

DEPARTMENTS = [
    {'id':'caja','name':'Caja','location':'Edificio A · planta baja','hours':'Lunes a viernes · 09:00–14:00','requirements':'Matrícula y folio del servicio','contact':'Atención presencial'},
    {'id':'escolares','name':'Servicios escolares','location':'Edificio A · primer piso','hours':'Lunes a viernes · 09:00–14:00','requirements':'Matrícula e identificación','contact':'Atención presencial'},
    {'id':'becas','name':'Becas','location':'Edificio B · planta baja','hours':'Lunes a viernes · 09:00–14:00','requirements':'Matrícula y solicitud de apoyo','contact':'Atención presencial'},
    {'id':'biblioteca','name':'Biblioteca','location':'Edificio C · planta baja','hours':'Lunes a viernes · 08:00–17:00','requirements':'Credencial vigente','contact':'Mostrador de préstamos'},
]
PROCEDURES = [
    {'id':'estudios','name':'Constancia de estudios','fee':120,'days':2,'requirements':'Verificación de inscripción por Servicios Escolares.'},
    {'id':'calificaciones','name':'Constancia de calificaciones','fee':150,'days':3,'requirements':'Validación del historial por Servicios Escolares.'},
    {'id':'credencial','name':'Reposición de credencial','fee':180,'days':3,'requirements':'Recoger con identificación; la fotografía se valida en ventanilla.'},
    {'id':'reinscripcion','name':'Reinscripción','fee':0,'days':3,'requirements':'Sin adeudos demo, documentos y validación académica aprobados.'},
]
BOOKS = [
    {'id':'algebra','title':'Álgebra para bachillerato','author':'Colección académica demo','copies':3},
    {'id':'historia','title':'Historia de México','author':'Colección académica demo','copies':2},
    {'id':'programacion','title':'Introducción a la programación','author':'Colección académica demo','copies':2},
]
ACTIVITIES = [
    {'id':'robotica','name':'Club de robótica','schedule':'Martes · 16:00–17:30','location':'Laboratorio B-102','capacity':12,'enabled':True},
    {'id':'futbol','name':'Fútbol universitario','schedule':'Miércoles · 16:00–18:00','location':'Cancha deportiva','capacity':20,'enabled':True},
    {'id':'lectura','name':'Círculo de lectura','schedule':'Viernes · 15:00–16:00','location':'Biblioteca','capacity':10,'enabled':True},
]
MODULES = ['turnos','tramites','seguimiento','reinscripcion','citas','horario','biblioteca','credencial','actividades','directorio','encuesta']
SCHEMA = [
    'CREATE TABLE IF NOT EXISTS campus_config (key TEXT PRIMARY KEY, value TEXT NOT NULL)',
    '''CREATE TABLE IF NOT EXISTS campus_records (id INTEGER PRIMARY KEY AUTOINCREMENT, folio TEXT UNIQUE NOT NULL,
       matricula TEXT NOT NULL, kind TEXT NOT NULL, item TEXT NOT NULL, status TEXT NOT NULL,
       fee REAL NOT NULL DEFAULT 0, detail TEXT NOT NULL DEFAULT "", created TEXT NOT NULL,
       request_id TEXT NOT NULL, UNIQUE(matricula, request_id))''',
    '''CREATE TABLE IF NOT EXISTS campus_history (id INTEGER PRIMARY KEY, record_id INTEGER NOT NULL,
       status TEXT NOT NULL, note TEXT NOT NULL, created TEXT NOT NULL)''',
    '''CREATE TABLE IF NOT EXISTS campus_validation (matricula TEXT PRIMARY KEY, documents INTEGER NOT NULL DEFAULT 0,
       academic INTEGER NOT NULL DEFAULT 0)''',
    '''CREATE TABLE IF NOT EXISTS campus_loans (id INTEGER PRIMARY KEY, matricula TEXT NOT NULL, book TEXT NOT NULL,
       due TEXT NOT NULL, renewed INTEGER NOT NULL DEFAULT 0, returned INTEGER NOT NULL DEFAULT 0)''',
    '''CREATE TABLE IF NOT EXISTS campus_events (id INTEGER PRIMARY KEY, session TEXT NOT NULL, module TEXT NOT NULL,
       event TEXT NOT NULL, created TEXT NOT NULL, UNIQUE(session,module,event))''',
    '''CREATE TABLE IF NOT EXISTS campus_surveys (session TEXT PRIMARY KEY, score INTEGER NOT NULL, topic TEXT NOT NULL, created TEXT NOT NULL)''',
    '''CREATE TABLE IF NOT EXISTS campus_incidents (id INTEGER PRIMARY KEY, source TEXT NOT NULL, detail TEXT NOT NULL,
       created TEXT NOT NULL, resolved INTEGER NOT NULL DEFAULT 0)''',
]


def now():
    return datetime.now(timezone.utc).isoformat()


def initialize(con):
    for statement in SCHEMA:
        con.execute(statement)
    defaults = {'departments':[{**d,'start_hour':9,'end_hour':14} for d in DEPARTMENTS],'activities':ACTIVITIES,'procedures':PROCEDURES,'disabled':[],
                'announcements':[{'title':'Tu campus, en un solo lugar','text':'Agenda una cita, consulta tus trámites y descubre actividades. Información de demostración.'}]}
    for key, value in defaults.items():
        con.execute('INSERT OR IGNORE INTO campus_config VALUES (?,?)',(key,json.dumps(value,ensure_ascii=False)))


@contextmanager
def db(write=False):
    with payments.connection() as con:
        if write:
            con.execute('BEGIN IMMEDIATE')
        yield con


def config(con, key):
    return json.loads(con.execute('SELECT value FROM campus_config WHERE key=?',(key,)).fetchone()[0])


def text(value, limit=240, required=True):
    if not isinstance(value,str) or len(value)>limit or (required and not value.strip()) or any(ord(c)<32 for c in value):
        raise ValueError('Revisa los campos: texto inválido o demasiado largo.')
    return value.strip()


def key(value):
    if not isinstance(value,str) or not re.fullmatch(r'[A-Za-z0-9_-]{16,80}',value):
        raise ValueError('Identificador de operación inválido.')
    return value


def find(items, item):
    result=next((i for i in items if i['id']==item),None)
    if result is None:
        raise ValueError('La opción seleccionada no existe.')
    return result


def paid(con, record):
    return record['fee']==0 or con.execute('SELECT 1 FROM paid_concepts WHERE matricula=? AND concept_id=?',
        (record['matricula'],100000+record['id'])).fetchone() is not None


def additional_charges(con, matricula):
    return [{'id':100000+r['id'],'nombre':find(config(con,'procedures'),r['item'])['name']+' · '+r['folio'],
             'grupo':'TRÁMITES','ciclo':'DEMO','periodo':'Solicitud','importe':r['fee'],'descuento':0,
             'restante':r['fee'],'estado':'PENDIENTE','fechaVencimiento':r['created'][:10]}
            for r in con.execute("SELECT * FROM campus_records WHERE matricula=? AND kind='procedure' AND fee>0 AND status NOT IN ('cancelado','rechazado')",(matricula,))]


def transition(con, record, status, note):
    con.execute('UPDATE campus_records SET status=? WHERE id=?',(status,record['id']))
    con.execute('INSERT INTO campus_history(record_id,status,note,created) VALUES (?,?,?,?)',(record['id'],status,note,now()))


def own(con, matricula, folio):
    r=con.execute('SELECT * FROM campus_records WHERE folio=? AND matricula=?',(text(folio,40),matricula)).fetchone()
    if r is None:
        raise LookupError('No se encontró el folio en tu cuenta.')
    return r


def serialize(con, row):
    r=dict(row)
    r['paid']=paid(con,r)
    r['history']=[dict(h) for h in con.execute('SELECT status,note,created FROM campus_history WHERE record_id=? ORDER BY id',(r['id'],))]
    if r['kind']=='turn':
        r['ahead']=con.execute("SELECT count(*) FROM campus_records WHERE kind='turn' AND item=? AND status='espera' AND id<? AND date(created,'localtime')=?",(r['item'],r['id'],date.today().isoformat())).fetchone()[0]
    return r


def slots(con, department):
    department_config=find(config(con,'departments'),department)
    occupied={r[0] for r in con.execute("SELECT detail FROM campus_records WHERE kind='appointment' AND item=? AND status='reservado'",(department,))}
    values=[]
    for offset in range(1,15):
        day=date.today()+timedelta(days=offset)
        if day.weekday()<5:
            for hour in [f'{h:02d}:00' for h in range(department_config.get('start_hour',9),department_config.get('end_hour',14))]:
                slot=day.isoformat()+'T'+hour
                if slot not in occupied:
                    values.append(slot)
    return values


def expire_turns(con):
    for old in con.execute("SELECT * FROM campus_records WHERE kind='turn' AND status IN ('espera','llamado') AND date(created,'localtime')<?",(date.today().isoformat(),)).fetchall():
        transition(con,old,'completado','Turno expirado al finalizar el día.')


def public():
    with db(True) as con:
        expire_turns(con)
        return {'demo':True,'departments':config(con,'departments'),'announcements':config(con,'announcements'),
                'disabled':config(con,'disabled'),'procedures':config(con,'procedures'),
                'called':[{'folio':r['folio'],'department':r['item']} for r in con.execute("SELECT folio,item FROM campus_records WHERE kind='turn' AND status='llamado' AND date(created,'localtime')=?",(date.today().isoformat(),))]}


def state(matricula, concepts):
    with db(True) as con:
        expire_turns(con)
        # Un préstamo ficticio inicial por alumno; nunca se vuelve a crear después de su devolución.
        con.execute('INSERT OR IGNORE INTO campus_validation(matricula) VALUES (?)',(matricula,))
        seed='loan_seed_'+matricula
        if not con.execute('SELECT 1 FROM campus_config WHERE key=?',(seed,)).fetchone():
            con.execute('INSERT INTO campus_loans(matricula,book,due) VALUES (?,?,?)',(matricula,'algebra',(date.today()+timedelta(days=7)).isoformat()))
            con.execute('INSERT INTO campus_config VALUES (?,?)',(seed,'true'))
        records=[serialize(con,r) for r in con.execute('SELECT * FROM campus_records WHERE matricula=? ORDER BY id DESC',(matricula,))]
        loans=[dict(r) for r in con.execute('SELECT * FROM campus_loans WHERE matricula=? AND returned=0',(matricula,))]
        books=[]
        for book in BOOKS:
            used=con.execute('SELECT count(*) FROM campus_loans WHERE book=? AND returned=0',(book['id'],)).fetchone()[0]
            reserved=con.execute("SELECT count(*) FROM campus_records WHERE kind='book' AND item=? AND status='reservado'",(book['id'],)).fetchone()[0]
            books.append({**book,'available':max(0,book['copies']-used-reserved)})
        activities=[]
        for activity in config(con,'activities'):
            used=con.execute("SELECT count(*) FROM campus_records WHERE kind='activity' AND item=? AND status='inscrito'",(activity['id'],)).fetchone()[0]
            activities.append({**activity,'available':max(0,activity['capacity']-used)})
        validations=dict(con.execute('SELECT documents,academic FROM campus_validation WHERE matricula=?',(matricula,)).fetchone())
        balance=payments.total(payments._pending(con,matricula,concepts))
        return {'demo':True,'records':records,'books':books,'loans':loans,'activities':activities,
                'slots':{d['id']:slots(con,d['id']) for d in config(con,'departments')},
                'checklist':{**validations,'payments':balance==0,'balance':balance},
                'schedule':[
                    {'day':'Lunes','time':'08:00–09:30','subject':'Matemáticas','room':'A-201','location':'Edificio A · segundo piso'},
                    {'day':'Martes','time':'09:00–10:30','subject':'Comunicación','room':'A-105','location':'Edificio A · primer piso'},
                    {'day':'Miércoles','time':'10:00–11:30','subject':'Ciencias','room':'B-102','location':'Edificio B · laboratorio'},
                    {'day':'Jueves','time':'08:00–09:30','subject':'Historia','room':'A-201','location':'Edificio A · segundo piso'},
                    {'day':'Viernes','time':'11:00–12:30','subject':'Tecnología','room':'B-102','location':'Edificio B · laboratorio'},
                ]}


def action(matricula, data, concepts):
    action_name=data.get('action')
    with db(True) as con:
        expire_turns(con)
        if action_name=='cancel':
            r=own(con,matricula,data.get('folio'))
            allowed={'procedure':['recibido'],'appointment':['reservado'],'turn':['espera'],'book':['reservado'],'activity':['inscrito']}
            if r['status']=='cancelado':
                return serialize(con,r)
            if r['status'] not in allowed.get(r['kind'],[]) or (r['fee']>0 and paid(con,r)):
                raise ValueError('Este servicio ya está en proceso o pagado. Solicita ayuda en ventanilla.')
            transition(con,r,'cancelado','Cancelado por el alumno. Sin cobro ni devolución real.')
            return serialize(con,own(con,matricula,r['folio']))
        if action_name=='renew':
            if 'biblioteca' in config(con,'disabled'):
                raise ValueError('La biblioteca está temporalmente fuera de atención.')
            loan=con.execute('SELECT * FROM campus_loans WHERE id=? AND matricula=? AND returned=0',(data.get('id'),matricula)).fetchone()
            if not loan:
                raise LookupError('No se encontró el préstamo.')
            if loan['renewed'] or loan['due']<date.today().isoformat():
                raise ValueError('Solo se permite una renovación demo antes del vencimiento.')
            if con.execute("SELECT 1 FROM campus_records WHERE kind='book' AND item=? AND status='reservado'",(loan['book'],)).fetchone():
                raise ValueError('El libro tiene reservas; acude a biblioteca.')
            due=(date.fromisoformat(loan['due'])+timedelta(days=7)).isoformat()
            con.execute('UPDATE campus_loans SET due=?,renewed=1 WHERE id=?',(due,loan['id']))
            return {'message':'Préstamo renovado hasta '+due}
        kinds={'procedure':'tramites','appointment':'citas','turn':'turnos','book':'biblioteca','activity':'actividades'}
        if action_name not in kinds:
            raise ValueError('Acción desconocida.')
        item=text(data.get('item'),60);detail=text(data.get('detail',''),240,False);operation=key(data.get('request_id'))
        previous=con.execute('SELECT * FROM campus_records WHERE matricula=? AND request_id=?',(matricula,operation)).fetchone()
        if previous:
            if (previous['kind'],previous['item'],previous['detail'])!=(action_name,item,detail):
                raise ValueError('El identificador ya corresponde a otra operación.')
            return serialize(con,previous)
        disabled=config(con,'disabled')
        module='credencial' if action_name=='procedure' and item=='credencial' else 'reinscripcion' if action_name=='procedure' and item=='reinscripcion' else kinds[action_name]
        if module in disabled:
            raise ValueError('Servicio temporalmente fuera de atención. Consulta el directorio.')
        active=con.execute("SELECT * FROM campus_records WHERE matricula=? AND kind=? AND item=? AND status NOT IN ('cancelado','rechazado','completado','entregado')",(matricula,action_name,item)).fetchone()
        if active:
            raise ValueError('Ya tienes una solicitud activa para este servicio: '+active['folio'])
        fee=0
        if action_name=='procedure':
            procedure=find(config(con,'procedures'),item);fee=procedure['fee'];status='recibido'
            if item=='reinscripcion':
                v=con.execute('SELECT * FROM campus_validation WHERE matricula=?',(matricula,)).fetchone()
                if not v or not v['documents'] or not v['academic'] or payments._pending(con,matricula,concepts):
                    raise ValueError('Completa las tres validaciones antes de solicitar la reinscripción.')
        elif action_name in ('appointment','turn'):
            find(config(con,'departments'),item)
            status='reservado' if action_name=='appointment' else 'espera'
            if action_name=='appointment' and detail not in slots(con,item):
                raise ValueError('Ese horario ya no está disponible. Elige otro.')
            if action_name=='turn':
                # Solo un turno activo por persona.
                if con.execute("SELECT 1 FROM campus_records WHERE kind='turn' AND matricula=? AND status IN ('espera','llamado')",(matricula,)).fetchone():
                    raise ValueError('Primero termina o cancela tu turno actual.')
        elif action_name=='book':
            book=find(BOOKS,item);status='reservado'
            used=con.execute('SELECT count(*) FROM campus_loans WHERE book=? AND returned=0',(item,)).fetchone()[0]
            reserved=con.execute("SELECT count(*) FROM campus_records WHERE kind='book' AND item=? AND status='reservado'",(item,)).fetchone()[0]
            if used+reserved>=book['copies']:
                raise ValueError('Ya no hay ejemplares disponibles.')
        else:
            activity=find(config(con,'activities'),item);status='inscrito'
            used=con.execute("SELECT count(*) FROM campus_records WHERE kind='activity' AND item=? AND status='inscrito'",(item,)).fetchone()[0]
            if not activity['enabled'] or used>=activity['capacity']:
                raise ValueError('La actividad está cerrada o sin lugares.')
        folio='JS-'+{'procedure':'TR','appointment':'CT','turn':'TU','book':'LB','activity':'AC'}[action_name]+'-'+secrets.token_hex(4).upper()
        cursor=con.execute('INSERT INTO campus_records(folio,matricula,kind,item,status,fee,detail,created,request_id) VALUES (?,?,?,?,?,?,?,?,?)',(folio,matricula,action_name,item,status,fee,detail,now(),operation))
        record=con.execute('SELECT * FROM campus_records WHERE id=?',(cursor.lastrowid,)).fetchone()
        transition(con,record,status,'Registro de demostración creado en el kiosco.')
        return serialize(con,record)


def incident(source, detail):
    with db(True) as con:
        con.execute('INSERT INTO campus_incidents(source,detail,created) VALUES (?,?,?)',(source,detail[:240],now()))


def event(data, survey=False):
    session=key(data.get('session'))
    with db(True) as con:
        if survey:
            if 'encuesta' in config(con,'disabled'):
                raise ValueError('La encuesta está temporalmente fuera de atención.')
            score=data.get('score');topic=data.get('topic')
            if type(score) is not int or not 1<=score<=5 or topic not in ('facilidad','rapidez','atencion'):
                raise ValueError('Selecciona una calificación y un motivo.')
            con.execute('INSERT OR IGNORE INTO campus_surveys VALUES (?,?,?,?)',(session,score,topic,now()))
        else:
            module=data.get('module');event_name=data.get('event')
            if module not in MODULES+['charges','history','billing','parking','system'] or event_name not in ('open','complete','abandon','api_offline'):
                raise ValueError('Evento inválido.')
            con.execute('INSERT OR IGNORE INTO campus_events(session,module,event,created) VALUES (?,?,?,?)',(session,module,event_name,now()))
    return {'ok':True}


def password_hash(password, salt=None):
    salt=salt or secrets.token_hex(16)
    digest=hashlib.pbkdf2_hmac('sha256',password.encode(),salt.encode(),600000).hex()
    return salt+':'+digest


def verify_admin(password):
    stored=os.environ.get('ADMIN_PASSWORD_HASH','')
    if not stored or not isinstance(password,str) or len(password)>256 or ':' not in stored:
        return False
    return hmac.compare_digest(password_hash(password,stored.split(':')[0]),stored)


def admin_state():
    with db() as con:
        import mail_delivery
        mail_delivery.initialize(con)
        metrics=[dict(r) for r in con.execute('SELECT module,event,count(*) AS total FROM campus_events GROUP BY module,event')]
        hours=[dict(r) for r in con.execute("SELECT substr(created,12,2) AS hour,count(*) AS total FROM campus_events WHERE event='open' GROUP BY hour ORDER BY hour")]
        surveys=dict(con.execute('SELECT count(*) AS total,round(avg(score),1) AS average FROM campus_surveys').fetchone())
        deliveries=[dict(r) for r in con.execute("SELECT request_id,status,masked_recipient,updated_at FROM email_deliveries WHERE status IN ('failed','unknown','sending') ORDER BY updated_at DESC LIMIT 50")]
        return {'demo':True,'records':[serialize(con,r) for r in con.execute('SELECT * FROM campus_records ORDER BY id DESC LIMIT 300')],
                'loans':[dict(r) for r in con.execute('SELECT * FROM campus_loans WHERE returned=0')],
                'validations':[dict(r) for r in con.execute('SELECT * FROM campus_validation')],
                'config':{k:config(con,k) for k in ('departments','activities','procedures','disabled','announcements')},
                'metrics':metrics,'hours':hours,'surveys':surveys,'deliveries':deliveries,
                'incidents':[dict(r) for r in con.execute('SELECT * FROM campus_incidents ORDER BY id DESC LIMIT 50')],
                'email_available':mail_delivery.capabilities()['email_available']}


def admin_action(data, concepts):
    with db(True) as con:
        action_name=data.get('action')
        if action_name=='transition':
            r=con.execute('SELECT * FROM campus_records WHERE folio=?',(text(data.get('folio'),40),)).fetchone()
            if r is None: raise LookupError('Folio no encontrado.')
            status=data.get('status');note=text(data.get('note','Actualizado por administración demo.'),240)
            if r['status']==status: return {'ok':True}
            transitions={
                'procedure':{'recibido':['revision','rechazado'],'revision':['listo','rechazado'],'listo':['entregado']},
                'appointment':{'reservado':['completado','cancelado']},
                'turn':{'espera':['llamado','cancelado'],'llamado':['completado']},
                'book':{'reservado':['entregado','cancelado']},
                'activity':{'inscrito':['completado','cancelado']},
            }
            if status not in transitions.get(r['kind'],{}).get(r['status'],[]):
                raise ValueError('El estado cambió. Actualiza antes de continuar.')
            if r['kind']=='procedure' and status in ('revision','listo') and not paid(con,r):
                raise ValueError('El trámite tiene un concepto pendiente de pago demo.')
            if r['kind']=='procedure' and r['item']=='reinscripcion' and status=='listo':
                v=con.execute('SELECT * FROM campus_validation WHERE matricula=?',(r['matricula'],)).fetchone()
                if not v or not v['documents'] or not v['academic'] or payments._pending(con,r['matricula'],concepts):
                    raise ValueError('La reinscripción ya no cumple las validaciones.')
            if r['kind']=='turn' and status=='llamado':
                first=con.execute("SELECT id FROM campus_records WHERE kind='turn' AND item=? AND status='espera' AND date(created,'localtime')=? ORDER BY id LIMIT 1",(r['item'],date.today().isoformat())).fetchone()
                if not first or first['id']!=r['id']:
                    raise ValueError('Llama primero al turno más antiguo de hoy.')
                if con.execute("SELECT 1 FROM campus_records WHERE kind='turn' AND item=? AND status='llamado' AND date(created,'localtime')=?",(r['item'],date.today().isoformat())).fetchone():
                    raise ValueError('Cierra el turno que está en atención.')
            if r['kind']=='book' and status=='entregado':
                con.execute('INSERT INTO campus_loans(matricula,book,due) VALUES (?,?,?)',(r['matricula'],r['item'],(date.today()+timedelta(days=7)).isoformat()))
            transition(con,r,status,note)
        elif action_name=='return_book':
            cursor=con.execute('UPDATE campus_loans SET returned=1 WHERE id=?',(data.get('id'),))
            if not cursor.rowcount: raise LookupError('Préstamo no encontrado.')
        elif action_name=='validate':
            matricula=text(data.get('matricula'),20)
            if type(data.get('documents')) is not bool or type(data.get('academic')) is not bool:
                raise ValueError('Validaciones inválidas.')
            con.execute('INSERT INTO campus_validation VALUES (?,?,?) ON CONFLICT(matricula) DO UPDATE SET documents=excluded.documents,academic=excluded.academic',(matricula,int(data['documents']),int(data['academic'])))
        elif action_name=='resolve':
            con.execute('UPDATE campus_incidents SET resolved=1 WHERE id=?',(data.get('id'),))
        elif action_name=='config':
            section=data.get('section');value=data.get('value')
            if section=='announcements':
                if not isinstance(value,list) or len(value)>5 or any(not isinstance(v,dict) for v in value): raise ValueError('Máximo cinco avisos válidos.')
                value=[{'title':text(v.get('title'),80),'text':text(v.get('text'),240)} for v in value if isinstance(v,dict)]
            elif section=='disabled':
                if not isinstance(value,list) or any(v not in MODULES for v in value): raise ValueError('Servicios inválidos.')
            elif section=='departments':
                if not isinstance(value,list) or any(not isinstance(v,dict) for v in value) or {v.get('id') for v in value}!={v['id'] for v in DEPARTMENTS} or len(value)!=len(DEPARTMENTS): raise ValueError('Directorio inválido.')
                for v in value:
                    if type(v.get('start_hour')) is not int or type(v.get('end_hour')) is not int or not 7<=v['start_hour']<v['end_hour']<=20: raise ValueError('Las citas deben estar entre 07:00 y 20:00, en bloques de una hora.')
                value=[{'id':v['id'],'start_hour':v['start_hour'],'end_hour':v['end_hour'],**{k:text(v.get(k),160) for k in ('name','location','hours','requirements','contact')}} for v in value]
            elif section=='procedures':
                if not isinstance(value,list) or any(not isinstance(v,dict) for v in value) or len(value)!=len(PROCEDURES) or {v.get('id') for v in value}!={v['id'] for v in PROCEDURES}: raise ValueError('Trámites inválidos.')
                for v in value:
                    if type(v.get('fee')) not in (int,float) or not 0<=v['fee']<=10000 or type(v.get('days')) is not int or not 1<=v['days']<=30: raise ValueError('Costo o plazo inválido.')
                    if v['id']=='reinscripcion' and v['fee']!=0: raise ValueError('La solicitud de reinscripción demo no agrega otro cargo.')
                value=[{'id':v['id'],'fee':round(v['fee'],2),'days':v['days'],'name':text(v.get('name'),80),'requirements':text(v.get('requirements'),240)} for v in value]
            elif section=='activities':
                if not isinstance(value,list) or any(not isinstance(v,dict) for v in value) or len(value)!=len(ACTIVITIES) or {v.get('id') for v in value}!={v['id'] for v in ACTIVITIES}: raise ValueError('Actividades inválidas.')
                for v in value:
                    if type(v.get('capacity')) is not int or not 1<=v['capacity']<=100 or type(v.get('enabled')) is not bool: raise ValueError('Cupo inválido (1 a 100).')
                    occupied=con.execute("SELECT count(*) FROM campus_records WHERE kind='activity' AND item=? AND status='inscrito'",(v['id'],)).fetchone()[0]
                    if v['capacity']<occupied: raise ValueError('El cupo no puede ser menor a las inscripciones actuales.')
                value=[{'id':v['id'],'capacity':v['capacity'],'enabled':v['enabled'],**{k:text(v.get(k),120) for k in ('name','schedule','location')}} for v in value]
            else: raise ValueError('Configuración inválida.')
            con.execute('UPDATE campus_config SET value=? WHERE key=?',(json.dumps(value,ensure_ascii=False),section))
        else:
            raise ValueError('Acción administrativa desconocida.')
    return {'ok':True}


def document(matricula, folio, student):
    with db() as con:
        r=own(con,matricula,folio)
        if r['kind']!='procedure' or r['item'] not in ('estudios','calificaciones') or r['status'] not in ('listo','entregado') or not paid(con,r):
            raise ValueError('La constancia todavía no está autorizada para envío.')
        return {'folio':r['folio'],'title':find(config(con,'procedures'),r['item'])['name'],'kind':r['item'],'student':student,'issued_at':r['created']}


def turn_ticket(matricula, folio):
    with db() as con:
        r=own(con,matricula,folio)
        if r['kind']!='turn' or r['status'] not in ('espera','llamado'):
            raise ValueError('Solo puedes imprimir un turno activo de tu cuenta.')
        department=find(config(con,'departments'),r['item'])
        lines=['JUSTO SIERRA','TURNO DE ATENCION DEMO',r['folio'],department['name'],department['location'],
               datetime.fromisoformat(r['created']).astimezone().strftime('%d/%m/%Y %H:%M'),
               'CONSERVA ESTE FOLIO','ESPERA TU LLAMADO EN EL AREA','SERVICIO DE PRUEBA']
        return b'\x1b@\x1bt\x02\x1ba\x01'+('\n'.join(lines)+'\n\n\n\n').encode('cp850','replace')+b'\x1dV\x01'
