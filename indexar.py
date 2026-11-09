
"""
HumanIA - Indexador local de documentos para RAG.

Lee documentos autorizados de la carpeta documentos,
genera embeddings con Ollama y los almacena en SQLite.

Admite .txt, .pdf y .docx.
No ejecuta instrucciones contenidas en documentos.
No modifica contratos ni aprobaciones.
"""

import hashlib
import json
import sqlite3
import urllib.error
import urllib.request

from pathlib import Path

from docx import Document
from pypdf import PdfReader


RAIZ = Path(__file__).resolve().parent
DOCUMENTOS = RAIZ / "documentos"
BASE = RAIZ / "base_vectorial" / "rag.db"

MODELO_EMBEDDINGS = "nomic-embed-text:latest"
URL_OLLAMA = "http://127.0.0.1:11434/api/embed"

EXTENSIONES = {".txt", ".pdf", ".docx"}
TAMANO_MAXIMO = 10 * 1024 * 1024
TAMANO_FRAGMENTO = 900
SOLAPAMIENTO = 120


def extraer_texto(ruta: Path) -> str:
    """Extrae texto de documentos locales."""

    if ruta.suffix.lower() == ".txt":
        return ruta.read_text(encoding="utf-8")

    if ruta.suffix.lower() == ".pdf":
        lector = PdfReader(str(ruta))
        return "\n".join(
            pagina.extract_text() or ""
            for pagina in lector.pages
        )

    if ruta.suffix.lower() == ".docx":
        documento = Document(str(ruta))

        textos = [
            parrafo.text
            for parrafo in documento.paragraphs
        ]

        for tabla in documento.tables:
            for fila in tabla.rows:
                for celda in fila.cells:
                    textos.append(celda.text)

        return "\n".join(textos)

    raise ValueError("Formato no admitido.")


def fragmentar(texto: str) -> list[str]:
    """Divide el texto en fragmentos con solapamiento."""

    texto = " ".join(texto.split())

    if not texto:
        return []

    fragmentos = []
    avance = TAMANO_FRAGMENTO - SOLAPAMIENTO

    for inicio in range(0, len(texto), avance):
        fragmento = texto[inicio:inicio + TAMANO_FRAGMENTO]

        if fragmento.strip():
            fragmentos.append(fragmento)

        if inicio + TAMANO_FRAGMENTO >= len(texto):
            break

    return fragmentos


def generar_embedding(texto: str) -> list[float]:
    """Solicita un embedding al Ollama local."""

    contenido = json.dumps({
        "model": MODELO_EMBEDDINGS,
        "input": texto,
        "truncate": False
    }).encode("utf-8")

    solicitud = urllib.request.Request(
        URL_OLLAMA,
        data=contenido,
        headers={"Content-Type": "application/json"},
        method="POST"
    )

    with urllib.request.urlopen(
        solicitud,
        timeout=120
    ) as respuesta:
        resultado = json.load(respuesta)

    vectores = resultado.get("embeddings")

    if (
        not isinstance(vectores, list)
        or len(vectores) != 1
        or not isinstance(vectores[0], list)
        or not vectores[0]
    ):
        raise ValueError("Respuesta de embeddings inválida.")

    return vectores[0]


def inicializar_base(db: sqlite3.Connection) -> None:
    """Crea la tabla de fragmentos vectoriales."""

    db.execute("""
        CREATE TABLE IF NOT EXISTS fragmentos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            documento TEXT NOT NULL,
            numero INTEGER NOT NULL,
            texto TEXT NOT NULL,
            embedding TEXT NOT NULL,
            modelo TEXT NOT NULL,
            huella_documento TEXT NOT NULL,
            UNIQUE(documento, numero)
        )
    """)


def indexar_documentos() -> None:
    """Indexa los documentos o informa un error."""

    DOCUMENTOS.mkdir(parents=True, exist_ok=True)
    BASE.parent.mkdir(parents=True, exist_ok=True)

    archivos = sorted(
        ruta for ruta in DOCUMENTOS.iterdir()
        if ruta.is_file()
        and not ruta.is_symlink()
        and ruta.suffix.lower() in EXTENSIONES
    )

    if not archivos:
        print("No hay documentos para indexar.")
        return

    documentos_indexados = []
    registros = []

    for ruta in archivos:
        if ruta.stat().st_size > TAMANO_MAXIMO:
            print("OMITIDO por tamaño:", ruta.name)
            continue

        texto = extraer_texto(ruta)
        fragmentos = fragmentar(texto)

        if not fragmentos:
            print("OMITIDO sin texto:", ruta.name)
            continue

        huella = hashlib.sha256(
            ruta.read_bytes()
        ).hexdigest()

        print("Indexando:", ruta.name)

        for numero, fragmento in enumerate(fragmentos, 1):
            vector = generar_embedding(fragmento)

            registros.append((
                ruta.name,
                numero,
                fragmento,
                json.dumps(vector),
                MODELO_EMBEDDINGS,
                huella
            ))

        documentos_indexados.append(ruta.name)

        print("Fragmentos:", len(fragmentos))

    if not registros:
        print("No se encontraron textos indexables.")
        return

    # Solo reemplazamos la colección cuando
    # todos los embeddings se generaron correctamente.
    with sqlite3.connect(BASE) as db:
        inicializar_base(db)

        db.execute("DELETE FROM fragmentos")

        db.executemany(
            """
            INSERT INTO fragmentos (
                documento,
                numero,
                texto,
                embedding,
                modelo,
                huella_documento
            )
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            registros
        )

    print("\nINDEXACION COMPLETADA")
    print("Documentos:", len(documentos_indexados))
    print("Fragmentos:", len(registros))
    print("Base:", BASE)


if __name__ == "__main__":
    try:
        indexar_documentos()

    except (
        urllib.error.URLError,
        TimeoutError
    ) as error:
        print("ERROR: no se pudo consultar Ollama.")
        print(str(error))
        raise SystemExit(1)

    except Exception as error:
        print("ERROR DE INDEXACION:", str(error))
        raise SystemExit(1)
