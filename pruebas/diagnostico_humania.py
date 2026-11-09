"""Diagnóstico de solo lectura para la entrega HumanIA.

Uso (desde raíz): python pruebas/diagnostico_humania.py
No crea usuarios, no borra archivos, no modifica SQLite.
"""
import hashlib
import importlib.util
import socket
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CRITICOS = [
    "api/main.py",
    "api/exportacion_aprobada.py",
    "api/flujo_conversacional.py",
    "humania/agent.py",
    "humania/servicios/contratos.py",
    "frontend/package.json",
    "frontend/src/App.tsx",
    "frontend/src/studio.css",
    "plantillas/indeterminado_v1.docx",
    "plantillas/indeterminado_v2.docx",
]
MODULOS = ["fastapi", "docx", "docxtpl", "pypdf", "reportlab",
           "httpx", "PIL", "google.adk", "litellm"]
PORTS = [
    (5173, "Frontend Vite"),
    (8001, "Backend FastAPI"),
    (8000, "Agente ADK"),
    (11434, "Ollama"),
]


def resultado(estado: str, mensaje: str) -> None:
    print(f"[{estado}] {mensaje}")


def main() -> int:
    print("=== HumanIA — Diagnóstico local de solo lectura ===")
    print("Proyecto:", ROOT)
    print("Python:", sys.version.split()[0])
    fallos = 0

    for archivo in CRITICOS:
        if (ROOT / archivo).is_file():
            resultado("OK", archivo)
        else:
            resultado("ERROR", f"Falta {archivo}")
            fallos += 1

    for modulo in MODULOS:
        try:
            existe = importlib.util.find_spec(modulo) is not None
        except (ModuleNotFoundError, ValueError):
            existe = False
        resultado("OK" if existe else "ERROR", "Módulo Python: " + modulo)
        if not existe:
            fallos += 1

    if sys.platform == "win32":
        try:
            import pythoncom  # noqa: F401
            resultado("OK", "COM Windows disponible para docx2pdf")
        except ImportError:
            resultado("ERROR", "Falta pywin32")
            fallos += 1
    else:
        resultado("AVISO", "PDF desde Word requiere Windows + Microsoft Word")

    try:
        sys.path.insert(0, str(ROOT))
        from humania.servicios.contratos import PLANTILLAS_AUTORIZADAS
        from humania.seguridad.plantillas import verificar_huella_plantilla_aprobada
        for version, (_, huella) in PLANTILLAS_AUTORIZADAS.items():
            valido = verificar_huella_plantilla_aprobada(huella)
            resultado("OK" if valido else "ERROR", f"Plantilla {version} SHA-256")
            fallos += int(not valido)
    except Exception as exc:
        resultado("ERROR", f"No se pudo verificar la plantilla: {type(exc).__name__}")
        fallos += 1

    for port, nombre in PORTS:
        with socket.socket() as sock:
            sock.settimeout(0.6)
            activo = sock.connect_ex(("127.0.0.1", port)) == 0
        resultado("OK" if activo else "AVISO", f"{nombre} (127.0.0.1:{port})")

    print()
    if fallos:
        resultado("PENDIENTE", f"{fallos} problemas locales detectados")
        return 1
    resultado("OK", "Estructura, módulos y huellas estáticas verificadas")
    print("Las pruebas funcionales y la lectura de imágenes se verifican aparte.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
