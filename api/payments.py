"""Cobros y documentos ficticios. No hay pasarela, timbrado ni conexión al SAT."""
from contextlib import contextmanager
from datetime import datetime, timezone
from decimal import Decimal
import json
import os
from pathlib import Path
import re
import secrets
import sqlite3
import textwrap
import xml.etree.ElementTree as ET

DB = Path(os.environ.get('PAYMENTS_DB', str(Path(__file__).parent / 'payments-demo.sqlite3')))
DEMO_NOTICE = 'DEMO / SIN VALIDEZ FISCAL / SIN COBRO REAL'
CODE_RE = re.compile(r'JS-PAY-[A-F0-9]{32}')


@contextmanager
def connection():
    con = sqlite3.connect(DB, timeout=10)
    con.row_factory = sqlite3.Row
    try:
        con.executescript('''
            CREATE TABLE IF NOT EXISTS payments (
                code TEXT PRIMARY KEY, matricula TEXT NOT NULL,
                request_id TEXT NOT NULL, payload TEXT NOT NULL,
                UNIQUE(matricula, request_id));
            CREATE TABLE IF NOT EXISTS paid_concepts (
                matricula TEXT NOT NULL, concept_id INTEGER NOT NULL,
                payment_code TEXT NOT NULL, PRIMARY KEY(matricula, concept_id));
            CREATE TABLE IF NOT EXISTS invoices (
                payment_code TEXT PRIMARY KEY, payload TEXT NOT NULL);
        ''')
        yield con
        con.commit()
    except Exception:
        con.rollback()
        raise
    finally:
        con.close()


def ordered(concepts):
    return sorted(concepts, key=lambda c: (c['fechaVencimiento'], c['id']))


def _pending(con, matricula, concepts):
    paid = {r['concept_id'] for r in con.execute('SELECT concept_id FROM paid_concepts WHERE matricula=?', (matricula,))}
    return [c for c in ordered(concepts) if c['id'] not in paid]


def pending(matricula, concepts):
    with connection() as con:
        return _pending(con, matricula, concepts)


def select_in_order(available, ids):
    if not isinstance(ids, list) or not ids or any(type(i) is not int for i in ids):
        raise ValueError('Selecciona al menos un concepto válido.')
    if ids != [c['id'] for c in available[:len(ids)]]:
        raise ValueError('Agrega los conceptos en orden de vencimiento. Actualiza los cargos si ya fueron pagados en la demo.')
    return available[:len(ids)]


def total(concepts):
    return float(sum((Decimal(str(c['restante'])) for c in concepts), Decimal('0')).quantize(Decimal('.01')))


def simulate(student, concepts, ids, request_id):
    if not isinstance(request_id, str) or not re.fullmatch(r'[A-Za-z0-9_-]{16,80}', request_id):
        raise ValueError('Identificador de operación inválido.')
    matricula = student['matricula']
    with connection() as con:
        con.execute('BEGIN IMMEDIATE')
        previous = con.execute('SELECT payload FROM payments WHERE matricula=? AND request_id=?', (matricula, request_id)).fetchone()
        if previous:
            payment = json.loads(previous['payload'])
            if ids != [c['id'] for c in payment['conceptos']]:
                raise ValueError('Este identificador ya corresponde a otra selección.')
            return payment, True
        selected = select_in_order(_pending(con, matricula, concepts), ids)
        code = 'JS-PAY-' + secrets.token_hex(16).upper()
        payment = {
            'code': code, 'issued_at': datetime.now(timezone.utc).isoformat(),
            'estudiante': student, 'conceptos': selected, 'total': total(selected),
            'moneda': 'MXN', 'status': 'PAGADO_DEMO', 'demo': True,
            'cobroReal': False, 'notice': DEMO_NOTICE, 'qr_payload': code,
        }
        con.execute('INSERT INTO payments VALUES (?,?,?,?)', (code, matricula, request_id, json.dumps(payment, ensure_ascii=False)))
        con.executemany('INSERT INTO paid_concepts VALUES (?,?,?)', [(matricula, c['id'], code) for c in selected])
        return payment, False


def normalize_code(code):
    if not isinstance(code, str) or not CODE_RE.fullmatch(code.strip().upper()):
        raise ValueError('Escanea un comprobante de pago demo válido (JS-PAY-…).')
    return code.strip().upper()


def lookup(code):
    code = normalize_code(code)
    with connection() as con:
        row = con.execute('SELECT payload FROM payments WHERE code=?', (code,)).fetchone()
        if not row:
            raise LookupError('No se encontró el comprobante en este kiosco.')
        invoice = con.execute('SELECT payload FROM invoices WHERE payment_code=?', (code,)).fetchone()
        return {'payment': json.loads(row['payload']), 'invoice': json.loads(invoice['payload']) if invoice else None}


