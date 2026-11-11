"""Gateway de consulta SIPAA. No registra pagos ni persiste datos de alumnos.

Contrato: manual de integración del 10/11/2026, pp. 2-3, 5 y 7-11.
El ejemplo específico de pago único sigue pendiente de confirmar.
"""
from collections import deque
from dataclasses import dataclass, field
from contextlib import contextmanager
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
import json
import http.client
import os
import re
import socket
import ssl
import threading
import time
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


class IntegrationError(Exception):
    def __init__(self, message, status=502, code='sipaa_response'):
        super().__init__(message)
        self.status, self.code = status, code


@dataclass(frozen=True)
class Config:
    base_url: str = 'https://sipaa-erp.justo-sierra.net/api'
    timezone: str = 'America/Mexico_City'
    ignore_expires_at: bool = False

    @classmethod
    def from_env(cls):
        return cls(os.getenv('SIPAA_BASE_URL', cls.base_url).rstrip('/'),
                   os.getenv('SIPAA_TIMEZONE', 'America/Mexico_City'),
                   os.getenv('SIPAA_IGNORE_EXPIRES_AT', '0').strip() == '1')

    def validate(self):
        try:
            parsed = urlsplit(self.base_url)
            parsed.port
        except ValueError:
            raise IntegrationError('Configura una URL HTTPS válida para SIPAA.', 503, 'sipaa_config') from None
        if (parsed.scheme != 'https' or not parsed.hostname or parsed.username or
                parsed.password or parsed.query or parsed.fragment):
            raise IntegrationError('Configura una URL HTTPS válida para SIPAA.', 503, 'sipaa_config')
        try:
            ZoneInfo(self.timezone)
        except (ZoneInfoNotFoundError, ValueError):
            raise IntegrationError('Revisa SIPAA_TIMEZONE e instala las dependencias de la API.', 503, 'sipaa_config') from None


class UpstreamStatus(Exception):
    def __init__(self, status):
        self.status = status


def post_json(url, payload, token=None):
    parsed = urlsplit(url)
    connection = http.client.HTTPSConnection(parsed.hostname, parsed.port or 443,
                                            timeout=4, context=ssl.create_default_context())
    held_socket = []
    expired = threading.Event()
    def abort():
        expired.set()
        sock = held_socket[0] if held_socket else connection.sock
        if sock is not None:
            try:
                sock.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
            sock.close()
    deadline = threading.Timer(4, abort)
    deadline.daemon = True
    headers = {'Content-Type': 'application/json', 'Accept': 'application/json'}
    if token:
        headers['Authorization'] = 'Bearer ' + token
    deadline.start()
    try:
        connection.connect()
        held_socket.append(connection.sock)
        if expired.is_set():
            raise TimeoutError()
        connection.request('POST', parsed.path, body=json.dumps(payload).encode('utf-8'), headers=headers)
        with connection.getresponse() as response:
            # No redirects: las credenciales y el Bearer permanecen en el origen configurado.
            if not 200 <= response.status < 300:
                raise UpstreamStatus(response.status)
            if response.headers.get_content_type() != 'application/json':
                raise IntegrationError('SIPAA no devolvió JSON. Solicita revisar la integración.')
            raw = response.read(2 * 1024 * 1024 + 1)
            if expired.is_set():
                raise TimeoutError()
            if len(raw) > 2 * 1024 * 1024:
                raise IntegrationError('La respuesta de SIPAA supera el límite permitido.')
            data = json.loads(raw, parse_float=Decimal)
            if not isinstance(data, dict):
                raise ValueError()
            return data
    except (http.client.HTTPException, TimeoutError, OSError):
        raise IntegrationError('No se pudo consultar SIPAA. Reintenta en unos momentos.', 503, 'sipaa_unavailable') from None
    except (ValueError, UnicodeError):
        raise IntegrationError('SIPAA devolvió un formato que no se pudo interpretar.') from None
    finally:
        deadline.cancel()
        connection.close()


def tuition(value):
    if not isinstance(value, str) or not re.fullmatch(r'[0-9]{1,20}', value.strip()):
        raise ValueError('Escribe una matrícula válida de hasta 20 dígitos.')
    return value.strip()  # Conserva ceros iniciales; nunca convertir a número.


def text_value(value, limit=160):
    if not isinstance(value, str) or not value.strip() or len(value) > limit:
        raise IntegrationError('SIPAA devolvió un concepto incompleto. Solicita revisar sus datos.')
    return value.strip()


def identifier(value):
    if isinstance(value, bool) or not isinstance(value, (int, str)):
        raise IntegrationError('SIPAA devolvió un identificador inválido.')
    value = str(value)
    if not re.fullmatch(r'[A-Za-z0-9_-]{1,64}', value):
        raise IntegrationError('SIPAA devolvió un identificador inválido.')
    return value


