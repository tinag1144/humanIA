
"""
HumanIA - Control de entrada del agente.

Detecta domicilios contradictorios atribuidos a
documentos y Recursos Humanos.

El orden de las fuentes no altera el resultado.

IMPORTANTE:
Este control complementa las validaciones del backend.
No sustituye la revisión humana ni garantiza detectar
todos los intentos de prompt injection.
"""

import re
import unicodedata

from google.genai import types
from google.adk.models.llm_response import LlmResponse


# Reconocemos direcciones con una vía y un número.
PATRON_DIRECCION = re.compile(
    r"\b(?:calle|avenida|av\.?|pasaje|ruta)\s+"
    r"[\wÁÉÍÓÚÜÑáéíóúüñ.\s-]*?\d{1,6}\b",
    re.IGNORECASE
)

# Reconocemos las fuentes sin exigir un orden concreto.
PATRON_FUENTES = re.compile(
    r"\b(?:pdf|documento|recursos humanos|rr\.?\s*hh\.?)\b",
    re.IGNORECASE
)


def normalizar_domicilio(valor: str) -> str:
    """
    Normaliza una dirección para comparar textos.

    Reduce diferencias de mayúsculas, tildes
    y espacios, sin modificar el valor original.
    """

    texto = unicodedata.normalize("NFKD", valor)

    texto = "".join(
        caracter
        for caracter in texto
        if not unicodedata.combining(caracter)
    )

    texto = re.sub(r"\s+", " ", texto).strip()

    return texto.casefold()


def identificar_fuente(nombre: str) -> str:
    """
    Clasifica la referencia encontrada.
    """

    nombre = nombre.casefold()

    if nombre in ("pdf", "documento"):
        return "documento"

    return "rrhh"


def detectar_conflicto_en_mensaje(
    texto: str
) -> dict | None:
    """
    Detecta domicilios diferentes procedentes
    de un documento y de Recursos Humanos.

    Funciona tanto si aparece primero el PDF
    como si aparece primero Recursos Humanos.
    """

    if not isinstance(texto, str):
        return None

    if not texto.strip() or len(texto) > 20000:
        return None

    # Identificamos todas las referencias a fuentes.
    referencias = list(
        PATRON_FUENTES.finditer(texto)
    )

    if len(referencias) < 2:
        return None

    # Guardamos direcciones asociadas a cada fuente.
    domicilios = {
        "documento": [],
        "rrhh": []
    }

    for indice, referencia in enumerate(referencias):

        fuente = identificar_fuente(
            referencia.group(0)
        )

        # El segmento termina donde comienza
        # la siguiente referencia a una fuente.
        inicio = referencia.end()

        if indice + 1 < len(referencias):
            fin = referencias[indice + 1].start()
        else:
            fin = len(texto)

        fragmento = texto[inicio:fin]

        # Buscamos una dirección en ese segmento.
        coincidencia = PATRON_DIRECCION.search(
            fragmento
        )

        if coincidencia:
            domicilios[fuente].append(
                coincidencia.group(0).strip()
            )

    # Si falta una fuente, no inventamos valores.
    if not domicilios["documento"]:
        return None

    if not domicilios["rrhh"]:
        return None

    # Comparamos todas las direcciones identificadas.
    for domicilio_documento in domicilios["documento"]:

        for domicilio_rrhh in domicilios["rrhh"]:

            if (
                normalizar_domicilio(domicilio_documento)
                != normalizar_domicilio(domicilio_rrhh)
            ):
                return {
                    "estado": "conflicto",
                    "domicilio_documento": domicilio_documento,
                    "domicilio_rrhh": domicilio_rrhh
                }

    return None


def controlar_entrada_agente(
    callback_context,
    llm_request
):
    """
    Inspecciona la última solicitud del usuario
    antes de consultar a Ollama.

    Si reconoce un conflicto, responde desde
    Python y solicita revisión humana.
    """

    mensaje = ""

    # Buscamos el último mensaje del usuario.
    for contenido in reversed(
        llm_request.contents or []
    ):

        if contenido.role != "user":
            continue

        partes = contenido.parts or []

        textos = [
            parte.text
            for parte in partes
            if isinstance(parte.text, str)
            and parte.text.strip()
        ]

        mensaje = "\n".join(textos)
        break

    conflicto = detectar_conflicto_en_mensaje(
        mensaje
    )

    # Si no reconocemos este conflicto específico,
    # dejamos que continúen los demás controles.
    if conflicto is None:
        return None

    # Registramos un indicador en la sesión ADK.
    callback_context.state[
        "domicilio_en_conflicto"
    ] = True

    # Construimos una respuesta sin consultar al LLM.
    respuesta = (
        "Se detectaron domicilios contradictorios.\n\n"
        "Domicilio del documento: "
        f"{conflicto['domicilio_documento']}\n"
        "Domicilio informado por RR. HH.: "
        f"{conflicto['domicilio_rrhh']}\n\n"
        "Ninguno está confirmado. "
        "Se necesita revisión de un responsable "
        "autorizado antes de continuar.\n\n"
        "No se modificó ni aprobó ningún contrato."
    )

    return LlmResponse(
        content=types.Content(
            role="model",
            parts=[
                types.Part(text=respuesta)
            ]
        )
    )
