"""Servidor exclusivo de pruebas: base temporal e impresión simulada, sin hardware."""
import pathlib
import sys
import tempfile

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / 'api'))
import parking
import payments
import server
import mail_delivery


class TestHandler(server.Handler):
    def do_POST(self):
        if self.path == '/__test/reset':
            with payments.connection() as con:
                con.execute('DELETE FROM invoices')
                con.execute('DELETE FROM paid_concepts')
                con.execute('DELETE FROM payments')
                mail_delivery.initialize(con)
                con.execute('DELETE FROM email_deliveries')
            server.TOKENS.clear()
            return self.respond(200, {'ok':True})
        return super().do_POST()


if __name__ == '__main__':
    with tempfile.TemporaryDirectory() as directory:
        parking.DB = pathlib.Path(directory) / 'parking.sqlite3'
        payments.DB = pathlib.Path(directory) / 'payments.sqlite3'
        parking.print_payload = lambda payload: {'printer':'E2E MOCK','job':'Sin impresión física'}
        # Nunca se establece conexión SMTP: solo se construyen los adjuntos en memoria.
        mail_delivery.config = lambda: mail_delivery.Config('test.invalid',587,'starttls','kiosco@example.invalid','','')
        mail_delivery.smtp_send = lambda message,settings: 'accepted'
        server.ThreadingHTTPServer(('127.0.0.1',8878),TestHandler).serve_forever()
