#!/usr/bin/env python3
"""API mock Justo Sierra: solo localhost, datos ficticios, sin pagos reales."""
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json, os, secrets, threading, time, urllib.parse
import parking

HOST=os.getenv('MOCK_HOST','127.0.0.1'); PORT=int(os.getenv('MOCK_PORT','8787'))
TOKENS={}; LOCK=threading.Lock(); TTL=3600
STUDENTS={
 '202210':{'id':'6019','matricula':'202210','nombre':'ALUMNO DEMOSTRACIÓN','nivel':'Preparatoria','grado':'Sexto','grupo':'A','ciclo':'2026/2027','email':'alumno.demo@ejemplo.invalid'},
 '202211':{'id':'6020','matricula':'202211','nombre':'ALUMNA PRUEBA','nivel':'Licenciatura','grado':'Tercero','grupo':'B','ciclo':'2026/2027','email':'alumna.demo@ejemplo.invalid'}
}
CONCEPTS=[
 {'id':36,'nombre':'COLEGIATURA REINSCRIPCIÓN PRIMARIA SEXTO','grupo':'COLEGIATURA','ciclo':'2026/2027','periodo':'03','importe':3045,'descuento':420,'restante':2625,'estado':'pendiente','fechaVencimiento':'2026-11-30'},
 {'id':45,'nombre':'TRANSPORTE BASES SOBRE RUTA COMPLETO','grupo':'TRANSPORTE','ciclo':'2026/2027','periodo':'03','importe':2900,'descuento':0,'restante':2900,'estado':'pendiente','fechaVencimiento':'2026-11-01'},
 {'id':55,'nombre':'SERVICIOS COMPLEMENTARIOS EXTRA CLASE ARTÍSTICA','grupo':'SERVICIOS COMPLEMENTARIOS','ciclo':'2026/2027','periodo':'06','importe':940,'descuento':0,'restante':940,'estado':'anticipado','fechaVencimiento':'2027-02-01'},
 {'id':56,'nombre':'SERVICIOS COMPLEMENTARIOS MÚSICA CLUB DE BANDA SINFÓNICA','grupo':'SERVICIOS COMPLEMENTARIOS','ciclo':'2026/2027','periodo':'08','importe':940,'descuento':0,'restante':940,'estado':'anticipado','fechaVencimiento':'2027-04-01'}
]
class Handler(BaseHTTPRequestHandler):
 def respond(self, code, body):
  b=json.dumps(body,ensure_ascii=False).encode();self.send_response(code);self.send_header('Content-Type','application/json; charset=utf-8');self.send_header('Cache-Control','no-store');self.send_header('Access-Control-Allow-Origin','*');self.send_header('Access-Control-Allow-Headers','Authorization,Content-Type');self.send_header('Access-Control-Allow-Methods','GET,POST,OPTIONS');self.send_header('Content-Length',str(len(b)));self.end_headers();self.wfile.write(b)
 def do_OPTIONS(self):
  self.send_response(204);self.send_header('Access-Control-Allow-Origin','*');self.send_header('Access-Control-Allow-Headers','Authorization,Content-Type');self.send_header('Access-Control-Allow-Methods','GET,POST,OPTIONS');self.end_headers()
 def body(self):
  try:
   n=int(self.headers.get('Content-Length','0'))
   if n>8192:raise ValueError('Body demasiado grande')
   return json.loads(self.rfile.read(n) or b'{}')
  except (ValueError,json.JSONDecodeError):return None
 def auth(self):
  value=self.headers.get('Authorization','');token=value[7:] if value.startswith('Bearer ') else ''
  with LOCK:
   record=TOKENS.get(token)
  return record if record and record['exp']>time.time() else None
 def do_GET(self):
  path=urllib.parse.urlparse(self.path).path
  if path=='/api/health':return self.respond(200,{'status':'ok','modo':'DEMO','integracionReal':False})
  if path=='/api/parking/printer':return self.respond(200,{'printer':parking.printer_name(),'demo':True})
  session=self.auth()
  if not session:return self.respond(401,{'error':'Token ausente o expirado'})
  if path=='/api/me':return self.respond(200,{'estudiante':STUDENTS[session['matricula']]})
  if path=='/api/charges':return self.respond(200,{'matricula':session['matricula'],'conceptos':CONCEPTS,'moneda':'MXN','demo':True})
  return self.respond(404,{'error':'Ruta no encontrada'})
 def do_POST(self):
  path=urllib.parse.urlparse(self.path).path;data=self.body()
  if data is None:return self.respond(400,{'error':'JSON inválido'})
  if path=='/api/auth/login':
   matricula=str(data.get('matricula','')).strip(); pin=str(data.get('pin','')).strip()
   if matricula not in STUDENTS or pin!='1234':return self.respond(401,{'error':'Matrícula o PIN demo incorrectos'})
   token=secrets.token_urlsafe(32)
   with LOCK:TOKENS[token]={'matricula':matricula,'exp':time.time()+TTL}
   return self.respond(200,{'access_token':token,'token_type':'Bearer','expires_in':TTL,'estudiante':STUDENTS[matricula],'demo':True})
  if path=='/api/parking/issue':
   ticket=parking.create_ticket()
   try:ticket['print']=parking.print_ticket(ticket);ticket['printed']=True
   except Exception as e:ticket['printed']=False;ticket['print_error']=str(e)
   return self.respond(200,{'ticket':ticket,'demo':True})
  if path=='/api/parking/reprint':
   try:
    quote=parking.quote_ticket(data.get('code',''))
    ticket={'code':quote['code'],'issued_at':quote['issued_at']}
    return self.respond(200,{'printed':True,'print':parking.print_ticket(ticket)})
   except (ValueError,RuntimeError) as e:return self.respond(400,{'error':str(e)})
  if path=='/api/parking/quote':
   try:return self.respond(200,parking.quote_ticket(data.get('code','')))
   except ValueError as e:return self.respond(404,{'error':str(e)})
  session=self.auth()
  if not session:return self.respond(401,{'error':'Sesión no válida'})
  if path=='/api/auth/logout':
   token=self.headers.get('Authorization','')[7:]
   with LOCK:TOKENS.pop(token,None)
   return self.respond(200,{'ok':True})
  if path=='/api/payments/quote':
   ids=data.get('concept_ids',[])
   if not isinstance(ids,list) or len(ids)<1 or any(not isinstance(i,int) for i in ids):return self.respond(400,{'error':'Selecciona conceptos válidos'})
   selected=[c for c in CONCEPTS if c['id'] in ids]
   if len(selected)!=len(set(ids)):return self.respond(400,{'error':'Concepto desconocido'})
   return self.respond(200,{'conceptos':selected,'total':round(sum(c['restante'] for c in selected),2),'moneda':'MXN','modo':'DEMO','cobroReal':False,'mensaje':'Cotización de ejemplo. No se generó cargo, liga ni transacción.'})
  return self.respond(404,{'error':'Ruta no encontrada'})
 def log_message(self, fmt,*args):print('[demo]',fmt%args)
if __name__=='__main__':
 print(f'API DEMO http://{HOST}:{PORT}/api/health | matrículas 202210 / 202211; PIN 1234')
 ThreadingHTTPServer((HOST,PORT),Handler).serve_forever()
