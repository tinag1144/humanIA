
"""
HumanIA - Servicio de aprobaciones y confirmaciones humanas.

Responsabilidades:
1. Verificar la identidad autorizada por el backend.
2. Resolver contradicciones contractuales.
3. Confirmar integralmente los datos.
4. Aprobar o rechazar versiones auditadas de borradores.

Las decisiones humanas NO son herramientas del agente de IA.
La autenticación real se realiza previamente en FastAPI.
"""

import hashlib
import json
import sqlite3

from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path

from pydantic import ValidationError

from humania.modelos.contrato import DatosContrato

from humania.servicios.estado_contrato import (
    conectar,
    inicializar_base,
    calcular_huella
)

from humania.seguridad.auditoria import (
    calcular_huella_archivo,
    inicializar_auditoria
)


# ============================================================
# CONFIGURACIÓN GENERAL
# ============================================================

RAIZ_PROYECTO = Path(__file__).resolve().parents[2]

CARPETA_BORRADORES = (
    RAIZ_PROYECTO / "contratos_generados"
)

# Las versiones antiguas siguen verificandose con su propia huella.
# La v2 solo debe activarse para nuevos borradores tras revision autorizada.
PLANTILLAS_POR_HUELLA = {
    "6AE8D8481DC599F41706876DAA6EEC295399E4DFB9514791E3625F1E3D0274E8": RAIZ_PROYECTO / "plantillas" / "indeterminado_v1.docx",
    "632127B239A1C86F2BFF3D166C5392B1AE8B00C95D1967DA272D74706CB6B7D4": RAIZ_PROYECTO / "plantillas" / "indeterminado_v2.docx",
}


# Campos necesarios para confirmar un contrato.
CAMPOS_OBLIGATORIOS = (
    "tipo_contrato",
    "empleador",
    "cuit_empleador",
    "domicilio_empleador",
    "nombre_empleado",
    "dni_empleado",
    "fecha_nacimiento",
    "domicilio_empleado",
    "puesto",
    "fecha_inicio",
    "jornada_laboral",
    "remuneracion_bruta",
    "lugar_trabajo",
)


# ============================================================
# 1. VERIFICACIÓN DEL RESPONSABLE
# ============================================================

def usuario_rrhh_valido(usuario: dict) -> bool:
    """
    Comprueba que los datos de identidad recibidos
    correspondan a un responsable de Recursos Humanos.

    IMPORTANTE:
    Esta función NO autentica por sí misma.
    FastAPI debe validar el token antes de llamarla.
    """

    return (
        isinstance(usuario, dict)
        and usuario.get("rol") == "rrhh"
        and type(usuario.get("id")) is int
        and usuario["id"] > 0
        and isinstance(usuario.get("usuario"), str)
        and bool(usuario["usuario"].strip())
    )


# ============================================================
# 2. CONFIRMACIÓN DE DATOS CONTRADICTORIOS
# ============================================================

