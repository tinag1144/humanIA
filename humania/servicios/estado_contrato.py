
"""
Persistencia y consulta del estado de los contratos.

Este módulo administra los registros contractuales
en SQLite sin aprobar contratos automáticamente.
"""

import hashlib
import json
import sqlite3

from pathlib import Path
from uuid import uuid4


# Ubicamos el proyecto y su base de datos.
BASE_DIR = Path(__file__).resolve().parents[2]

CARPETA_DATOS = BASE_DIR / "datos"
RUTA_DB = CARPETA_DATOS / "humania.db"


def conectar():
    """
    Abre una conexión con la base de datos.
    """

    CARPETA_DATOS.mkdir(
        parents=True,
        exist_ok=True
    )

    return sqlite3.connect(str(RUTA_DB))


def calcular_huella(datos: dict) -> str:
    """
    Calcula una huella SHA-256 de los datos.

    Ordenamos las claves para que el resultado
    no dependa de su orden en el diccionario.
    """

    contenido = json.dumps(
        datos,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":")
    )

    return hashlib.sha256(
        contenido.encode("utf-8")
    ).hexdigest()


def inicializar_base():
    """
    Crea la tabla si no existe.

    También incorpora las columnas nuevas a las
    bases de datos anteriores sin borrar registros.
    """

    with conectar() as conexion:

        conexion.execute("""
            CREATE TABLE IF NOT EXISTS contratos (
                id TEXT PRIMARY KEY,
                estado TEXT NOT NULL,
                datos TEXT NOT NULL,
                inconsistencias TEXT NOT NULL,
                aprobado_por TEXT,
                fecha_aprobacion TEXT,
                confirmado_por TEXT,
                fecha_confirmacion TEXT,
                huella_confirmacion TEXT
            )
        """)

        # Consultamos las columnas que ya existen.
        columnas = {
            fila[1]
            for fila in conexion.execute(
                "PRAGMA table_info(contratos)"
            ).fetchall()
        }

        # Actualizamos las instalaciones anteriores.
        nuevas_columnas = {
            "confirmado_por": "TEXT",
            "fecha_confirmacion": "TEXT",
            "huella_confirmacion": "TEXT"
        }

        for nombre, tipo in nuevas_columnas.items():

            if nombre not in columnas:

                conexion.execute(
                    f"ALTER TABLE contratos "
                    f"ADD COLUMN {nombre} {tipo}"
                )


def crear_registro(
    datos: dict,
    inconsistencias: list
) -> dict:
    """
    Guarda un contrato sin confirmarlo ni aprobarlo.
    """

    if not isinstance(datos, dict):
        return {
            "estado": "error",
            "mensaje": "Los datos deben ser un diccionario."
        }

    if not isinstance(inconsistencias, list):
        return {
            "estado": "error",
            "mensaje": "Las inconsistencias deben ser una lista."
        }

    # Ningún registro recién creado está confirmado.
    if inconsistencias:
        estado = "en_conflicto"
    else:
        estado = "pendiente_confirmacion"

    identificador = str(uuid4())

    try:
        inicializar_base()

        with conectar() as conexion:

            conexion.execute(
                """
                INSERT INTO contratos (
                    id,
                    estado,
                    datos,
                    inconsistencias,
                    aprobado_por,
                    fecha_aprobacion,
                    confirmado_por,
                    fecha_confirmacion,
                    huella_confirmacion
                )
                VALUES (
                    ?, ?, ?, ?,
                    NULL, NULL,
                    NULL, NULL, NULL
                )
                """,
                (
                    identificador,
                    estado,
                    json.dumps(
                        datos,
                        ensure_ascii=False
                    ),
                    json.dumps(
                        inconsistencias,
                        ensure_ascii=False
                    )
                )
            )

        return {
            "estado": estado,
            "contrato_id": identificador,
            "mensaje": (
                "Información registrada sin confirmación "
                "ni aprobación."
            )
        }

    except (sqlite3.Error, TypeError, ValueError):
        return {
            "estado": "error",
            "mensaje": "No se pudo guardar el registro."
        }


def consultar_registro(contrato_id: str) -> dict:
    """
    Recupera un contrato y sus estados de revisión.
    """

    if (
        not isinstance(contrato_id, str)
        or not contrato_id.strip()
    ):
        return {
            "estado": "error",
            "mensaje": "Identificador inválido."
        }

    try:
        inicializar_base()

        with conectar() as conexion:

            fila = conexion.execute(
                """
                SELECT
                    id,
                    estado,
                    datos,
                    inconsistencias,
                    aprobado_por,
                    fecha_aprobacion,
                    confirmado_por,
                    fecha_confirmacion,
                    huella_confirmacion
                FROM contratos
                WHERE id = ?
                """,
                (contrato_id,)
            ).fetchone()

        if fila is None:
            return {
                "estado": "no_encontrado",
                "mensaje": "El registro no existe."
            }

        datos = json.loads(fila[2])

        # Comprobamos si existen datos confirmados.
        huella_guardada = fila[8]

        integridad_confirmada = (
            huella_guardada is not None
            and huella_guardada == calcular_huella(datos)
        )

        return {
            "id": fila[0],
            "estado": fila[1],
            "datos": datos,
            "inconsistencias": json.loads(fila[3]),
            "aprobado_por": fila[4],
            "fecha_aprobacion": fila[5],
            "confirmado_por": fila[6],
            "fecha_confirmacion": fila[7],
            "huella_confirmacion": huella_guardada,
            "integridad_confirmada": integridad_confirmada
        }

    except (
        sqlite3.Error,
        ValueError,
        TypeError
    ):
        return {
            "estado": "error",
            "mensaje": "No se pudo consultar el registro."
        }
