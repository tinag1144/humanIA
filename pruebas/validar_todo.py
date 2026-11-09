"""Ejecuta comprobaciones locales de HumanIA en un solo comando.

Uso desde la raíz:
    python pruebas/validar_todo.py

No elimina bases de datos ni contratos. No crea usuarios.
Las pruebas con Ollama/Word requieren validación funcional separada.
"""
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PASOS = [
    ("Sintaxis Python", [sys.executable, "-m", "compileall", "-q", "api", "humania", "pruebas"], ROOT),
    (
        "Regresión de exportación, documentos, validaciones y RAG",
        [sys.executable, "-m", "unittest",
         "pruebas.probar_cierre_final", "pruebas.probar_rag_sin_ollama", "-v"],
        ROOT,
    ),
    ("Compilación frontend TypeScript + Vite", ["npm", "run", "build"], ROOT / "frontend"),
    ("Diagnóstico de dependencias y plantillas", [sys.executable, "pruebas/diagnostico_humania.py"], ROOT),
]


def ejecutar() -> int:
    print("HumanIA — Validación de cierre", flush=True)
    fallidos = []
    for nombre, comando, carpeta in PASOS:
        print("\n" + "=" * 60, flush=True)
        print("PRUEBA:", nombre, flush=True)
        print("=" * 60, flush=True)
        try:
            resultado = subprocess.run(
                comando, cwd=carpeta, check=False,
            )
            codigo = resultado.returncode
        except FileNotFoundError:
            codigo = 127
            print("No se encontró el comando: " + comando[0])
        if codigo:
            fallidos.append(nombre)
            print("ERROR:", nombre, flush=True)
        else:
            print("OK:", nombre, flush=True)
    print("\n" + "=" * 60, flush=True)
    if fallidos:
        print("VALIDACIÓN INCOMPLETA — etapas con errores:")
        for nombre in fallidos:
            print(" -", nombre)
        return 1
    print("COMPROBACIONES LOCALES SUPERADAS")
    print("PENDIENTE: probar descargas Word/PDF y OCR/RAG con Ollama real.")
    return 0


if __name__ == "__main__":
    raise SystemExit(ejecutar())
