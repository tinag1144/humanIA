"""Instalacion segura: agrega descarga para revision sin sobrescribir archivos enteros.

Ejecutar desde la raiz de HumanIA: python instalar_revision_borrador.py
"""
from datetime import datetime
from pathlib import Path
import shutil

raiz = Path(__file__).resolve().parent
main = raiz / "api" / "main.py"
app = raiz / "frontend" / "src" / "App.tsx"
endpoint = raiz / "api" / "descarga_borrador.py"

for ruta in (main, app, endpoint):
    if not ruta.is_file():
        raise SystemExit(f"ERROR: falta {ruta}. No se realizaron cambios.")

origen_main = main.read_text(encoding="utf-8")
origen_app = app.read_text(encoding="utf-8")

registro = "app.include_router(descarga_revision_router)"
importacion = "from api.descarga_borrador import router as descarga_revision_router"

ancla = '<Status value={d.decision || \'pendiente_confirmacion\'}/></div>)}'
boton = (
    '<button className="btn secondary" '
    'title="Descargar DOCX sin aprobar" '
    'disabled={!!action} '
    'onClick={() => { if (!token) return; '
    'void runAction(`revision-${d.id}`, '
    '() => download(`/api/borradores/${d.id}/revision-docx`, token), '
    '"Borrador descargado para revisión. La aprobación sigue pendiente."); '
    '}}><ArrowDownToLine size={16}/> Revisar DOCX</button>'
)

if registro in origen_main:
    nuevo_main = origen_main
else:
    if "app.include_router(flujo_router)" not in origen_main:
        raise SystemExit("ERROR: no se encontró el router del flujo. No se realizaron cambios.")
    nuevo_main = origen_main.rstrip() + "\n\n# Descarga autenticada previa a la aprobacion.\n" + importacion + "\n" + registro + "\n"

if "`/api/borradores/${d.id}/revision-docx`" in origen_app:
    nuevo_app = origen_app
else:
    if origen_app.count(ancla) != 1:
        raise SystemExit("ERROR: el diseño de App.tsx cambió. No se realizaron cambios.")
    nuevo_app = origen_app.replace(ancla, boton + ancla, 1)

if nuevo_main == origen_main and nuevo_app == origen_app:
    print("La descarga para revisión ya estaba instalada. No se modificó nada.")
    raise SystemExit(0)

marca = datetime.now().strftime("%Y%m%d_%H%M%S")
for ruta, original, nuevo in (
    (main, origen_main, nuevo_main),
    (app, origen_app, nuevo_app),
):
    if original == nuevo:
        continue
    copia = ruta.with_name(ruta.name + f".antes_revision_{marca}.bak")
    shutil.copy2(ruta, copia)
    print("Respaldo:", copia)
    ruta.write_text(nuevo, encoding="utf-8")
    print("Actualizado:", ruta)

print("LISTO: botón 'Revisar DOCX' y ruta /api/borradores/{id}/revision-docx")
print("No se modificaron SQLite, plantillas, documentos ni aprobaciones.")
