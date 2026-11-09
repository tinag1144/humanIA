
"""
HumanIA - Controles de seguridad sobre las respuestas.

Protecciones:
1. Registra conflictos detectados por herramientas.
2. Impide confirmar domicilios contradictorios.
3. Bloquea afirmaciones falsas de aprobacion o firma.

No modifica contratos, documentos ni SQLite.
"""

import re
import unicodedata

from google.genai import types
from google.adk.models.llm_response import LlmResponse


RESPUESTA_APROBACION_SEGURA = (
    "No puedo confirmar que un contrato haya sido "
    "aprobado o firmado automaticamente.\n\n"
    "Como asistente de Recursos Humanos, solamente "
    "puedo ayudar a recopilar y revisar informacion. "
    "La aprobacion requiere un responsable autorizado "
    "y debe verificarse en el backend de HumanIA.\n\n"
    "No se aprobo ni firmo ningun contrato "
    "mediante esta conversacion."
)


# Patrones de afirmaciones potencialmente falsas.
PATRONES_AFIRMACIONES = [
    r"\b(?:el|este|tu|su)\s+contrato\s+"
    r"(?:ya\s+)?(?:fue|ha\s+sido|quedo|esta)\s+"
    r"(?:debidamente\s+)?(?:aprobado|firmado)\b",

    r"\b(?:he|hemos|se\s+ha)\s+"
    r"(?:aprobado|firmado)\s+"
    r"(?:el|este|tu|su)\s+contrato\b",

    r"\bcontrato\s+(?:aprobado|firmado)\s+"
    r"(?:automaticamente|exitosamente)\b",

    r"\b(?:aprobacion|firma)\s+"
    r"(?:automatica|completada|realizada)\b",

    r"\b(?:aprobado|firmado)\s+y\s+"
    r"(?:aprobado|firmado)\s+automaticamente\b",
]


def normalizar_texto(texto: str) -> str:
    """
    Normaliza tildes, mayusculas y espacios.
    No modifica el texto original.
    """

    texto = unicodedata.normalize("NFKD", texto)

    texto = "".join(
        caracter
        for caracter in texto
        if not unicodedata.combining(caracter)
    )

    texto = re.sub(r"\s+", " ", texto)

    return texto.casefold().strip()


def detectar_aprobacion_falsa(texto: str) -> bool:
    """
    Detecta afirmaciones conocidas que presentan
    una aprobacion o firma como realizada.

    Es una proteccion complementaria basada
    en patrones, no una garantia absoluta.
    """

    if not isinstance(texto, str):
        return False

    normalizado = normalizar_texto(texto)

    for patron in PATRONES_AFIRMACIONES:

        for coincidencia in re.finditer(
            patron,
            normalizado
        ):
            fragmento = coincidencia.group(0)

            # Evitamos bloquear una negacion
            # explicita del tipo "no he aprobado".
            if re.search(
                r"\b(?:no|nunca)\s+"
                r"(?:he|hemos|se\s+ha)\s+"
                r"(?:aprobado|firmado)\b",
                fragmento
            ):
                continue

            inicio = coincidencia.start()
            contexto = normalizado[
                max(0, inicio - 12):inicio
            ]

            if re.search(r"\bno\s+$", contexto):
                continue

            return True

    return False


def registrar_conflicto(
    tool,
    args,
    tool_context,
    tool_response
):
    """
    Callback posterior a la ejecucion de herramientas.

    Registra un conflicto real detectado por
    comparar_domicilios en el estado de la sesion.

    No confirma valores ni modifica contratos.
    """

    if getattr(tool, "name", None) != "comparar_domicilios":
        return None

    if not isinstance(tool_response, dict):
        return None

    if tool_response.get("estado") != "conflicto":
        return None

    if tool_context is None:
        return None

    estado = tool_context.state

    estado["domicilio_en_conflicto"] = True

    # La herramienta puede devolver las direcciones
    # en la respuesta o recibirlas por argumentos.
    argumentos = args if isinstance(args, dict) else {}

    domicilio_documento = (
        tool_response.get("domicilio_documento")
        or argumentos.get("domicilio_documento")
    )

    domicilio_rrhh = (
        tool_response.get("domicilio_rrhh")
        or tool_response.get("domicilio_usuario")
        or argumentos.get("domicilio_usuario")
    )

    if isinstance(domicilio_documento, str):
        estado["domicilio_documento_conflicto"] = (
            domicilio_documento
        )

    if isinstance(domicilio_rrhh, str):
        estado["domicilio_rrhh_conflicto"] = (
            domicilio_rrhh
        )

    return None


def construir_respuesta_conflicto(estado) -> str:
    """
    Prepara una respuesta sin elegir ni confirmar
    ninguno de los domicilios contradictorios.
    """

    documento = estado.get(
        "domicilio_documento_conflicto"
    )

    rrhh = estado.get(
        "domicilio_rrhh_conflicto"
    )

    lineas = [
        "Se detecto una inconsistencia en el "
        "domicilio del empleado."
    ]

    if isinstance(documento, str) and documento:
        lineas.append(
            f"\nDocumento: {documento}"
        )

    if isinstance(rrhh, str) and rrhh:
        lineas.append(
            f"Recursos Humanos: {rrhh}"
        )

    lineas.append(
        "\nNinguno de los domicilios está confirmado. "
        "Un responsable autorizado debe revisar "
        "la contradiccion antes de continuar."
    )

    lineas.append(
        "No se modifico ni aprobo ningun contrato."
    )

    return "\n".join(lineas)


def crear_respuesta_segura(texto: str) -> LlmResponse:
    """
    Construye una respuesta de ADK sin
    llamadas a herramientas.
    """

    return LlmResponse(
        content=types.Content(
            role="model",
            parts=[
                types.Part(text=texto)
            ]
        )
    )


def controlar_respuesta(
    callback_context,
    llm_response
):
    """
    Callback posterior a la consulta de Ollama.

    Prioridad:
    1. Mantener un conflicto abierto sin confirmar.
    2. Bloquear afirmaciones falsas de aprobacion.
    3. Permitir otras respuestas.

    No reemplaza llamadas a herramientas.
    """

    contenido = llm_response.content

    if contenido is None:
        return None

    partes = contenido.parts or []

    # No interferimos con llamadas a herramientas.
    for parte in partes:
        if parte.function_call is not None:
            return None

    # Si ADK registro un conflicto, Python determina
    # la respuesta segura sin dejar que el modelo elija.
    if (
        callback_context is not None
        and callback_context.state.get(
            "domicilio_en_conflicto"
        ) is True
    ):
        return crear_respuesta_segura(
            construir_respuesta_conflicto(
                callback_context.state
            )
        )

    textos = [
        parte.text
        for parte in partes
        if isinstance(parte.text, str)
    ]

    respuesta = "\n".join(textos)

    if not detectar_aprobacion_falsa(respuesta):
        return None

    if callback_context is not None:
        callback_context.state[
            "respuesta_aprobacion_bloqueada"
        ] = True

    return crear_respuesta_segura(
        RESPUESTA_APROBACION_SEGURA
    )


def controlar_respuesta_agente(
    callback_context,
    llm_response
):
    """
    Conserva el nombre utilizado actualmente
    por humania/agent.py.
    """

    return controlar_respuesta(
        callback_context,
        llm_response
    )
