"""Integra la interfaz en el FastAPI existente sin reemplazar api/main.py."""
from pathlib import Path

raiz = Path(__file__).resolve().parent
main = raiz / 'api' / 'main.py'
bridge = raiz / 'api' / 'frontend_bridge.py'
frontend = raiz / 'frontend' / 'package.json'

if not all(p.is_file() for p in [main, bridge, frontend]):
    raise SystemExit('ERROR: extraé el ZIP en la raíz de humanIA (junto a api/, humania/ y README.md).')
contenido = main.read_text(encoding='utf-8')
marca = 'app.include_router(frontend_router)'
if marca in contenido:
    print('La interfaz ya está integrada. No se modificó api/main.py.')
else:
    if 'app = FastAPI(' not in contenido:
        raise SystemExit('ERROR: no se encontró la aplicación FastAPI. No se modificó nada.')
    respaldo = raiz / 'api' / 'main.py.antes_frontend.bak'
    if not respaldo.exists():
        respaldo.write_text(contenido, encoding='utf-8')
    agregado = (
        '\n\n# Rutas adicionales para la interfaz web HumanIA.\n'
        'from api.frontend_bridge import router as frontend_router\n'
        'app.include_router(frontend_router)\n'
    )
    main.write_text(contenido.rstrip() + '\n' + agregado, encoding='utf-8')
    print('Interfaz integrada con api/main.py. Respaldo guardado en api/main.py.antes_frontend.bak')
print('SIGUIENTE: uv pip install httpx')
print('DESPUES: levantar FastAPI (8001), ADK api_server (8000) y Vite (5173).')
