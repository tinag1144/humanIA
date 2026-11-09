
# Importamos Path para trabajar con archivos y rutas.
from pathlib import Path

# Importamos las bibliotecas para leer PDF y DOCX.
from pypdf import PdfReader
from docx import Document


# Esta función extrae texto de un archivo PDF.
def leer_pdf(ruta: str) -> str:

    # Abrimos el archivo PDF.
    lector = PdfReader(ruta)

    # Creamos una lista para guardar el texto.
    paginas = []

    # Recorremos las páginas del documento.
    for pagina in lector.pages:

        # Extraemos el texto de cada página.
        texto = pagina.extract_text() or ""

        # Guardamos el texto extraído.
        paginas.append(texto)

    # Unimos el contenido de todas las páginas.
    return "\n".join(paginas)


# Esta función extrae texto de un documento Word.
def leer_docx(ruta: str) -> str:

    # Abrimos el documento.
    documento = Document(ruta)

    # Lista donde guardaremos el contenido.
    partes = []

    # Recorremos los párrafos.
    for parrafo in documento.paragraphs:

        if parrafo.text.strip():
            partes.append(parrafo.text)

    # También leemos las tablas.
    for tabla in documento.tables:
        for fila in tabla.rows:

            celdas = [
                celda.text for celda in fila.cells
            ]

            partes.append(" | ".join(celdas))

    # Unimos todo el contenido.
    return "\n".join(partes)


# Función principal para seleccionar el lector.
def leer_documento(ruta: str) -> dict:

    # Convertimos la ruta en un objeto Path.
    archivo = Path(ruta)

    # Comprobamos que exista.
    if not archivo.is_file():
        return {
            "estado": "error",
            "mensaje": "El archivo no existe."
        }

    # Obtenemos la extensión.
    extension = archivo.suffix.lower()

    # Intentamos leer el archivo.
    try:

        if extension == ".pdf":
            texto = leer_pdf(str(archivo))

        elif extension == ".docx":
            texto = leer_docx(str(archivo))

        else:
            return {
                "estado": "error",
                "mensaje": "Formato no admitido."
            }

        # Comprobamos si extrajimos contenido.
        if not texto.strip():
            return {
                "estado": "sin_texto",
                "mensaje": "No se encontró texto extraíble."
            }

        # Devolvemos el contenido.
        return {
            "estado": "correcto",
            "archivo": archivo.name,
            "texto": texto
        }

    # Capturamos posibles errores.
    except Exception:
        return {
            "estado": "error",
            "mensaje": "No se pudo procesar el documento."
        }