def confirmar_dato(
    contrato_id: str,
    campo: str,
    fuente_elegida: str,
    usuario_actual: dict
) -> dict:
    """
    Permite resolver una contradicción entre un documento
    y la información proporcionada por RR. HH.

    Solo acepta valores que ya estaban registrados.

    No confirma integralmente ni aprueba el contrato.
    """

    # Verificamos los datos del responsable.
    if not usuario_rrhh_valido(usuario_actual):
        return {
            "estado": "bloqueado",
            "mensaje": "Usuario sin autorización."
        }

    # Validamos el identificador contractual.
    if (
        not isinstance(contrato_id, str)
        or not contrato_id.strip()
    ):
        return {
            "estado": "error",
            "mensaje": "Identificador inválido."
        }

    # Comprobamos que el campo exista en el modelo.
    if campo not in DatosContrato.model_fields:
        return {
            "estado": "error",
            "mensaje": "Campo contractual desconocido."
        }

    # Solo admitimos fuentes reconocidas.
    if fuente_elegida not in ("documento", "usuario"):
        return {
            "estado": "error",
            "mensaje": "Fuente inválida."
        }

    try:
        inicializar_base()

        with closing(conectar()) as db:

            # Creamos la tabla histórica si no existe.
            db.execute("""
                CREATE TABLE IF NOT EXISTS confirmaciones (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    contrato_id TEXT NOT NULL,
                    campo TEXT NOT NULL,
                    fuente TEXT NOT NULL,
                    valor TEXT NOT NULL,
                    usuario_id INTEGER NOT NULL,
                    fecha TEXT NOT NULL
                )
            """)

            # Bloqueamos escrituras concurrentes.
            db.execute("BEGIN IMMEDIATE")

            fila = db.execute(
                """
                SELECT
                    estado,
                    datos,
                    inconsistencias
                FROM contratos
                WHERE id = ?
                """,
                (contrato_id,)
            ).fetchone()

            if fila is None:
                return {
                    "estado": "no_encontrado",
                    "mensaje": "El contrato no existe."
                }

            estado, datos_json, conflictos_json = fila

            # Solo pueden resolverse contratos en conflicto.
            if estado != "en_conflicto":
                return {
                    "estado": "bloqueado",
                    "mensaje": (
                        "El contrato no tiene conflictos "
                        "pendientes."
                    )
                }

            datos = json.loads(datos_json)
            conflictos = json.loads(conflictos_json)

            # Buscamos la contradicción del campo solicitado.
            conflicto_encontrado = next(
                (
                    item
                    for item in conflictos
                    if item.get("campo") == campo
                ),
                None
            )

            if conflicto_encontrado is None:
                return {
                    "estado": "error",
                    "mensaje": (
                        "No existe un conflicto para ese campo."
                    )
                }

            # Seleccionamos un valor existente.
            clave_valor = (
                "valor_documento"
                if fuente_elegida == "documento"
                else "valor_usuario"
            )

            valor = conflicto_encontrado.get(clave_valor)

            if valor is None or (
                isinstance(valor, str)
                and not valor.strip()
            ):
                return {
                    "estado": "error",
                    "mensaje": (
                        "La fuente seleccionada no contiene datos."
                    )
                }

            # Aplicamos el valor seleccionado.
            datos[campo] = valor

            # Volvemos a validar la estructura contractual.
            contrato = DatosContrato.model_validate(datos)

            datos_validados = contrato.model_dump(mode="json")

            # Quitamos exclusivamente el conflicto resuelto.
            pendientes = [
                item
                for item in conflictos
                if item.get("campo") != campo
            ]

            nuevo_estado = (
                "en_conflicto"
                if pendientes
                else "pendiente_confirmacion"
            )

            # Invalidamos confirmaciones anteriores.
            db.execute(
                """
                UPDATE contratos
                SET
                    estado = ?,
                    datos = ?,
                    inconsistencias = ?,
                    aprobado_por = NULL,
                    fecha_aprobacion = NULL,
                    confirmado_por = NULL,
                    fecha_confirmacion = NULL,
                    huella_confirmacion = NULL
                WHERE id = ?
                """,
                (
                    nuevo_estado,
                    json.dumps(
                        datos_validados,
                        ensure_ascii=False
                    ),
                    json.dumps(
                        pendientes,
                        ensure_ascii=False
                    ),
                    contrato_id
                )
            )

            fecha = datetime.now(
                timezone.utc
            ).isoformat()

            # Registramos la decisión.
            db.execute(
                """
                INSERT INTO confirmaciones (
                    contrato_id,
                    campo,
                    fuente,
                    valor,
                    usuario_id,
                    fecha
                )
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    contrato_id,
                    campo,
                    fuente_elegida,
                    json.dumps(
                        valor,
                        ensure_ascii=False
                    ),
                    usuario_actual["id"],
                    fecha
                )
            )

            db.commit()

        return {
            "estado": nuevo_estado,
            "contrato_id": contrato_id,
            "campo_confirmado": campo,
            "fuente_elegida": fuente_elegida,
            "valor": valor,
            "confirmado_por": usuario_actual["usuario"],
            "fecha": fecha,
            "mensaje": (
                "Contradicción resuelta por RR. HH. "
                "El contrato continúa sin aprobación final."
            )
        }

    except (
        sqlite3.Error,
        ValidationError,
        ValueError,
        KeyError,
        TypeError,
        AttributeError
    ):
        return {
            "estado": "error",
            "mensaje": "No se pudo confirmar el dato."
        }


# ============================================================
# 3. CONFIRMACIÓN INTEGRAL DEL CONTRATO
# ============================================================

def confirmar_datos_completos(
    contrato_id: str,
    usuario_actual: dict
) -> dict:
    """
    Confirma todos los datos de un contrato.

    Requisitos:
    - Responsable autorizado.
    - Datos completos.
    - Sin contradicciones.
    - Sin aprobación previa.

    Registra una huella SHA-256 de los datos confirmados.
    """

    if not usuario_rrhh_valido(usuario_actual):
        return {
            "estado": "bloqueado",
            "mensaje": "Usuario sin autorización."
        }

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

        with closing(conectar()) as db:

            # Tabla para registrar confirmaciones integrales.
            db.execute("""
                CREATE TABLE IF NOT EXISTS
                confirmaciones_integrales (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    contrato_id TEXT NOT NULL,
                    usuario_id INTEGER NOT NULL,
                    usuario TEXT NOT NULL,
                    fecha TEXT NOT NULL,
                    huella TEXT NOT NULL
                )
            """)

            # Comenzamos una transacción de escritura.
            db.execute("BEGIN IMMEDIATE")

            fila = db.execute(
                """
                SELECT
                    estado,
                    datos,
                    inconsistencias,
                    aprobado_por,
                    fecha_aprobacion
                FROM contratos
                WHERE id = ?
                """,
                (contrato_id,)
            ).fetchone()

            if fila is None:
                return {
                    "estado": "no_encontrado",
                    "mensaje": "El contrato no existe."
                }

            (
                estado,
                datos_json,
                conflictos_json,
                aprobado_por,
                fecha_aprobacion
            ) = fila

            # Solo confirmamos contratos pendientes.
            if estado != "pendiente_confirmacion":
                return {
                    "estado": "bloqueado",
                    "mensaje": (
                        "El contrato no está pendiente "
                        "de confirmación integral."
                    )
                }

            if (
                aprobado_por is not None
                or fecha_aprobacion is not None
            ):
                return {
                    "estado": "bloqueado",
                    "mensaje": (
                        "El contrato ya tiene datos de aprobación."
                    )
                }

            conflictos = json.loads(conflictos_json)

            if not isinstance(conflictos, list) or conflictos:
                return {
                    "estado": "bloqueado",
                    "mensaje": "Existen contradicciones pendientes."
                }

            datos_originales = json.loads(datos_json)

            if not isinstance(datos_originales, dict):
                return {
                    "estado": "bloqueado",
                    "mensaje": "Los datos almacenados son inválidos."
                }

            # Validación mediante nuestro modelo Pydantic.
            contrato = DatosContrato.model_validate(
                datos_originales
            )

            datos = contrato.model_dump(mode="json")

            # Comprobamos todos los campos obligatorios.
            faltantes = []

            for campo in CAMPOS_OBLIGATORIOS:

                valor = datos.get(campo)

                if valor is None or (
                    isinstance(valor, str)
                    and not valor.strip()
                ):
                    faltantes.append(campo)

            if faltantes:
                return {
                    "estado": "bloqueado",
                    "mensaje": "Faltan datos obligatorios.",
                    "campos_faltantes": faltantes
                }

            # Calculamos la huella sobre los datos
            # efectivamente almacenados.
            huella = calcular_huella(datos_originales)

            fecha = datetime.now(
                timezone.utc
            ).isoformat()

            # Marcamos los datos como confirmados.
            db.execute(
                """
                UPDATE contratos
                SET
                    estado = ?,
                    confirmado_por = ?,
                    fecha_confirmacion = ?,
                    huella_confirmacion = ?
                WHERE id = ?
                """,
                (
                    "datos_confirmados",
                    usuario_actual["usuario"],
                    fecha,
                    huella,
                    contrato_id
                )
            )

            # Guardamos la confirmación en el historial.
            db.execute(
                """
                INSERT INTO confirmaciones_integrales (
                    contrato_id,
                    usuario_id,
                    usuario,
                    fecha,
                    huella
                )
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    contrato_id,
                    usuario_actual["id"],
                    usuario_actual["usuario"],
                    fecha,
                    huella
                )
            )

            db.commit()

        return {
            "estado": "datos_confirmados",
            "contrato_id": contrato_id,
            "confirmado_por": usuario_actual["usuario"],
            "fecha_confirmacion": fecha,
            "integridad_confirmada": True,
            "mensaje": (
                "Los datos fueron confirmados por RR. HH. "
                "El contrato todavía no está aprobado."
            )
        }

    except ValidationError:
        return {
            "estado": "bloqueado",
            "mensaje": "El contrato contiene datos inválidos."
        }

    except (
        sqlite3.Error,
        ValueError,
        TypeError,
        KeyError,
        AttributeError
    ):
        return {
            "estado": "error",
            "mensaje": "No se pudo confirmar el contrato."
        }


