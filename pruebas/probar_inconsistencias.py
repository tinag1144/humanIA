
# Importamos las funciones que ya desarrollamos.
from humania.servicios.documentos import leer_documento
from humania.tools.extraer import extraer_datos
from humania.servicios.inconsistencias import (
    detectar_inconsistencias
)


# Leemos nuestro contrato de prueba.
documento = leer_documento(
    "documentos_prueba/contrato_ejemplo.pdf"
)

if documento["estado"] != "correcto":
    print("Error al leer el documento:", documento)

else:
    # Extraemos los datos mediante Ollama.
    extraccion = extraer_datos(documento["texto"])

    if extraccion["estado"] != "pendiente_confirmacion":
        print("Error de extracción:", extraccion)

    else:
        # Datos proporcionados por RR. HH. para simular
        # una contradicción con el documento.
        datos_usuario = {
            "nombre_empleado": "Juan Pérez",
            "domicilio_empleado": (
                "Calle Falsa 850, Ciudad de Córdoba, Córdoba"
            ),
            "puesto": "Desarrollador de Software"
        }

        # Comparamos ambas fuentes.
        resultado = detectar_inconsistencias(
            datos_documento=extraccion["datos"],
            datos_usuario=datos_usuario
        )

        # Mostramos el estado general.
        print("Estado:", resultado["estado"])

        # Mostramos los conflictos encontrados.
        print("\nInconsistencias detectadas:")

        for conflicto in resultado.get(
            "inconsistencias", []
        ):
            print("Campo:", conflicto["campo"])
            print("Documento:", conflicto["valor_documento"])
            print("Usuario:", conflicto["valor_usuario"])

        # Mostramos el mensaje final.
        print("\nMensaje:", resultado["mensaje"])
