
# Importamos los servicios existentes.
from humania.servicios.inconsistencias import (
    detectar_inconsistencias
)

from humania.servicios.estado_contrato import (
    crear_registro,
    consultar_registro
)


# Simulamos un conflicto entre el PDF y RR. HH.
comparacion = detectar_inconsistencias(
    datos_documento={
        "nombre_empleado": "Juan Pérez",
        "domicilio_empleado": "Calle Falsa 742"
    },
    datos_usuario={
        "nombre_empleado": "Juan Pérez",
        "domicilio_empleado": "Calle Falsa 850"
    }
)

assert comparacion["estado"] == "conflicto"

# Guardamos la información con estado en_conflicto.
registro = crear_registro(
    datos=comparacion["datos"],
    inconsistencias=comparacion["inconsistencias"]
)

assert registro["estado"] == "en_conflicto"

# Comprobamos que SQLite guardó el contrato.
contrato = consultar_registro(
    registro["contrato_id"]
)

print("CONTRATO_ID:", contrato["id"])
print("ESTADO:", contrato["estado"])
print(
    "DOMICILIO:",
    contrato["datos"]["domicilio_empleado"]
)

assert contrato["datos"]["domicilio_empleado"] is None
assert contrato["aprobado_por"] is None

print("PRUEBA SUPERADA")
