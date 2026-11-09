
# Importamos nuestro modelo de datos.
from humania.modelos.contrato import DatosContrato


# Normalizamos los valores para compararlos.
def normalizar_valor(valor):

    # Si no hay información, devolvemos None.
    if valor is None:
        return None

    # Si recibimos texto, eliminamos espacios
    # sobrantes y convertimos a minúsculas.
    if isinstance(valor, str):
        return " ".join(valor.lower().split())

    # Otros valores se mantienen sin cambios.
    return valor


# Esta función compara la información de dos fuentes.
def detectar_inconsistencias(
    datos_documento: dict,
    datos_usuario: dict
) -> dict:

    # Verificamos que ambas fuentes sean diccionarios.
    if not isinstance(datos_documento, dict):
        return {
            "estado": "error",
            "mensaje": "Los datos del documento son inválidos."
        }

    if not isinstance(datos_usuario, dict):
        return {
            "estado": "error",
            "mensaje": "Los datos del usuario son inválidos."
        }

    # Validamos los campos con nuestro modelo Pydantic.
    try:
        documento = DatosContrato.model_validate(
            datos_documento
        ).model_dump(mode="json")

        usuario = DatosContrato.model_validate(
            datos_usuario
        ).model_dump(mode="json")

    except Exception as error:
        return {
            "estado": "error",
            "mensaje": f"Datos inválidos: {error}"
        }

    # Guardamos aquí los campos contradictorios.
    inconsistencias = []

    # Guardamos los datos que no presentan conflictos.
    datos_combinados = {}

    # Registramos el origen de cada dato.
    procedencia = {}

    # Recorremos todos los campos del modelo.
    for campo in DatosContrato.model_fields:

        valor_documento = documento[campo]
        valor_usuario = usuario[campo]

        # Normalizamos los valores para compararlos.
        normal_documento = normalizar_valor(
            valor_documento
        )

        normal_usuario = normalizar_valor(
            valor_usuario
        )

        # Si las dos fuentes tienen valores diferentes,
        # registramos una inconsistencia.
        if (
            normal_documento is not None
            and normal_usuario is not None
            and normal_documento != normal_usuario
        ):

            inconsistencias.append({
                "campo": campo,
                "valor_documento": valor_documento,
                "valor_usuario": valor_usuario
            })

            # No elegimos ninguno de los dos valores.
            datos_combinados[campo] = None
            procedencia[campo] = "conflicto"

        # Si los valores coinciden, conservamos el dato.
        elif (
            normal_documento is not None
            and normal_usuario is not None
        ):
            datos_combinados[campo] = valor_documento
            procedencia[campo] = "ambas_fuentes"

        # Si solo el usuario proporcionó el valor.
        elif normal_usuario is not None:
            datos_combinados[campo] = valor_usuario
            procedencia[campo] = "usuario"

        # Si solo aparece en el documento.
        elif normal_documento is not None:
            datos_combinados[campo] = valor_documento
            procedencia[campo] = "documento"

        # Si ninguna fuente tiene el dato.
        else:
            datos_combinados[campo] = None
            procedencia[campo] = "sin_informacion"

    # Si encontramos contradicciones, detenemos
    # la combinación hasta recibir una aclaración.
    if inconsistencias:
        return {
            "estado": "conflicto",
            "inconsistencias": inconsistencias,
            "datos": datos_combinados,
            "procedencia": procedencia,
            "mensaje": (
                "Se encontraron datos contradictorios. "
                "Se requiere confirmación de RR. HH."
            )
        }

    # Sin contradicciones no significa que los
    # datos ya estén aprobados.
    return {
        "estado": "pendiente_confirmacion",
        "inconsistencias": [],
        "datos": datos_combinados,
        "procedencia": procedencia,
        "mensaje": (
            "No se detectaron diferencias entre los "
            "valores comparables. "
            "Los datos requieren confirmación humana."
        )
    }
