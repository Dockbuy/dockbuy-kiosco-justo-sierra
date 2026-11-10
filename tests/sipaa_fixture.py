"""Datos ficticios: contrato con campos de p. 7; pago único propuesto, sin confirmar."""
from copy import deepcopy
from datetime import datetime, timedelta, timezone


def login_response(token='test-upstream-token'):
    return {'success': True, 'message': 'Autenticación exitosa', 'data': {
        'token': token, 'token_type': 'Bearer',
        'expires_at': (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat(),
        'user': {'id': 42, 'name': 'USUARIO DE PRUEBA', 'email': 'test@example.invalid',
                 'type_user': '1', 'internal_key': '000042'},
        'system': {'id': 1, 'code': 'AP', 'name': 'KIOSCO'},
        'redirect_url': '/dashboard', 'identifier_type': 'tuition',
    }}


def kardex(matricula='000042'):
    return deepcopy({
        'success': True, 'currency': 'MXN', 'tuition': matricula,
        'dateConsult': '11:10:54 2026-11-10', 'message': 'Consulta de prueba',
        'concepts': {
            '129': [{
                'id': 9, 'name': 'COLEGIATURA DE PRUEBA', 'group': 'COLEGIATURA',
                'cycle': '2026/2027', 'idCycle': 129, 'type': 'contract',
                'payments': [
                    {'id': 256, 'period': '04', 'periodDesc': 'DICIEMBRE',
                     'date_expiration': '2026-12-31', 'total_amount': 6510,
                     'scholarship_amount': '1953.00', 'discount': 800,
                     'pending_amount': 5710, 'dayStateDesc': 'Anticipado'},
                    {'id': 255, 'period': '03', 'periodDesc': 'NOVIEMBRE',
                     'date_expiration': '2026-11-30', 'pending_amount': '0.10'},
                ],
            }],
            '128': [{'id': 10, 'name': 'BIBLIOTECA DE PRUEBA', 'group': 'SERVICIOS',
                     'cycle': '2025/2026', 'type': 'single', 'period': 'ÚNICO',
                     'date_expiration': '2026-08-01', 'pending_amount': '0.20'}],
        },
    })
