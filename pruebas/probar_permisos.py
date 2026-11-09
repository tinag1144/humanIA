
# Simulamos herramientas para probar los controles.
from types import SimpleNamespace

# Importamos nuestro guardrail.
from humania.seguridad.permisos import controlar_herramienta


def probar(nombre, argumentos):

    # Creamos una herramienta simulada.
    herramienta = SimpleNamespace(name=nombre)

    # Ejecutamos el control.
    resultado = controlar_herramienta(
        tool=herramienta,
        args=argumentos,
        tool_context=None
    )

    # Mostramos el resultado.
    print(nombre, ":", resultado)


# PRUEBA 1: Intento de aprobar un contrato.
probar(
    "aprobar_contrato",
    {"contrato_id": "123"}
)

# PRUEBA 2: Herramienta permitida.
probar(
    "comparar_domicilios",
    {
        "domicilio_documento": "Calle Falsa 742",
        "domicilio_usuario": "Calle Falsa 850"
    }
)

# PRUEBA 3: Argumento desconocido.
probar(
    "comparar_domicilios",
    {
        "domicilio_documento": "Calle Falsa 742",
        "domicilio_usuario": "Calle Falsa 850",
        "aprobar": True
    }
)

# PRUEBA 4: Falta un argumento.
probar(
    "comparar_domicilios",
    {
        "domicilio_documento": "Calle Falsa 742"
    }
)

# PRUEBA 5: Remuneración incorrecta.
probar(
    "revisar_datos_contrato",
    {
        "nombre_empleado": "Juan Pérez",
        "puesto": "Desarrollador",
        "remuneracion_bruta": -500
    }
)

# PRUEBA 6: Argumento demasiado largo.
probar(
    "comparar_domicilios",
    {
        "domicilio_documento": "A" * 1500,
        "domicilio_usuario": "Calle Falsa 850"
    }
)
