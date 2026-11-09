
# Importamos la función que ya desarrollamos.
from humania.servicios.inconsistencias import detectar_inconsistencias


def comparar_domicilios(
    domicilio_documento: str,
    domicilio_usuario: str
) -> dict:
    """
    Compara el domicilio del empleado entre dos fuentes.

    Args:
        domicilio_documento: Domicilio extraído del documento.
        domicilio_usuario: Domicilio informado por RR. HH.

    Returns:
        Resultado de la comparación y posibles inconsistencias.
    """

    # Validamos que los dos valores sean textos.
    if not isinstance(domicilio_documento, str):
        return {
            "estado": "error",
            "mensaje": "El domicilio del documento debe ser texto."
        }

    if not isinstance(domicilio_usuario, str):
        return {
            "estado": "error",
            "mensaje": "El domicilio del usuario debe ser texto."
        }

    # Comprobamos que los domicilios no estén vacíos.
    if not domicilio_documento.strip() or not domicilio_usuario.strip():
        return {
            "estado": "error",
            "mensaje": "Se necesitan los dos domicilios."
        }

    # Reutilizamos nuestra función de detección.
    resultado = detectar_inconsistencias(
        datos_documento={
            "domicilio_empleado": domicilio_documento
        },
        datos_usuario={
            "domicilio_empleado": domicilio_usuario
        }
    )

    # Devolvemos el resultado al agente.
    return resultado
