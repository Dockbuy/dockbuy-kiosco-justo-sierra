"""Límites del servidor local. No sustituyen la autenticación institucional."""
from collections import deque
from http.server import ThreadingHTTPServer as StandardServer
import json
import os
import socket
import threading
import time


class RequestError(RuntimeError):
    def __init__(self, message, status=400, retry_after=None):
        super().__init__(message)
        self.status = status
        self.retry_after = retry_after


DEFAULT_ORIGINS = frozenset({
    'http://127.0.0.1:1420', 'http://localhost:1420',
    'tauri://localhost', 'http://tauri.localhost', 'https://tauri.localhost',
})


class ThreadingHTTPServer(StandardServer):
    max_workers = 16
    read_deadline = 10
    requests_per_minute = 240
    request_queue_size = 16

    def __init__(self, address, handler):
        if address[0] not in ('127.0.0.1', 'localhost'):
            raise ValueError('La API demo solo admite MOCK_HOST=127.0.0.1 o localhost.')
        self.allowed_origins = DEFAULT_ORIGINS | frozenset(
            value.strip() for value in os.getenv('API_ALLOWED_ORIGINS', '').split(',') if value.strip())
        if {'*', 'null'} & self.allowed_origins:
            raise ValueError('API_ALLOWED_ORIGINS requiere orígenes exactos, sin * ni null.')
        self.worker_slots = threading.BoundedSemaphore(self.max_workers)
        self.admission_lock = threading.Lock()
        self.request_times = deque()
        super().__init__(address, handler)

    def process_request(self, request, client_address):
        if not self.worker_slots.acquire(blocking=False):
            # No crear un hilo ni esperar a que otro usuario libere su conexión.
            payload = json.dumps({'error': 'API ocupada. Reintenta en un segundo.'}).encode()
            try:
                request.settimeout(0.1)
                request.sendall(b'HTTP/1.1 503 Service Unavailable\r\nConnection: close\r\n'
                                b'Content-Type: application/json\r\nRetry-After: 1\r\nContent-Length: '
                                + str(len(payload)).encode() + b'\r\n\r\n' + payload)
            except OSError:
                pass
            finally:
                self.shutdown_request(request)
            return
        try:
            request.settimeout(self.read_deadline)
            super().process_request(request, client_address)
        except BaseException:
            self.worker_slots.release()
            raise

    def process_request_thread(self, request, client_address):
        try:
            super().process_request_thread(request, client_address)
        finally:
            self.worker_slots.release()

    def admit_request(self):
        now = time.monotonic()
        with self.admission_lock:
            while self.request_times and self.request_times[0] <= now - 60:
                self.request_times.popleft()
            if len(self.request_times) >= self.requests_per_minute:
                raise RequestError('Demasiadas solicitudes. Espera un minuto.', 429, 60)
            self.request_times.append(now)


class GuardedHTTPHandler:
    """El plazo absoluto cubre línea inicial, cabeceras y cuerpo, incluso por goteo."""
    def handle_one_request(self):
        self.read_expired = threading.Event()
        def expire():
            self.read_expired.set()
            try:
                self.connection.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
        self.read_timer = threading.Timer(self.server.read_deadline, expire)
        self.read_timer.daemon = True
        self.read_timer.start()
        try:
            super().handle_one_request()
        except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
            # Cierre del cliente o del plazo de lectura; el slot se libera igual.
            pass
        finally:
            self.read_timer.cancel()

    def finish_reading(self):
        self.read_timer.cancel()
        if self.read_expired.is_set():
            raise RequestError('Se agotó el tiempo para recibir la solicitud.', 408)
        # El plazo de lectura no debe interrumpir un envío SMTP o una impresión.
        self.connection.settimeout(5)

    def parse_request(self):
        if not super().parse_request():
            return False
        self.close_connection = True
        try:
            hosts = self.headers.get_all('Host', [])
            port = self.server.server_port
            allowed_hosts = {f'127.0.0.1:{port}', f'localhost:{port}'}
            if port == 80:
                allowed_hosts.update(('127.0.0.1', 'localhost'))
            if len(hosts) != 1 or hosts[0].lower() not in allowed_hosts:
                raise RequestError('Host no permitido.', 403)
            if not self.path.startswith('/') or self.path.startswith('//'):
                raise RequestError('Se requiere una ruta local.')
            origins = self.headers.get_all('Origin', [])
            if len(origins) > 1 or (origins and origins[0] not in self.server.allowed_origins):
                raise RequestError('Origen no permitido.', 403)
            lengths = self.headers.get_all('Content-Length', [])
            if self.headers.get_all('Transfer-Encoding') or len(lengths) > 1:
                raise RequestError('Formato de longitud no permitido.')
            length = lengths[0] if lengths else '0'
            if not length.isascii() or not length.isdecimal() or len(length) > 5:
                raise RequestError('Longitud inválida.')
            self.body_length = int(length)
            if self.body_length > 8192:
                raise RequestError('La solicitud supera 8 KB.', 413)
            if self.command == 'POST':
                types = self.headers.get_all('Content-Type', [])
                if len(types) != 1 or types[0].split(';', 1)[0].strip().lower() != 'application/json':
                    raise RequestError('Se requiere Content-Type: application/json.', 415)
            elif self.body_length:
                raise RequestError('Este método no admite cuerpo.')
            self.server.admit_request()
            if self.command != 'POST':
                self.finish_reading()
            return True
        except RequestError as exc:
            self.read_timer.cancel()
            self.respond(exc.status, {'error': str(exc), 'retry_after': exc.retry_after})
            return False