def amount(value):
    try:
        if isinstance(value, bool) or not isinstance(value, (str, int, float, Decimal)):
            raise ValueError()
        if not re.fullmatch(r'(?:[0-9]+(?:\.[0-9]{1,2})?|\.[0-9]{1,2})', str(value)):
            raise ValueError()
        result = Decimal(str(value))
        if not result.is_finite() or not 0 <= result <= Decimal('999999999.99'):
            raise ValueError()
        return float(result)
    except (ValueError, InvalidOperation):
        raise IntegrationError('SIPAA devolvió un importe inválido. No se calculará un saldo sustituto.') from None


def normalize(data, matricula):
    if data.get('success') is not True:
        raise IntegrationError('SIPAA no confirmó la consulta. Verifica la matrícula o solicita ayuda.')
    if data.get('tuition') != matricula or data.get('currency') != 'MXN':
        raise IntegrationError('La matrícula o moneda de la respuesta SIPAA no coincide con la consulta.')
    groups = data.get('concepts')
    if groups == []:
        groups = {}
    if not isinstance(groups, dict):
        raise IntegrationError('SIPAA devolvió una estructura de conceptos desconocida.')
    result, seen = [], set()
    for cycle_key, entries in groups.items():
        cycle_key = identifier(cycle_key)
        if not isinstance(entries, list):
            raise IntegrationError('SIPAA devolvió un ciclo con formato desconocido.')
        for parent in entries:
            if not isinstance(parent, dict):
                raise IntegrationError('SIPAA devolvió un concepto con formato desconocido.')
            contract = parent.get('type') == 'contract'
            if ('payments' in parent) != contract:
                raise IntegrationError('Revisa el formato de contratos y pagos únicos de SIPAA.')
            parent_id = identifier(parent.get('id'))
            leaves = parent.get('payments') if contract else [parent]
            if not isinstance(leaves, list):
                raise IntegrationError('SIPAA devolvió un contrato sin su lista de mensualidades.')
            for leaf in leaves:
                if not isinstance(leaf, dict):
                    raise IntegrationError('SIPAA devolvió una mensualidad con formato desconocido.')
                source_id = identifier(leaf.get('id'))
                key = f'sipaa:{cycle_key}:contract:{parent_id}:{source_id}' if contract else f'sipaa:{cycle_key}:single:{source_id}'
                if key in seen:
                    raise IntegrationError('SIPAA devolvió conceptos duplicados. Solicita revisar el adeudo.')
                seen.add(key)
                # pending_amount es el saldo del ejemplo real; restante es el contrato normalizado.
                balance = amount(leaf.get('pending_amount', leaf.get('restante')))
                if balance == 0:
                    continue
                due = leaf.get('date_expiration', leaf.get('fechaVencimiento'))
                try:
                    if not isinstance(due, str) or not re.fullmatch(r'\d{4}-\d{2}-\d{2}', due):
                        raise ValueError()
                    date.fromisoformat(due)
                except ValueError:
                    raise IntegrationError('Un adeudo de SIPAA no tiene un vencimiento válido. Solicita revisión.') from None
                def inherited(english, spanish):
                    return leaf.get(english, leaf.get(spanish, parent.get(english, parent.get(spanish))))
                concept = {
                    'id': key, 'sourceId': source_id,
                    'nombre': text_value(inherited('name', 'nombre')),
                    'grupo': text_value(inherited('group', 'grupo')),
                    'ciclo': text_value(inherited('cycle', 'ciclo')),
                    'periodo': str(leaf.get('periodDesc', leaf.get('period', leaf.get('periodo', 'Único'))))[:80],
                    'restante': balance, 'fechaVencimiento': due,
                    'estado': str(leaf.get('dayStateDesc', leaf.get('estado', 'Pendiente')))[:80],
                    'tipo': 'mensualidad' if contract else 'unico',
                }
                result.append(concept)
                if len(result) > 2000:
                    raise IntegrationError('SIPAA devolvió demasiados conceptos para una consulta.')
    def order(c):
        sid = c['sourceId']
        return c['fechaVencimiento'], (0, int(sid)) if sid.isdigit() else (1, sid), c['id']
    result.sort(key=order)
    for index, concept in enumerate(result):
        concept['orden'] = index
    return {'matricula': matricula, 'conceptos': result, 'moneda': 'MXN', 'demo': False,
            'origen': 'SIPAA', 'consultaEn': str(data.get('dateConsult', ''))[:80], 'cobroHabilitado': False}


@dataclass(frozen=True)
class Access:
    token: str = field(repr=False)
    expires_in: int = 600
    name: str = field(default='', repr=False)
    expires_at: float = 0


