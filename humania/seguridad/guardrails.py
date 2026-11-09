
"""
HumanIA - Detección de instrucciones sospechosas.

Analiza texto extraído de documentos antes de
enviarlo al agente.

IMPORTANTE:
Los patrones son una defensa complementaria.
No garantizan detectar todos los ataques.
Las autorizaciones definitivas se comprueban
en el backend, nunca mediante instrucciones del LLM.
"""

import re
import unicodedata


# Patrones aplicados sobre texto normalizado:
# sin tildes y en minúsculas.
PATRONES_SOSPECHOSOS = [
    r"\bignora\w*\b.{0,100}\binstruccion\w*",
    r"\bdesactiva\w*\b.{0,100}\bseguridad\b",
    r"\bomit\w*\b.{0,100}\bvalidacion\w*",
    r"\bsalta\w*\b.{0,100}\brestriccion\w*",
    r"\baprob\w*\b.{0,100}\bautomatic\w*",
    r"\bmodifica\w*\b.{0,100}\bclausula\w*",
    r"\brevela\w*\b.{0,100}\bprompt\b",
    r"\bactua\b.{0,40}\bcomo\b.{0,40}\badministrador\b",

    # Intentos de modificar condiciones laborales.
    r"\b(?:cambia\w*|modifica\w*|altera\w*)\b"
    r".{0,100}\b(?:salario|sueldo|remuneracion)\b",

    # Órdenes para ocultar modificaciones.
    r"\b(?:oculta\w*|esconde\w*|no\s+(?:informes|avises|menciones))\b"
    r".{0,70}\b(?:cambio|modificacion|salario|sueldo|remuneracion)\b",
]


def normalizar_texto(texto: str) -> str:
    """
    Elimina diferencias de acentuación y mayúsculas
    para facilitar la detección de patrones.

    No altera el documento original.
    """

    texto = unicodedata.normalize("NFKD", texto)

    texto = "".join(
        caracter
        for caracter in texto
        if not unicodedata.combining(caracter)
    )

    return texto.casefold()


def analizar_documento(texto: str) -> dict:
    """
    Analiza el contenido textual de un documento.

    Estados:
    - bloqueado: entrada inválida o no procesable.
    - requiere_revision: se encontró contenido sospechoso.
    - sin_alertas: no coincidió con los patrones conocidos.

    'sin_alertas' no equivale a contenido seguro.
    """

    # Validación del tipo de dato.
    if not isinstance(texto, str):
        return {
            "estado": "bloqueado",
            "mensaje": "El contenido debe ser texto."
        }

    # Documentos sin contenido.
    if not texto.strip():
        return {
            "estado": "bloqueado",
            "mensaje": "El documento está vacío."
        }

    # Límite preventivo de longitud.
    if len(texto) > 20000:
        return {
            "estado": "bloqueado",
            "mensaje": (
                "El documento supera el límite permitido."
            )
        }

    texto_normalizado = normalizar_texto(texto)

    detecciones = []

    # Buscamos las expresiones sospechosas conocidas.
    for patron in PATRONES_SOSPECHOSOS:

        coincidencia = re.search(
            patron,
            texto_normalizado,
            flags=re.IGNORECASE | re.DOTALL
        )

        if coincidencia:
            detecciones.append({
                "patron": patron,
                "fragmento": coincidencia.group(0)[:120]
            })

    if detecciones:
        return {
            "estado": "requiere_revision",
            "mensaje": (
                "Se detectaron posibles instrucciones "
                "maliciosas dentro del documento."
            ),
            "detecciones": detecciones
        }

    # No encontrar coincidencias no implica seguridad.
    return {
        "estado": "sin_alertas",
        "mensaje": (
            "No se detectaron los patrones conocidos. "
            "El documento sigue siendo contenido no confiable."
        ),
        "detecciones": []
    }