def invoice_xml(invoice):
    # Estructura ilustrativa: deliberadamente SIN certificado, sello ni TimbreFiscalDigital.
    ns = 'http://www.sat.gob.mx/cfd/4'
    ET.register_namespace('cfdi', ns)
    root = ET.Element(f'{{{ns}}}Comprobante', {
        'Version': '4.0', 'Serie': 'DEMO', 'Folio': invoice['folio'],
        'Fecha': invoice['issued_at'], 'Moneda': 'MXN',
        'SubTotal': f"{invoice['total']:.2f}", 'Total': f"{invoice['total']:.2f}",
        'TipoDeComprobante': 'I',
    })
    ET.SubElement(root, f'{{{ns}}}Emisor', {'Rfc': 'XAXX010101000', 'Nombre': 'EMISOR FICTICIO DE PRUEBAS'})
    ET.SubElement(root, f'{{{ns}}}Receptor', {'Rfc': 'XAXX010101000', 'Nombre': 'PUBLICO GENERAL DE PRUEBA'})
    details = ET.SubElement(root, f'{{{ns}}}Conceptos')
    for c in invoice['conceptos']:
        ET.SubElement(details, f'{{{ns}}}Concepto', {
            'Descripcion': c['nombre'], 'Cantidad': '1',
            'ValorUnitario': f"{c['restante']:.2f}", 'Importe': f"{c['restante']:.2f}",
        })
    addenda = ET.SubElement(root, f'{{{ns}}}Addenda')
    ET.SubElement(addenda, 'DocumentoDePrueba', {'Aviso': DEMO_NOTICE, 'Timbrado': 'NO', 'CertificadoSAT': 'NO'})
    return ET.tostring(root, encoding='unicode', xml_declaration=True)


def create_invoice(code):
    code = normalize_code(code)
    with connection() as con:
        con.execute('BEGIN IMMEDIATE')
        previous = con.execute('SELECT payload FROM invoices WHERE payment_code=?', (code,)).fetchone()
        if previous:
            return json.loads(previous['payload']), True
        row = con.execute('SELECT payload FROM payments WHERE code=?', (code,)).fetchone()
        if not row:
            raise LookupError('No se encontró el comprobante en este kiosco.')
        payment = json.loads(row['payload'])
        invoice = {
            'folio': 'DEMO-' + secrets.token_hex(6).upper(), 'payment_code': code,
            'issued_at': datetime.now(timezone.utc).isoformat(),
            'conceptos': payment['conceptos'], 'total': payment['total'],
            'moneda': 'MXN', 'demo': True, 'timbrado': False,
            'rfc_emisor': 'XAXX010101000', 'rfc_receptor': 'XAXX010101000',
            'emisor': 'EMISOR FICTICIO DE PRUEBAS', 'receptor': 'PUBLICO GENERAL DE PRUEBA',
            'notice': DEMO_NOTICE, 'qr_payload': code,
        }
        invoice['xml'] = invoice_xml(invoice)
        con.execute('INSERT INTO invoices VALUES (?,?)', (code, json.dumps(invoice, ensure_ascii=False)))
        return invoice, False


def receipt(document, invoice=False):
    from parking import qr_command
    title = 'FACTURA DE PRUEBA' if invoice else 'COMPROBANTE DE PAGO DEMO'
    lines = ['UNIVERSIDAD JUSTO SIERRA', title, 'DEMO / SIN VALIDEZ FISCAL', 'SIN COBRO REAL', '=' * 32,
             datetime.fromisoformat(document['issued_at']).astimezone().strftime('%d/%m/%Y %H:%M:%S')]
    if invoice:
        lines += [document['folio'], 'CFDI 4.0 ILUSTRATIVO / NO TIMBRADO', 'EMISOR Y RECEPTOR FICTICIOS', 'RFC: XAXX010101000']
    else:
        lines += ['MATRICULA DEMO: ' + document['estudiante']['matricula']]
    for c in document['conceptos']:
        lines += textwrap.wrap(c['nombre'], 32) + [f"${c['restante']:,.2f} MXN", '-' * 32]
    lines += [f"TOTAL DEMO: ${document['total']:,.2f} MXN", '', 'ESCANEA EN ESTE KIOSCO', 'PARA FACTURAR / REIMPRIMIR', '']
    text = '\n'.join(lines).encode('cp850', 'replace')
    code = document['qr_payload']
    logo = (Path(__file__).parent / 'assets' / 'justo_sierra_logo_escpos.bin').read_bytes()
    return b'\x1b@\x1bt\x02\x1ba\x01\n\n' + logo + b'\n\n' + text + b'\n' + qr_command(code) + b'\n' + code.encode('ascii') + b'\nSIN VALIDEZ FISCAL\n\n\n\n\x1dV\x01'
