
# Importamos nuestro modelo de datos del contrato.
from humania.modelos.contrato import DatosContrato


# Definimos los campos necesarios para preparar el contrato.
# fecha_nacimiento se validará cuando la plantilla la requiera.
CAMPOS_OBLIGATORIOS = [
    "tipo_contrato",
    "empleador",
    "cuit_empleador",
    "domicilio_empleador",
    "nombre_empleado",
    "dni_empleado",
    "domicilio_empleado",
    "puesto",
    "fecha_inicio",
    "jornada_laboral",
    "remuneracion_bruta",
    "lugar_trabajo"
]


# Esta función recibe los datos del contrato y comprueba
# si falta información.
def validar_contrato(datos: dict) -> dict:

    # Intentamos convertir los datos al modelo DatosContrato.
    try:
        contrato = DatosContrato.model_validate(datos)

    # Si algún dato es inválido, devolvemos el error.
    except Exception as error:
        return {
            "estado": "error",
            "mensaje": str(error)
        }

    # Creamos una lista donde guardaremos los campos faltantes.
    faltantes = []

    # Recorremos cada campo obligatorio.
    for campo in CAMPOS_OBLIGATORIOS:

        # Obtenemos el valor correspondiente.
        valor = getattr(contrato, campo)

        # Comprobamos si no tiene información.
        if valor is None or valor == "":
            faltantes.append(campo)

    # Si encontramos campos faltantes, los devolvemos.
    if faltantes:
        return {
            "estado": "incompleto",
            "campos_faltantes": faltantes,
            "mensaje": "Faltan datos para preparar el contrato."
        }

    # Si todos los campos están presentes:
    return {
        "estado": "pendiente_revision",
        "campos_faltantes": [],
        "mensaje": (
            "Los campos obligatorios están completos. "
            "Todavía deben validarse antes de generar el contrato."
        )
    }
