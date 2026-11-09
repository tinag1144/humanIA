"""Instalador conservador: agrega un router y cambia solo la URL del chat.
No altera datos/humania.db, plantillas ni herramientas ADK.
"""
from pathlib import Path
from datetime import datetime
import shutil

raiz = Path(__file__).resolve().parent
main = raiz / 'api' / 'main.py'
front = raiz / 'frontend' / 'src' / 'App.tsx'
modulo = raiz / 'api' / 'flujo_conversacional.py'

if not all(p.is_file() for p in (main, front, modulo)):
    raise SystemExit('ERROR: ubicá estos archivos en la raíz de HumanIA; no se modificó nada.')

texto_main = main.read_text(encoding='utf-8')
texto_front = front.read_text(encoding='utf-8')
importacion = 'from api.flujo_conversacional import router as flujo_router'
registro = 'app.include_router(flujo_router)'

if registro not in texto_main and 'app.include_router(frontend_router)' not in texto_main:
    raise SystemExit('ERROR: no se encontró la integración actual del frontend. No se modificó nada.')
if "'/api/interfaz/chat'" not in texto_front and "'/api/flujo/chat'" not in texto_front:
    raise SystemExit('ERROR: no se encontró la URL de chat esperada en App.tsx. No se modificó nada.')

nuevo_main = texto_main
if registro not in nuevo_main:
    nuevo_main += '\n# Flujo contractual conversacional supervisado.\n' + importacion + '\n' + registro + '\n'
nuevo_front = texto_front.replace("'/api/interfaz/chat'", "'/api/flujo/chat'")

if nuevo_main == texto_main and nuevo_front == texto_front:
    print('Ya estaba instalado; no se cambió ningún archivo.')
    raise SystemExit(0)

marca = datetime.now().strftime('%Y%m%d_%H%M%S')
for archivo in (main, front):
    copia = archivo.with_name(archivo.name + f'.antes_flujo_{marca}.bak')
    shutil.copy2(archivo, copia)
    print('Respaldo:', copia)

main.write_text(nuevo_main, encoding='utf-8')
front.write_text(nuevo_front, encoding='utf-8')
print('INSTALADO: nuevo flujo /api/flujo/chat')
print('No se modificó la base de datos de contratos, ni sus plantillas.')
