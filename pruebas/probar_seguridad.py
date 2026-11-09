
# Importamos SimpleNamespace para simular una herramienta
# sin necesidad de ejecutar el modelo de inteligencia artificial.
from types import SimpleNamespace

# Importamos el control de herramientas de nuestro agente.
from humania.agent import controlar_herramienta

# Importamos la herramienta que sí está autorizada.
from humania.tools.agente import comparar_domicilios


# PRUEBA 1: Intentar ejecutar una herramienta no autorizada.

herramienta_prohibida = SimpleNamespace(
    name="aprobar_contrato"
)

resultado1 = controlar_herramienta(
    tool=herramienta_prohibida,
    args={"contrato_id": "123"},
    tool_context=None
)

print("PRUEBA 1 - Aprobación no autorizada:")
print(resultado1)


# PRUEBA 2: Ejecutar una herramienta permitida.

herramienta_permitida = SimpleNamespace(
    name="comparar_domicilios"
)

resultado2 = controlar_herramienta(
    tool=herramienta_permitida,
    args={
        "domicilio_documento": "Calle Falsa 742",
        "domicilio_usuario": "Calle Falsa 850"
    },
    tool_context=None
)

print("\nPRUEBA 2 - Herramienta permitida:")
print(resultado2)


# PRUEBA 3: Intentar enviar argumentos demasiado largos.

resultado3 = controlar_herramienta(
    tool=herramienta_permitida,
    args={
        "domicilio_documento": "A" * 1500,
        "domicilio_usuario": "Calle Falsa 850"
    },
    tool_context=None
)

print("\nPRUEBA 3 - Argumento demasiado largo:")
print(resultado3)


# PRUEBA 4: Comprobar que se detecten contradicciones.

resultado4 = comparar_domicilios(
    domicilio_documento="Calle Falsa 742",
    domicilio_usuario="Calle Falsa 850"
)

print("\nPRUEBA 4 - Domicilios contradictorios:")
print("Estado:", resultado4["estado"])


# PRUEBA 5: Comprobar que domicilios iguales
# no generen una contradicción.

resultado5 = comparar_domicilios(
    domicilio_documento="Calle Falsa 742",
    domicilio_usuario="Calle Falsa 742"
)

print("\nPRUEBA 5 - Domicilios iguales:")
print("Estado:", resultado5["estado"])
