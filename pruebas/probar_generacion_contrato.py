
"""
Pruebas automáticas del generador DOCX de HumanIA.

Verificamos:
1. Bloqueo de contratos incompletos.
2. Bloqueo de contratos completos sin confirmación.
3. Generación luego de una confirmación integral.
4. Rechazo de datos modificados después de confirmarse.
5. Contenido básico del documento generado.

Todos los datos utilizados son ficticios.
"""

import json

from datetime import date
from pathlib import Path

from docx import Document

from humania.servicios.estado_contrato import (
    crear_registro,
    consultar_registro,
    conectar
)

from humania.servicios.aprobaciones import (
    confirmar_datos_completos
)

from humania.servicios.contratos import generar_borrador


# Identidad ficticia para probar el servicio directamente.
# No reemplaza la autenticación de FastAPI.
USUARIO_PRUEBA = {
    "id": 1,
    "usuario": "responsable_prueba",
    "rol": "rrhh"
}


# Datos ficticios completos.
DATOS_PRUEBA = {
    "tipo_contrato": "indeterminado",
    "empleador": "HumanIA S.A.",
    "cuit_empleador": "30-00000000-0",
    "domicilio_empleador": "Av. Ejemplo 1234",
    "nombre_empleado": "Juan Pérez",
    "dni_empleado": "00.000.000",
    "fecha_nacimiento": "1995-03-15",
    "domicilio_empleado": "Calle Falsa 742",
    "puesto": "Desarrollador de Software",
    "fecha_inicio": "2026-11-09",
    "jornada_laboral": (
        "40 horas semanales, lunes a viernes de 9 a 17"
    ),
    "remuneracion_bruta": 2500000,
    "lugar_trabajo": "Av. Ejemplo 1234, Córdoba"
}


def crear_contrato(datos):
    """
    Crea un registro aislado para cada prueba.
    """

    resultado = crear_registro(
        datos=datos,
        inconsistencias=[]
    )

    assert "contrato_id" in resultado, resultado

    return resultado["contrato_id"]


def generar(contrato_id):
    """
    Ejecuta la generación con datos de firma ficticios.
    """

    return generar_borrador(
        contrato_id=contrato_id,
        ciudad_firma="Córdoba",
        fecha_firma=date(2026, 11, 9)
    )


def obtener_texto_docx(ruta):
    """
    Recupera el texto de párrafos, tablas y encabezados.
    """

    documento = Document(str(ruta))
    partes = []

    for parrafo in documento.paragraphs:
        partes.append(parrafo.text)

    for tabla in documento.tables:
        for fila in tabla.rows:
            for celda in fila.cells:
                for parrafo in celda.paragraphs:
                    partes.append(parrafo.text)

    for seccion in documento.sections:
        for parrafo in seccion.header.paragraphs:
            partes.append(parrafo.text)

    return "\n".join(partes)


# PRUEBA 1: contrato incompleto.
contrato_incompleto = crear_contrato({
    "nombre_empleado": "Juan Pérez"
})

resultado = generar(contrato_incompleto)

assert resultado["estado"] == "bloqueado", resultado

print("PRUEBA 1 SUPERADA: contrato incompleto bloqueado.")


# PRUEBA 2: contrato completo, pero sin confirmación.
contrato_completo = crear_contrato(DATOS_PRUEBA.copy())

resultado = generar(contrato_completo)

assert resultado["estado"] == "bloqueado", resultado

print(
    "PRUEBA 2 SUPERADA: contrato sin "
    "confirmación humana bloqueado."
)


# PRUEBA 3: confirmación integral y generación.
confirmacion = confirmar_datos_completos(
    contrato_id=contrato_completo,
    usuario_actual=USUARIO_PRUEBA
)

assert confirmacion["estado"] == "datos_confirmados", confirmacion

registro = consultar_registro(contrato_completo)

assert registro["integridad_confirmada"] is True
assert registro["aprobado_por"] is None

resultado = generar(contrato_completo)

assert resultado["estado"] == "borrador_generado", resultado
assert resultado["aprobado"] is False
assert resultado["integridad_confirmada"] is True

ruta_documento = Path(resultado["ruta"])

assert ruta_documento.is_file()

print(
    "PRUEBA 3 SUPERADA: borrador generado "
    "con datos confirmados."
)


# PRUEBA 4: contenido básico del DOCX.
texto_documento = obtener_texto_docx(ruta_documento)

assert "Juan Pérez" in texto_documento
assert "Calle Falsa 742" in texto_documento
assert "Desarrollador de Software" in texto_documento
assert "$ 2.500.000,00" in texto_documento

assert "BORRADOR - SIN APROBACION FINAL" in texto_documento

# No deben quedar variables de plantilla sin resolver.
assert "{{" not in texto_documento
assert "}}" not in texto_documento

# Comprobamos los encabezados de las ocho cláusulas.
for numero in (
    "PRIMERA", "SEGUNDA", "TERCERA", "CUARTA",
    "QUINTA", "SEXTA", "SÉPTIMA", "OCTAVA"
):
    assert numero in texto_documento, (
        f"No se encontró la cláusula {numero}."
    )

print("PRUEBA 4 SUPERADA: contenido DOCX verificado.")


# PRUEBA 5: modificación posterior de datos.
# Creamos otro registro para no alterar el contrato
# que utilizamos en la prueba de generación.
contrato_modificado = crear_contrato(DATOS_PRUEBA.copy())

confirmacion = confirmar_datos_completos(
    contrato_id=contrato_modificado,
    usuario_actual=USUARIO_PRUEBA
)

assert confirmacion["estado"] == "datos_confirmados"

# Simulamos una modificación directa no autorizada
# sobre los datos almacenados en SQLite.
with conectar() as db:

    fila = db.execute(
        "SELECT datos FROM contratos WHERE id = ?",
        (contrato_modificado,)
    ).fetchone()

    datos_alterados = json.loads(fila[0])

    datos_alterados["remuneracion_bruta"] = 9999999

    db.execute(
        """
        UPDATE contratos
        SET datos = ?
        WHERE id = ?
        """,
        (
            json.dumps(
                datos_alterados,
                ensure_ascii=False
            ),
            contrato_modificado
        )
    )

# La huella original ya no debe coincidir.
registro_alterado = consultar_registro(
    contrato_modificado
)

assert registro_alterado["integridad_confirmada"] is False

resultado = generar(contrato_modificado)

assert resultado["estado"] == "bloqueado", resultado

print(
    "PRUEBA 5 SUPERADA: modificación posterior "
    "detectada y generación bloqueada."
)


print()
print("TODAS LAS PRUEBAS DE GENERACIÓN SUPERADAS")
print("BORRADOR CREADO:", ruta_documento.name)
