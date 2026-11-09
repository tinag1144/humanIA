
# Importamos el lector de documentos.
from humania.servicios.documentos import leer_documento

# Importamos nuestra función de extracción inteligente.
from humania.tools.extraer import extraer_datos

# Importamos el validador que ya desarrollamos.
from humania.tools.validar import validar_contrato


# Paso 1: Leemos el contrato PDF.
documento = leer_documento(
    "documentos_prueba/contrato_ejemplo.pdf"
)

# Comprobamos si pudimos leerlo.
if documento["estado"] != "correcto":
    print("Error al leer:", documento["mensaje"])

else:
    print("Documento leído correctamente.")

    # Paso 2: Extraemos los datos mediante Ollama.
    resultado = extraer_datos(documento["texto"])

    print("Estado de extracción:", resultado["estado"])

    if resultado["estado"] == "pendiente_confirmacion":

        # Mostramos cada dato extraído.
        datos = resultado["datos"]

        for campo, valor in datos.items():
            print(f"{campo}: {valor}")

        # Paso 3: Comprobamos campos faltantes.
        validacion = validar_contrato(datos)

        print("\nResultado de validación:")
        print(validacion)

        print(
            "\nATENCIÓN: los datos todavía "
            "requieren confirmación humana."
        )

    else:
        print(resultado["mensaje"])
