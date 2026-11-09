
# Importamos la detección de inconsistencias.
from humania.servicios.inconsistencias import (
    detectar_inconsistencias
)

# Importamos las funciones de almacenamiento.
from humania.servicios.estado_contrato import (
    crear_registro,
    consultar_registro
)


# Simulamos dos domicilios contradictorios.
resultado = detectar_inconsistencias(
    datos_documento={
        "nombre_empleado": "Juan Pérez",
        "domicilio_empleado": "Calle Falsa 742"
    },
    datos_usuario={
        "nombre_empleado": "Juan Pérez",
        "domicilio_empleado": "Calle Falsa 850"
    }
)

# Comprobamos que existe un conflicto.
assert resultado["estado"] == "conflicto"

# Guardamos los datos sin confirmar.
registro = crear_registro(
    datos=resultado["datos"],
    inconsistencias=resultado["inconsistencias"]
)

print("Estado al guardar:", registro["estado"])

# Consultamos lo que quedó almacenado.
guardado = consultar_registro(
    registro["contrato_id"]
)

print("Estado en SQLite:", guardado["estado"])
print(
    "Domicilio almacenado:",
    guardado["datos"]["domicilio_empleado"]
)
print("Aprobado por:", guardado["aprobado_por"])

# Validaciones automáticas.
assert guardado["estado"] == "en_conflicto"

# El domicilio contradictorio debe permanecer vacío.
assert guardado["datos"]["domicilio_empleado"] is None

# Nadie debe aparecer como aprobador.
assert guardado["aprobado_por"] is None

# No debe existir fecha de aprobación.
assert guardado["fecha_aprobacion"] is None

print("\nTODAS LAS PRUEBAS SUPERADAS")
