"""Diagnóstico opcional de solo lectura. No guarda contraseñas, tokens ni adeudos."""
from getpass import getpass
from pathlib import Path
from dotenv import load_dotenv
from sipaa import Gateway, IntegrationError, tuition


if __name__ == '__main__':
    load_dotenv(Path(__file__).parent / '.env')
    try:
        print('Prueba de LoginApi y KardexStudent. No registra ningún pago.')
        matricula = tuition(input('Tu matrícula: '))
        password = getpass('Tu contraseña (no se muestra): ')
        gateway = Gateway()
        try:
            access = gateway.authenticate(matricula, password)
        finally:
            password = None
        result = gateway.consult(matricula, access.token)
        print(f"Consulta correcta: {len(result['conceptos'])} conceptos; moneda {result['moneda']}.")
        print('No se guardaron datos ni se muestran tokens o importes.')
    except (IntegrationError, ValueError) as exc:
        raise SystemExit(str(exc)) from None
    except (EOFError, KeyboardInterrupt):
        raise SystemExit('Prueba interrumpida.') from None