class Gateway:
    SYSTEM_CODE = 'AP'

    def __init__(self, config=None, transport=post_json):
        self.config = config or Config.from_env()
        self.transport = transport
        self._lock = threading.Lock()
        self._slots = threading.BoundedSemaphore(2)
        self._calls = deque()

    def ready(self):
        try:
            self.config.validate()
            return True
        except IntegrationError:
            return False

    @contextmanager
    def admitted(self):
        self.config.validate()
        if not self._slots.acquire(blocking=False):
            raise IntegrationError('Hay otra consulta en curso. Reintenta en unos segundos.', 429, 'sipaa_busy')
        try:
            with self._lock:
                now = time.monotonic()
                while self._calls and now - self._calls[0] >= 60:
                    self._calls.popleft()
                if len(self._calls) >= 30:
                    raise IntegrationError('Se alcanzó el límite de consultas. Espera un minuto.', 429, 'sipaa_rate_limit')
                self._calls.append(now)
            yield
        finally:
            self._slots.release()

    def authenticate(self, matricula, password):
        matricula = tuition(matricula)
        if not isinstance(password, str) or not password or len(password) > 256:
            raise ValueError('Escribe tu contraseña (hasta 256 caracteres).')
        with self.admitted():
            try:
                data = self.transport(self.config.base_url + '/loginApp/direct', {
                    'username': matricula, 'password': password, 'system_code': self.SYSTEM_CODE})
            except UpstreamStatus as exc:
                if exc.status in (400, 401, 403, 422):
                    raise IntegrationError('SIPAA no autorizó el acceso. Revisa tu matrícula, contraseña y acceso al kiosco.', 401, 'sipaa_login') from None
                self.status_error(exc.status)
        if data.get('success') is False:
            raise IntegrationError('SIPAA no autorizó el acceso. Revisa tus datos.', 401, 'sipaa_login')
        # Estructura de la imagen de la p. 3. No seguir redirect_url desde el kiosco.
        details = data.get('data')
        if data.get('success') is not True or not isinstance(details, dict):
            raise IntegrationError('LoginApi devolvió una respuesta de acceso desconocida.')
        value = details.get('token')
        if (not isinstance(value, str) or not re.fullmatch(r'[\x21-\x7e]{1,8192}', value)
                or details.get('token_type') != 'Bearer'):
            raise IntegrationError('LoginApi no devolvió un token Bearer válido en data.token.', 502, 'sipaa_token_format')
        if self.config.ignore_expires_at:
            # Excepción temporal, activada solo en la configuración del servidor.
            # Este límite es LOCAL; no modifica el token ni la fecha de SIPAA.
            # server.py aún exige que KardexStudent acepte el token antes de abrir sesión.
            lifetime = 600
            expires = datetime.now(timezone.utc) + timedelta(seconds=lifetime)
        else:
            try:
                expires = datetime.fromisoformat(details['expires_at'].replace('Z', '+00:00'))
                if expires.tzinfo is None:
                    expires = expires.replace(tzinfo=ZoneInfo(self.config.timezone))
                lifetime = min(600, int((expires - datetime.now(timezone.utc)).total_seconds()))
            except (KeyError, TypeError, ValueError, AttributeError):
                raise IntegrationError('LoginApi no devolvió una fecha de vencimiento válida.') from None
            if lifetime <= 0:
                raise IntegrationError('SIPAA devolvió una sesión vencida. Vuelve a ingresar.', 401, 'sipaa_expired')
        user = details.get('user')
        name = user.get('name') if isinstance(user, dict) else ''
        name = name.strip()[:160] if isinstance(name, str) else ''
        return Access(value, lifetime, name, expires.timestamp())

    @staticmethod
    def status_error(status):
        if status in (401, 403):
            # No se guarda la contraseña ni se intenta renovar con otra identidad.
            raise IntegrationError('Tu sesión en SIPAA venció o no tiene acceso. Vuelve a ingresar.', 401, 'sipaa_expired')
        if status == 404:
            raise IntegrationError('SIPAA no encontró información para esa matrícula. Verifícala o solicita ayuda.', 404, 'sipaa_not_found')
        if status == 429:
            raise IntegrationError('SIPAA está recibiendo muchas consultas. Reintenta en un minuto.', 429, 'sipaa_rate_limit')
        raise IntegrationError('SIPAA no pudo completar la consulta. Reintenta más tarde.', 503, 'sipaa_unavailable')

    def consult(self, matricula, token):
        matricula = tuition(matricula)
        if not isinstance(token, str) or not re.fullmatch(r'[\x21-\x7e]{1,8192}', token):
            raise IntegrationError('Tu sesión en SIPAA venció. Vuelve a ingresar.', 401, 'sipaa_expired')
        with self.admitted():
            try:
                data = self.transport(self.config.base_url + '/kardexStudent', {'tuition': matricula}, token)
            except UpstreamStatus as exc:
                self.status_error(exc.status)
            return normalize(data, matricula)


def quote(gateway, matricula, token, ids):
    snapshot = gateway.consult(matricula, token)
    available = snapshot['conceptos']
    if not isinstance(ids, list) or not ids or any(not isinstance(i, str) for i in ids):
        raise ValueError('Selecciona al menos un concepto válido.')
    if ids != [c['id'] for c in available[:len(ids)]]:
        raise IntegrationError('Los adeudos cambiaron. Actualiza la lista y vuelve a seleccionar en orden de vencimiento.', 409, 'sipaa_changed')
    selected = available[:len(ids)]
    total = float(sum((Decimal(str(c['restante'])) for c in selected), Decimal('0')))
    return {'conceptos': selected, 'total': total, 'moneda': 'MXN', 'modo': 'SIPAA',
            'consultaEn': snapshot['consultaEn'], 'cobroReal': False, 'cobroHabilitado': False}
