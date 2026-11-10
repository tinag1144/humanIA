
"""
Auditoría de borradores contractuales de HumanIA.

Registra:
- Contrato de origen.
- Nombre del archivo generado.
- Fecha de generación.
- Huella SHA-256 del DOCX.
- Huellas de los datos y de la plantilla.

Permite detectar modificaciones posteriores.

No aprueba ni firma contratos.
"""

import hashlib
import sqlite3

from datetime import datetime, timezone
from pathlib import Path

from humania.servicios.estado_contrato import (
    conectar,
    inicializar_base,
    consultar_registro
)


# Ubicación del proyecto.
RAIZ = Path(__file__).resolve().parents[2]

# Reutilizamos la carpeta existente.
CARPETA_BORRADORES = RAIZ / "contratos_generados"


def calcular_huella_archivo(ruta: Path) -> str:
    """
    Calcula SHA-256 leyendo el archivo en bloques.

    Evitamos cargar todo el DOCX en memoria.
    """

    digest = hashlib.sha256()

    with ruta.open("rb") as archivo:
        for bloque in iter(
            lambda: archivo.read(65536),
            b""
        ):
            digest.update(bloque)

    return digest.hexdigest()


def inicializar_auditoria():
    """
    Crea la tabla de versiones sin modificar
    ni eliminar los contratos existentes.
    """

    inicializar_base()

    with conectar() as db:

        db.execute("""
            CREATE TABLE IF NOT EXISTS borradores (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                contrato_id TEXT NOT NULL,
                version INTEGER NOT NULL,
                archivo TEXT NOT NULL UNIQUE,
                fecha_generacion TEXT NOT NULL,
                huella_archivo TEXT NOT NULL,
                huella_datos TEXT NOT NULL,
                huella_plantilla TEXT NOT NULL,
                confirmado_por TEXT NOT NULL,
                UNIQUE (contrato_id, version),
                FOREIGN KEY (contrato_id)
                    REFERENCES contratos(id)
            )
        """)

        db.commit()


def registrar_borrador(
    contrato_id: str,
    ruta_archivo: str,
    huella_plantilla: str
) -> dict:
    """
    Registra una versión concreta de un borrador.

    Solo admite DOCX dentro de contratos_generados
    y contratos con datos confirmados e íntegros.
    """

    if not isinstance(contrato_id, str) or not contrato_id.strip():
        return {
            "estado": "bloqueado",
            "mensaje": "Identificador inválido."
        }

    if (
        not isinstance(ruta_archivo, str)
        or not isinstance(huella_plantilla, str)
        or len(huella_plantilla) != 64
        or any(
            caracter not in "0123456789abcdefABCDEF"
            for caracter in huella_plantilla
        )
    ):
        return {
            "estado": "bloqueado",
            "mensaje": "Parámetros de auditoría inválidos."
        }

    try:
        ruta = Path(ruta_archivo).resolve()
        carpeta = CARPETA_BORRADORES.resolve()

        # Evitamos registrar archivos fuera de la carpeta.
        if ruta.parent != carpeta or ruta.suffix.lower() != ".docx":
            return {
                "estado": "bloqueado",
                "mensaje": "Ruta de borrador no autorizada."
            }

        if not ruta.is_file():
            return {
                "estado": "bloqueado",
                "mensaje": "El archivo no existe."
            }

        inicializar_auditoria()

        with conectar() as db:
            db.execute("BEGIN IMMEDIATE")

            # Consultamos el contrato dentro de la transacción.
            fila = db.execute(
                """
                SELECT
                    estado,
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
                    "estado": "bloqueado",
                    "mensaje": "El contrato no existe."
                }

            (
                estado,
                inconsistencias,
                aprobado_por,
                fecha_aprobacion,
                confirmado_por,
                fecha_confirmacion,
                huella_datos
            ) = fila

            # Comprobamos los requisitos de auditoría.
            if (
                estado != "datos_confirmados"
                or inconsistencias != "[]"
                or aprobado_por is not None
                or fecha_aprobacion is not None
                or not confirmado_por
                or not fecha_confirmacion
                or not huella_datos
            ):
                return {
                    "estado": "bloqueado",
                    "mensaje": "El contrato no cumple las condiciones."
                }

            # También comprobamos la huella de los datos.
            registro = consultar_registro(contrato_id)

            if registro.get("integridad_confirmada") is not True:
                return {
                    "estado": "bloqueado",
                    "mensaje": "La integridad de los datos es inválida."
                }

            # Calculamos la huella del DOCX real.
            huella_archivo = calcular_huella_archivo(ruta)

            # Asignamos una versión nueva para este contrato.
            fila_version = db.execute(
                """
                SELECT COALESCE(MAX(version), 0)
                FROM borradores
                WHERE contrato_id = ?
                """,
                (contrato_id,)
            ).fetchone()

            version = fila_version[0] + 1

            fecha = datetime.now(timezone.utc).isoformat()

            # Registramos la versión del documento.
            cursor = db.execute(
                """
                INSERT INTO borradores (
                    contrato_id,
                    version,
                    archivo,
                    fecha_generacion,
                    huella_archivo,
                    huella_datos,
                    huella_plantilla,
                    confirmado_por
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    contrato_id,
                    version,
                    ruta.name,
                    fecha,
                    huella_archivo,
                    huella_datos,
                    huella_plantilla.upper(),
                    confirmado_por
                )
            )

            identificador = cursor.lastrowid

            db.commit()

        return {
            "estado": "registrado",
            "borrador_id": identificador,
            "contrato_id": contrato_id,
            "version": version,
            "archivo": ruta.name,
            "fecha_generacion": fecha,
            "huella_archivo": huella_archivo
        }

    except (OSError, sqlite3.Error, ValueError, TypeError):
        return {
            "estado": "error",
            "mensaje": "No se pudo registrar el borrador."
        }


def verificar_borrador(borrador_id: int) -> dict:
    """
    Comprueba que un DOCX registrado conserve
    exactamente el contenido de su versión original.
    """

    if type(borrador_id) is not int or borrador_id <= 0:
        return {
            "estado": "bloqueado",
            "mensaje": "Identificador de borrador inválido."
        }

    try:
        inicializar_auditoria()

        with conectar() as db:

            fila = db.execute(
                """
                SELECT
                    contrato_id,
                    version,
                    archivo,
                    huella_archivo
                FROM borradores
                WHERE id = ?
                """,
                (borrador_id,)
            ).fetchone()

        if fila is None:
            return {
                "estado": "no_encontrado",
                "mensaje": "El borrador no está registrado."
            }

        contrato_id, version, archivo, huella_guardada = fila

        ruta = CARPETA_BORRADORES / archivo

        # No seguimos si se eliminó el documento.
        if not ruta.is_file():
            return {
                "estado": "bloqueado",
                "mensaje": "El archivo registrado ya no existe."
            }

        huella_actual = calcular_huella_archivo(ruta)

        if huella_actual != huella_guardada:
            return {
                "estado": "bloqueado",
                "mensaje": "El DOCX fue modificado.",
                "integridad": False
            }

        return {
            "estado": "integro",
            "borrador_id": borrador_id,
            "contrato_id": contrato_id,
            "version": version,
            "archivo": archivo,
            "integridad": True
        }

    except (OSError, sqlite3.Error):
        return {
            "estado": "error",
            "mensaje": "No se pudo verificar el borrador."
        }
