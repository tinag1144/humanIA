
"""
HumanIA - Control de herramientas del agente.

Permite exclusivamente herramientas de:
- Comparacion de domicilios.
- Revision de datos contractuales.
- Consulta documental RAG.

No permite aprobaciones, firmas, modificaciones
de contratos ni acceso a credenciales.
"""

import math


HERRAMIENTAS_PERMITIDAS = {
    "comparar_domicilios",
    "revisar_datos_contrato",
    "consultar_documentacion"
}


ARGUMENTOS_PERMITIDOS = {
    "comparar_domicilios": {
        "domicilio_documento",
        "domicilio_usuario"
    },
    "revisar_datos_contrato": {
        "nombre_empleado",
        "puesto",
        "dni_empleado",
        "remuneracion_bruta"
    },
    "consultar_documentacion": {
        "pregunta"
    }
}


ARGUMENTOS_OBLIGATORIOS = {
    "comparar_domicilios": {
        "domicilio_documento",
        "domicilio_usuario"
    },
    "revisar_datos_contrato": {
        "nombre_empleado",
        "puesto"
    },
    "consultar_documentacion": {
        "pregunta"
    }
}


def bloquear(mensaje: str) -> dict:
    return {
        "estado": "bloqueado",
        "mensaje": mensaje
    }


def controlar_herramienta(tool, args, tool_context):
    """
    Callback de Google ADK.

    Devuelve None si la llamada esta permitida.
    Devuelve un diccionario si debe bloquearse.
    """

    nombre = getattr(tool, "name", None)

    # 1. Herramientas autorizadas.
    if nombre not in HERRAMIENTAS_PERMITIDAS:
        return bloquear(
            "Herramienta no autorizada."
        )

    # 2. Estructura de argumentos.
    if not isinstance(args, dict):
        return bloquear(
            "Los argumentos deben ser un diccionario."
        )

    permitidos = ARGUMENTOS_PERMITIDOS[nombre]

    # 3. Bloqueo de argumentos desconocidos.
    for argumento in args:
        if argumento not in permitidos:
            return bloquear(
                "La herramienta recibió un argumento "
                "que no está autorizado."
            )

    # 4. Validacion de tipos y tamanos.
    for clave, valor in args.items():

        if clave == "remuneracion_bruta":
            if type(valor) not in (int, float):
                return bloquear(
                    "La remuneración debe ser numérica."
                )

            if (
                not math.isfinite(valor)
                or valor < 0
                or valor > 1000000000
            ):
                return bloquear(
                    "Remuneración fuera del rango admitido."
                )

        else:
            if not isinstance(valor, str):
                return bloquear(
                    f"Argumento inválido: {clave}"
                )

            limite = (
                500
                if nombre == "consultar_documentacion"
                else 1000
            )

            if len(valor) > limite:
                return bloquear(
                    "El argumento es demasiado largo."
                )

    # 5. Comprobamos los argumentos obligatorios.
    for campo in ARGUMENTOS_OBLIGATORIOS[nombre]:

        if campo not in args:
            return bloquear(
                f"Falta el argumento obligatorio: {campo}"
            )

        if not args[campo].strip():
            return bloquear(
                f"Argumento inválido: {campo}"
            )

    # Solo estas operaciones superan el control.
    return None