# ============================================================
# 4. APROBACIÓN O RECHAZO HUMANO DE UN BORRADOR
# ============================================================

def decidir_borrador(
    borrador_id: int,
    decision: str,
    motivo: str,
    usuario_actual: dict
) -> dict:
    """
    Registra una decisión humana sobre una versión DOCX.

    Verifica:
    - Responsable autorizado por FastAPI.
    - Borrador registrado en auditoría.
    - Última versión del contrato.
    - Integridad del archivo DOCX.
    - Integridad de los datos confirmados.
    - Integridad de la plantilla de referencia.
    - Ausencia de decisiones anteriores.

    No genera firmas ni modifica el documento.
    """

    # --------------------------------------------------------
    # 4.1. VALIDACIÓN DE ENTRADA
    # --------------------------------------------------------

    if not usuario_rrhh_valido(usuario_actual):
        return {
            "estado": "bloqueado",
            "mensaje": "Responsable sin autorización."
        }

    if type(borrador_id) is not int or borrador_id <= 0:
        return {
            "estado": "bloqueado",
            "mensaje": "Identificador de borrador inválido."
        }

    if decision not in ("aprobar", "rechazar"):
        return {
            "estado": "bloqueado",
            "mensaje": "Decisión no permitida."
        }

    if not isinstance(motivo, str) or len(motivo) > 1000:
        return {
            "estado": "bloqueado",
            "mensaje": "Motivo inválido."
        }

    motivo = motivo.strip()

    # Los rechazos deben explicar el motivo.
    if decision == "rechazar" and len(motivo) < 10:
        return {
            "estado": "bloqueado",
            "mensaje": (
                "El rechazo debe incluir un motivo "
                "de al menos 10 caracteres."
            )
        }

    try:
        # Creamos las tablas necesarias si no existen.
        # Esto se hace antes de iniciar la transacción.
        inicializar_auditoria()

        with closing(conectar()) as db:

            db.execute("""
                CREATE TABLE IF NOT EXISTS decisiones_borrador (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    contrato_id TEXT NOT NULL UNIQUE,
                    borrador_id INTEGER NOT NULL UNIQUE,
                    decision TEXT NOT NULL,
                    motivo TEXT NOT NULL,
                    usuario_id INTEGER NOT NULL,
                    usuario TEXT NOT NULL,
                    fecha TEXT NOT NULL,
                    huella_archivo TEXT NOT NULL,
                    huella_datos TEXT NOT NULL,
                    huella_plantilla TEXT NOT NULL
                )
            """)

            # Transacción para impedir decisiones concurrentes.
            db.execute("BEGIN IMMEDIATE")

            # ------------------------------------------------
            # 4.2. OBTENER LA VERSIÓN AUDITADA
            # ------------------------------------------------

            fila_borrador = db.execute(
                """
                SELECT
                    contrato_id,
                    version,
                    archivo,
                    huella_archivo,
                    huella_datos,
                    huella_plantilla
                FROM borradores
                WHERE id = ?
                """,
                (borrador_id,)
            ).fetchone()

            if fila_borrador is None:
                return {
                    "estado": "no_encontrado",
                    "mensaje": "El borrador no está registrado."
                }

            (
                contrato_id,
                version,
                nombre_archivo,
                huella_archivo,
                huella_datos,
                huella_plantilla
            ) = fila_borrador

            # ------------------------------------------------
            # 4.3. OBTENER EL CONTRATO ASOCIADO
            # ------------------------------------------------

            fila_contrato = db.execute(
                """
                SELECT
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

            if fila_contrato is None:
                return {
                    "estado": "bloqueado",
                    "mensaje": "El contrato asociado no existe."
                }

            (
                estado_contrato,
                datos_json,
                inconsistencias_json,
                aprobado_por,
                fecha_aprobacion,
                confirmado_por,
                fecha_confirmacion,
                huella_confirmacion
            ) = fila_contrato

            # ------------------------------------------------
            # 4.4. VALIDAR EL ESTADO CONTRACTUAL
            # ------------------------------------------------

            if estado_contrato != "datos_confirmados":
                return {
                    "estado": "bloqueado",
                    "mensaje": (
                        "El contrato no está en estado "
                        "datos_confirmados."
                    )
                }

            if (
                aprobado_por is not None
                or fecha_aprobacion is not None
            ):
                return {
                    "estado": "bloqueado",
                    "mensaje": "El contrato ya tiene aprobación."
                }

            if not confirmado_por or not fecha_confirmacion:
                return {
                    "estado": "bloqueado",
                    "mensaje": "Falta la confirmación integral."
                }

            inconsistencias = json.loads(
                inconsistencias_json
            )

            if inconsistencias != []:
                return {
                    "estado": "bloqueado",
                    "mensaje": "Existen inconsistencias pendientes."
                }

            # ------------------------------------------------
            # 4.5. VALIDAR LA INTEGRIDAD DE LOS DATOS
            # ------------------------------------------------

            datos = json.loads(datos_json)

            huella_actual_datos = calcular_huella(datos)

            if (
                huella_actual_datos != huella_confirmacion
                or huella_actual_datos != huella_datos
            ):
                return {
                    "estado": "bloqueado",
                    "mensaje": (
                        "Los datos del contrato cambiaron "
                        "después de la confirmación."
                    )
                }

            # ------------------------------------------------
            # 4.6. COMPROBAR LA VERSIÓN
            # ------------------------------------------------

            ultima_version = db.execute(
                """
                SELECT MAX(version)
                FROM borradores
                WHERE contrato_id = ?
                """,
                (contrato_id,)
            ).fetchone()[0]

            if version != ultima_version:
                return {
                    "estado": "bloqueado",
                    "mensaje": (
                        "Existe una versión más reciente "
                        "del borrador."
                    )
                }

            # ------------------------------------------------
            # 4.7. COMPROBAR LA INTEGRIDAD DEL DOCX
            # ------------------------------------------------

            # Solo admitimos nombres de archivo,
            # no rutas indicadas por el usuario.
            if (
                not isinstance(nombre_archivo, str)
                or Path(nombre_archivo).name != nombre_archivo
                or not nombre_archivo.endswith(".docx")
            ):
                return {
                    "estado": "bloqueado",
                    "mensaje": "Nombre de documento inválido."
                }

            ruta_documento = (
                CARPETA_BORRADORES / nombre_archivo
            )

            if not ruta_documento.is_file():
                return {
                    "estado": "bloqueado",
                    "mensaje": "El DOCX ya no existe."
                }

            huella_actual_archivo = calcular_huella_archivo(
                ruta_documento
            )

            if huella_actual_archivo != huella_archivo:
                return {
                    "estado": "bloqueado",
                    "mensaje": (
                        "El documento fue modificado "
                        "después de su generación."
                    )
                }

            # ------------------------------------------------
            # 4.8. COMPROBAR LA PLANTILLA
            # ------------------------------------------------

            huella_registrada = str(huella_plantilla).upper()
            archivo_plantilla = PLANTILLAS_POR_HUELLA.get(huella_registrada)

            if archivo_plantilla is None:
                return {
                    "estado": "bloqueado",
                    "mensaje": "La version de plantilla no esta autorizada."
                }

            if not archivo_plantilla.is_file():
                return {
                    "estado": "bloqueado",
                    "mensaje": "La plantilla de esta version no existe."
                }

            huella_actual_plantilla = hashlib.sha256(
                archivo_plantilla.read_bytes()
            ).hexdigest().upper()

            if huella_actual_plantilla != huella_registrada:
                return {
                    "estado": "bloqueado",
                    "mensaje": "La plantilla fue modificada desde la generacion."
                }

            # ------------------------------------------------
            # 4.9. REGISTRAR LA DECISIÓN HUMANA
            # ------------------------------------------------

            fecha = datetime.now(
                timezone.utc
            ).isoformat()

            # Solo permitimos una decisión final por contrato.
            db.execute(
                """
                INSERT INTO decisiones_borrador (
                    contrato_id,
                    borrador_id,
                    decision,
                    motivo,
                    usuario_id,
                    usuario,
                    fecha,
                    huella_archivo,
                    huella_datos,
                    huella_plantilla
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    contrato_id,
                    borrador_id,
                    decision,
                    motivo,
                    usuario_actual["id"],
                    usuario_actual["usuario"],
                    fecha,
                    huella_archivo,
                    huella_datos,
                    huella_plantilla
                )
            )

            # ------------------------------------------------
            # 4.10. ACTUALIZAR EL ESTADO DEL CONTRATO
            # ------------------------------------------------

            if decision == "aprobar":

                nuevo_estado = "aprobado"

                db.execute(
                    """
                    UPDATE contratos
                    SET
                        estado = ?,
                        aprobado_por = ?,
                        fecha_aprobacion = ?
                    WHERE id = ?
                    """,
                    (
                        nuevo_estado,
                        usuario_actual["usuario"],
                        fecha,
                        contrato_id
                    )
                )

            else:

                nuevo_estado = "rechazado"

                db.execute(
                    """
                    UPDATE contratos
                    SET
                        estado = ?,
                        aprobado_por = NULL,
                        fecha_aprobacion = NULL
                    WHERE id = ?
                    """,
                    (
                        nuevo_estado,
                        contrato_id
                    )
                )

            # Guardamos la decisión y el estado juntos.
            db.commit()

        return {
            "estado": nuevo_estado,
            "contrato_id": contrato_id,
            "borrador_id": borrador_id,
            "version": version,
            "decision": decision,
            "decidido_por": usuario_actual["usuario"],
            "fecha": fecha,
            "integridad": True,
            "mensaje": (
                "Decisión humana registrada correctamente. "
                "No se realizó ninguna firma digital."
            )
        }

    except (
        sqlite3.Error,
        OSError,
        ValueError,
        TypeError,
        KeyError,
        AttributeError
    ):
        return {
            "estado": "error",
            "mensaje": "No se pudo registrar la decisión."
        }
