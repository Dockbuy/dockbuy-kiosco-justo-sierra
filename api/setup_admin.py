"""Ejecutar en la computadora del operador: python api/setup_admin.py."""
from getpass import getpass
from pathlib import Path
from campus import password_hash

if __name__=='__main__':
    password=getpass('Nueva contraseña administrativa (mínimo 12 caracteres): ')
    if len(password)<12 or password!=getpass('Confirmar contraseña: '):
        raise SystemExit('No coincide o tiene menos de 12 caracteres. No se cambió nada.')
    path=Path(__file__).parent/'.env'
    lines=path.read_text(encoding='utf-8').splitlines() if path.exists() else []
    lines=[line for line in lines if not line.startswith('ADMIN_PASSWORD_HASH=')]
    lines.append('ADMIN_PASSWORD_HASH='+password_hash(password))
    path.write_text('\n'.join(lines)+'\n',encoding='utf-8')
    print('Contraseña guardada como hash en api/.env (ignorado por Git). Reinicia la API y abre /admin.')
