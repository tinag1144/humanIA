
# Importamos las funciones necesarias.
from humania.servicios.inconsistencias import (
    detectar_inconsistencias
)

from humania.servicios.estado_contrato import (
    crear_registro,
    consultar_registro
)

from humania.servicios.revision import (
    obtener_revision_pendiente
)


# Creamos un conflicto ficticio entre dos domicilios.
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

# Guardamos el contrato sin confirmar.
registro = crear_registro(
    datos=comparacion["datos"],
    inconsistencias=comparacion["inconsistencias"]
)

# Consultamos la revisión pendiente.
revision = obtener_revision_pendiente(
    registro["contrato_id"]
)

print("Estado de revisión:", revision["estado"])

# Recorremos los conflictos registrados.
for conflicto in revision.get("conflictos", []):
    print("Campo:", conflicto["campo"])
    print("Documento:", conflicto["valor_documento"])
    print("RR. HH.:", conflicto["valor_usuario"])

# Consultamos nuevamente SQLite.
guardado = consultar_registro(registro["contrato_id"])

print("\nEstado en SQLite:", guardado["estado"])
print("Aprobado por:", guardado["aprobado_por"])

# Comprobamos que la revisión no modificó el contrato.
assert revision["estado"] == "requiere_revision"
assert guardado["estado"] == "en_conflicto"
assert guardado["datos"]["domicilio_empleado"] is None
assert guardado["aprobado_por"] is None

print("\nTODAS LAS PRUEBAS SUPERADAS")
