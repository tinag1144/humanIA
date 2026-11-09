
# Importamos el validador que desarrollamos anteriormente.
from humania.tools.validar import validar_contrato


def revisar_datos_contrato(
    nombre_empleado: str,
    puesto: str,
    dni_empleado: str = "",
    remuneracion_bruta: float = 0
) -> dict:
    """
    Revisa los datos iniciales de un contrato laboral.

    Args:
        nombre_empleado: Nombre y apellido del empleado.
        puesto: Función que desempeñará.
        dni_empleado: Documento de identidad, si está disponible.
        remuneracion_bruta: Salario bruto, si fue informado.

    Returns:
        Estado del contrato y campos que faltan completar.
    """

    # Comprobamos los argumentos recibidos.
    if not isinstance(nombre_empleado, str):
        return {
            "estado": "error",
            "mensaje": "El nombre debe ser texto."
        }

    if not isinstance(puesto, str):
        return {
            "estado": "error",
            "mensaje": "El puesto debe ser texto."
        }

    if not nombre_empleado.strip() or not puesto.strip():
        return {
            "estado": "error",
            "mensaje": "Se necesitan el nombre y el puesto."
        }

    # Comprobamos si el salario fue informado.
    if remuneracion_bruta < 0:
        return {
            "estado": "error",
            "mensaje": "La remuneración no puede ser negativa."
        }

    # Construimos un diccionario con los datos disponibles.
    datos = {
        "nombre_empleado": nombre_empleado.strip(),
        "puesto": puesto.strip()
    }

    # Agregamos el DNI solamente si fue proporcionado.
    if dni_empleado.strip():
        datos["dni_empleado"] = dni_empleado.strip()

    # Agregamos la remuneración cuando es mayor que cero.
    if remuneracion_bruta > 0:
        datos["remuneracion_bruta"] = remuneracion_bruta

    # Reutilizamos nuestro validador original.
    resultado = validar_contrato(datos)

    # Devolvemos el resultado al agente.
    return resultado
