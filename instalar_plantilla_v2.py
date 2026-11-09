"""Instalacion local de la plantilla HumanIA v2, preservando v1.

Uso desde raiz del proyecto:
    python instalar_plantilla_v2.py
    python instalar_plantilla_v2.py --activar

Para activar, RR. HH. debe autorizar antes el texto de la clausula octava.
"""
from pathlib import Path
from datetime import datetime
import hashlib
import shutil
import sys

ROOT = Path.cwd()
PAQUETE = Path(__file__).resolve().parent / "paquete_plantilla_v2"
EXPECTED_V1 = '6AE8D8481DC599F41706876DAA6EEC295399E4DFB9514791E3625F1E3D0274E8'
EXPECTED_V2 = '632127B239A1C86F2BFF3D166C5392B1AE8B00C95D1967DA272D74706CB6B7D4'


def sha(ruta):
    return hashlib.sha256(ruta.read_bytes()).hexdigest().upper()


def main():
    activar = '--activar' in sys.argv[1:]
    if any(x != '--activar' for x in sys.argv[1:]):
        sys.exit('Uso: python instalar_plantilla_v2.py [--activar]')

    original_v1 = ROOT / 'plantillas/indeterminado_v1.docx'
    if not original_v1.is_file() or sha(original_v1) != EXPECTED_V1:
        sys.exit('ERROR: la plantilla v1 no coincide con la referencia. No se hizo ningun cambio.')

    objetivo_v2 = ROOT / 'plantillas/indeterminado_v2.docx'
    origen_v2 = PAQUETE / 'plantillas/indeterminado_v2.docx'
    if sha(origen_v2) != EXPECTED_V2:
        sys.exit('ERROR: contenido v2 del paquete alterado.')

    for nombre in ('contratos.py', 'aprobaciones.py'):
        destino = ROOT / 'humania/servicios' / nombre
        if not destino.is_file():
            sys.exit(f'ERROR: no existe {destino}.')
        texto = destino.read_text(encoding='utf-8')
        if 'PLANTILLAS_AUTORIZADAS' not in texto and nombre == 'contratos.py':
            if 'PLANTILLA = RAIZ / "plantillas" / "indeterminado_v1.docx"' not in texto:
                sys.exit('ERROR: contratos.py es distinto del codigo revisado. No se modifico nada.')
        if 'PLANTILLAS_POR_HUELLA' not in texto and nombre == 'aprobaciones.py':
            if 'HUELLA_PLANTILLA_APROBADA' not in texto:
                sys.exit('ERROR: aprobaciones.py es distinto del codigo revisado. No se modifico nada.')

    if activar:
        texto = (ROOT / 'humania/servicios/contratos.py').read_text(encoding='utf-8')
        if 'PLANTILLAS_AUTORIZADAS' not in texto or not objetivo_v2.is_file():
            sys.exit('Primero instala sin --activar, y revisa la plantilla.')
        if sha(objetivo_v2) != EXPECTED_V2:
            sys.exit('ERROR: plantilla v2 alterada. No se activo.')
        print('La v2 cambia la clausula octava y requiere revision y autorizacion humana.')
        confirmacion = input('Si sos responsable autorizado y ya revisaste la clausula, escribi AUTORIZO V2: ').strip()
        if confirmacion != 'AUTORIZO V2':
            sys.exit('Activacion cancelada. La v1 sigue activa.')
        ruta = ROOT / 'humania/servicios/contratos.py'
        if 'PLANTILLA_ACTIVA = "v2"' in texto:
            print('La plantilla v2 ya estaba activa.')
            return
        if 'PLANTILLA_ACTIVA = "v1"' not in texto:
            sys.exit('No se encontro configuracion segura de plantilla.')
        respaldo = ruta.with_suffix('.py.respaldo_' + datetime.now().strftime('%Y%m%d_%H%M%S'))
        shutil.copy2(ruta, respaldo)
        ruta.write_text(texto.replace('PLANTILLA_ACTIVA = "v1"', 'PLANTILLA_ACTIVA = "v2"', 1), encoding='utf-8')
        print('v2 ACTIVADA. Reinicia FastAPI. Respaldo:', respaldo)
        return

    if objetivo_v2.exists() and sha(objetivo_v2) != EXPECTED_V2:
        sys.exit('ERROR: existe una plantilla v2 diferente. No se reemplaza.')

    backups = ROOT / 'respaldos_plantilla' / datetime.now().strftime('%Y%m%d_%H%M%S')
    backups.mkdir(parents=True, exist_ok=True)

    for nombre in ('contratos.py', 'aprobaciones.py'):
        destino = ROOT / 'humania/servicios' / nombre
        shutil.copy2(destino, backups / nombre)
        shutil.copy2(PAQUETE / 'humania/servicios' / nombre, destino)

    if not objetivo_v2.exists():
        shutil.copy2(origen_v2, objetivo_v2)

    print('INSTALACION COMPLETADA. v1 sigue activa; no se modificaron datos ni borradores.')
    print('v2 lista para revision:', objetivo_v2)
    print('Respaldo codigo:', backups)
    print('Despues de la autorizacion, ejecutar: python instalar_plantilla_v2.py --activar')


if __name__ == '__main__':
    main()
