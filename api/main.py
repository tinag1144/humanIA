
"""
HumanIA - API de Recursos Humanos.

Incluye:
- Autenticación.
- Consulta y confirmación de datos.
- Aprobación y rechazo humanos.
- Descarga de DOCX aprobados.
- Exportación a PDF.
- Constancia de aprobación humana.

La IA no aprueba, firma ni autoriza documentos.
"""

import hashlib
import json
import sqlite3
import tempfile

from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path
from xml.sax.saxutils import escape

import pythoncom

from docx2pdf import convert
from pypdf import PdfReader
from api.exportacion_aprobada import crear_copia_presentacion

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle
)

from fastapi import FastAPI, Depends, HTTPException
from fastapi.responses import Response

from fastapi.security import (
    HTTPBearer,
    HTTPAuthorizationCredentials
)

from pydantic import BaseModel, ConfigDict, Field

from humania.seguridad.autenticacion import (
    iniciar_sesion,
    verificar_token
)

from humania.servicios.estado_contrato import (
    conectar,
    consultar_registro,
    calcular_huella
)

from humania.servicios.aprobaciones import (
    confirmar_dato,
    confirmar_datos_completos,
    decidir_borrador
)

from humania.seguridad.auditoria import verificar_borrador
from humania.seguridad.plantillas import verificar_huella_plantilla_aprobada

from humania.servicios.contratos import (
    verificar_plantilla,
    HUELLA_PLANTILLA
)


# ============================================================
# CONFIGURACION
# ============================================================

app = FastAPI(
    title="HumanIA - API de Recursos Humanos",
    version="0.7.0"
)

seguridad = HTTPBearer(auto_error=False)

RAIZ = Path(__file__).resolve().parents[1]

CARPETA_BORRADORES = (
    RAIZ / "contratos_generados"
)


# ============================================================
# MODELOS
# ============================================================

class Credenciales(BaseModel):
    model_config = ConfigDict(extra="forbid")

    usuario: str
    clave: str


class ConfirmacionDato(BaseModel):
    model_config = ConfigDict(extra="forbid")

    campo: str
    fuente_elegida: str


class AprobacionBorrador(BaseModel):
    model_config = ConfigDict(extra="forbid")

    motivo: str = Field(
        default="",
        max_length=1000
    )


class RechazoBorrador(BaseModel):
    model_config = ConfigDict(extra="forbid")

    motivo: str = Field(
        min_length=10,
        max_length=1000
    )


# ============================================================
# AUTENTICACION
# ============================================================

def obtener_usuario_actual(
    credenciales: HTTPAuthorizationCredentials | None = Depends(
        seguridad
    )
) -> dict:

    if credenciales is None:
        raise HTTPException(
            status_code=401,
            detail="Autenticación requerida."
        )

    usuario = verificar_token(
        credenciales.credentials
    )

    if usuario is None:
        raise HTTPException(
            status_code=401,
            detail="Token inválido o vencido."
        )

    return usuario


def requerir_rrhh(
    usuario: dict = Depends(obtener_usuario_actual)
) -> dict:

    if usuario.get("rol") != "rrhh":
        raise HTTPException(
            status_code=403,
            detail="Operación no autorizada."
        )

    return usuario


def comprobar_resultado(resultado: dict) -> dict:

    estado = resultado.get("estado")

    if estado == "no_encontrado":
        raise HTTPException(
            status_code=404,
            detail=resultado.get("mensaje")
        )

    if estado == "bloqueado":
        raise HTTPException(
            status_code=409,
            detail=resultado
        )

    if estado == "error":
        raise HTTPException(
            status_code=400,
            detail=resultado.get("mensaje")
        )

    return resultado


# ============================================================
# ENDPOINTS DE RECURSOS HUMANOS
# ============================================================

@app.get("/api/salud")
def consultar_salud():

    return {
        "estado": "correcto",
        "servicio": "HumanIA"
    }


@app.post("/api/login")
def login(datos: Credenciales):

    resultado = iniciar_sesion(
        datos.usuario,
        datos.clave
    )

    if resultado["estado"] != "correcto":
        raise HTTPException(
            status_code=401,
            detail="Credenciales inválidas."
        )

    return resultado


@app.get("/api/yo")
def consultar_mi_usuario(
    usuario: dict = Depends(obtener_usuario_actual)
):

    return {
        "estado": "autenticado",
        "usuario": usuario["usuario"],
        "rol": usuario["rol"]
    }


@app.get("/api/contratos/{contrato_id}")
def obtener_contrato(
    contrato_id: str,
    usuario: dict = Depends(requerir_rrhh)
):

    return comprobar_resultado(
        consultar_registro(contrato_id)
    )


@app.post("/api/contratos/{contrato_id}/confirmar")
def confirmar_campo(
    contrato_id: str,
    solicitud: ConfirmacionDato,
    usuario: dict = Depends(requerir_rrhh)
):

    return comprobar_resultado(
        confirmar_dato(
            contrato_id=contrato_id,
            campo=solicitud.campo,
            fuente_elegida=solicitud.fuente_elegida,
            usuario_actual=usuario
        )
    )


@app.post("/api/contratos/{contrato_id}/confirmar-datos")
def confirmar_contrato_completo(
    contrato_id: str,
    usuario: dict = Depends(requerir_rrhh)
):

    return comprobar_resultado(
        confirmar_datos_completos(
            contrato_id=contrato_id,
            usuario_actual=usuario
        )
    )


@app.get("/api/borradores/{borrador_id}/verificar")
def consultar_integridad_borrador(
    borrador_id: int,
    usuario: dict = Depends(requerir_rrhh)
):

    return comprobar_resultado(
        verificar_borrador(borrador_id)
    )


@app.post("/api/borradores/{borrador_id}/aprobar")
def aprobar_borrador(
    borrador_id: int,
    solicitud: AprobacionBorrador,
    usuario: dict = Depends(requerir_rrhh)
):

    return comprobar_resultado(
        decidir_borrador(
            borrador_id=borrador_id,
            decision="aprobar",
            motivo=solicitud.motivo,
            usuario_actual=usuario
        )
    )


@app.post("/api/borradores/{borrador_id}/rechazar")
def rechazar_borrador(
    borrador_id: int,
    solicitud: RechazoBorrador,
    usuario: dict = Depends(requerir_rrhh)
):

    return comprobar_resultado(
        decidir_borrador(
            borrador_id=borrador_id,
            decision="rechazar",
            motivo=solicitud.motivo,
            usuario_actual=usuario
        )
    )


# ============================================================
# VALIDACION COMPARTIDA DE DOCUMENTOS APROBADOS
# ============================================================

def obtener_docx_aprobado(
    borrador_id: int
) -> tuple[bytes, str, str]:
    """
    Recupera los bytes de una versión DOCX aprobada.

    Verifica la aprobación, el contrato,
    los datos, la plantilla y el archivo.
    """

    if type(borrador_id) is not int or borrador_id <= 0:
        raise HTTPException(
            status_code=400,
            detail="Identificador inválido."
        )

    try:
        with conectar() as db:

            fila = db.execute(
                """
                SELECT
                    b.archivo,
                    b.huella_archivo,
                    b.huella_datos,
                    b.huella_plantilla,
                    b.contrato_id,
                    c.estado,
                    c.datos,
                    c.inconsistencias,
                    c.aprobado_por,
                    c.fecha_aprobacion,
                    c.huella_confirmacion,
                    d.decision,
                    d.usuario,
                    d.fecha,
                    d.huella_archivo,
                    d.huella_datos,
                    d.huella_plantilla
                FROM borradores b
                JOIN contratos c
                    ON c.id = b.contrato_id
                LEFT JOIN decisiones_borrador d
                    ON d.borrador_id = b.id
                    AND d.contrato_id = c.id
                WHERE b.id = ?
                """,
                (borrador_id,)
            ).fetchone()

        if fila is None:
            raise HTTPException(
                status_code=404,
                detail="Borrador no encontrado."
            )

        (
            nombre,
            huella_docx,
            huella_datos,
            huella_plantilla,
            contrato_id,
            estado,
            datos_json,
            inconsistencias_json,
            aprobado_por,
            fecha_aprobacion,
            huella_confirmacion,
            decision,
            usuario_decision,
            fecha_decision,
            huella_docx_decision,
            huella_datos_decision,
            huella_plantilla_decision
        ) = fila

        # Solo se permite la versión aprobada.
        if (
            estado != "aprobado"
            or decision != "aprobar"
            or not aprobado_por
            or not fecha_aprobacion
            or aprobado_por != usuario_decision
            or fecha_aprobacion != fecha_decision
        ):
            raise HTTPException(
                status_code=409,
                detail="El borrador no está aprobado."
            )

        # Verificamos la integridad de los datos.
        datos = json.loads(datos_json)
        inconsistencias = json.loads(
            inconsistencias_json
        )

        huella_actual_datos = calcular_huella(datos)

        if (
            inconsistencias != []
            or huella_actual_datos != huella_confirmacion
            or huella_actual_datos != huella_datos
            or huella_actual_datos != huella_datos_decision
        ):
            raise HTTPException(
                status_code=409,
                detail="Los datos del contrato fueron modificados."
            )

        # Una versión histórica aprobada puede usar v1 o v2.
        # Cada archivo se verifica contra su propia huella autorizada.
        if (
            not isinstance(huella_plantilla, str)
            or not isinstance(huella_plantilla_decision, str)
            or huella_plantilla.upper() != huella_plantilla_decision.upper()
            or not verificar_huella_plantilla_aprobada(huella_plantilla)
        ):
            raise HTTPException(
                status_code=409,
                detail="La plantilla histórica no conserva su integridad."
            )

        # Impedimos utilizar rutas manipuladas.
        if (
            not isinstance(nombre, str)
            or Path(nombre).name != nombre
            or not nombre.endswith(".docx")
        ):
            raise HTTPException(
                status_code=409,
                detail="Nombre de documento inválido."
            )

        carpeta = CARPETA_BORRADORES.resolve()
        ruta = (carpeta / nombre).resolve()

        if ruta.parent != carpeta:
            raise HTTPException(
                status_code=409,
                detail="Ruta no autorizada."
            )

        if not ruta.is_file():
            raise HTTPException(
                status_code=404,
                detail="El documento ya no existe."
            )

        # Leemos los mismos bytes que serán entregados.
        contenido = ruta.read_bytes()

        huella_actual = hashlib.sha256(
            contenido
        ).hexdigest()

        if (
            huella_actual != huella_docx
            or huella_actual != huella_docx_decision
        ):
            raise HTTPException(
                status_code=409,
                detail="El DOCX aprobado fue modificado."
            )

        return contenido, nombre, contrato_id

    except HTTPException:
        raise

    except (
        sqlite3.Error,
        OSError,
        ValueError,
        TypeError,
        AttributeError
    ):
        raise HTTPException(
            status_code=500,
            detail="No se pudo verificar el documento."
        )


# ============================================================
# DESCARGA DEL DOCX APROBADO
# ============================================================

@app.get("/api/borradores/{borrador_id}/descargar-docx")
def descargar_docx_aprobado(
    borrador_id: int,
    usuario: dict = Depends(requerir_rrhh)
):

    contenido_original, _, _ = obtener_docx_aprobado(
        borrador_id
    )
    contenido = crear_copia_presentacion(contenido_original, borrador_id)

    return Response(
        content=contenido,
        media_type=(
            "application/vnd.openxmlformats-officedocument."
            "wordprocessingml.document"
        ),
        headers={
            "Content-Disposition": (
                f'attachment; filename="copia_aprobada_{borrador_id}.docx"'
            ),
            "Cache-Control": "no-store",
            "X-Content-Type-Options": "nosniff"
        }
    )


# ============================================================
# EXPORTACION A PDF MEDIANTE MICROSOFT WORD
# ============================================================

@app.get("/api/borradores/{borrador_id}/descargar-pdf")
def descargar_pdf_aprobado(
    borrador_id: int,
    usuario: dict = Depends(requerir_rrhh)
):
    """
    Convierte temporalmente a PDF el DOCX aprobado.

    No altera el archivo original.
    """

    contenido_original, _, contrato_id = obtener_docx_aprobado(
        borrador_id
    )
    contenido_docx = crear_copia_presentacion(contenido_original, borrador_id)

    try:
        with tempfile.TemporaryDirectory() as carpeta:

            temporal = Path(carpeta)

            ruta_docx = temporal / "documento.docx"
            ruta_pdf = temporal / "documento.pdf"

            ruta_docx.write_bytes(contenido_docx)

            # Word COM requiere inicialización
            # cuando FastAPI ejecuta la ruta en un hilo.
            pythoncom.CoInitialize()

            try:
                convert(
                    str(ruta_docx),
                    str(ruta_pdf)
                )
            finally:
                pythoncom.CoUninitialize()

            if not ruta_pdf.is_file():
                raise HTTPException(
                    status_code=500,
                    detail="Word no generó el PDF."
                )

            contenido_pdf = ruta_pdf.read_bytes()

            if not contenido_pdf.startswith(b"%PDF-"):
                raise HTTPException(
                    status_code=500,
                    detail="El archivo generado no es un PDF válido."
                )

            lector = PdfReader(str(ruta_pdf))

            if len(lector.pages) == 0:
                raise HTTPException(
                    status_code=500,
                    detail="El PDF no contiene páginas."
                )

        # Calculamos la huella de la exportación concreta.
        huella_pdf = hashlib.sha256(
            contenido_pdf
        ).hexdigest()

        huella_docx = hashlib.sha256(
            contenido_original
        ).hexdigest()

        fecha = datetime.now(timezone.utc).isoformat()

        # Registramos la exportación en SQLite.
        with conectar() as db:

            db.execute("""
                CREATE TABLE IF NOT EXISTS exportaciones_pdf (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    contrato_id TEXT NOT NULL,
                    borrador_id INTEGER NOT NULL,
                    fecha TEXT NOT NULL,
                    usuario TEXT NOT NULL,
                    huella_docx TEXT NOT NULL,
                    huella_pdf TEXT NOT NULL
                )
            """)

            db.execute(
                """
                INSERT INTO exportaciones_pdf (
                    contrato_id,
                    borrador_id,
                    fecha,
                    usuario,
                    huella_docx,
                    huella_pdf
                )
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    contrato_id,
                    borrador_id,
                    fecha,
                    usuario["usuario"],
                    huella_docx,
                    huella_pdf
                )
            )

        return Response(
            content=contenido_pdf,
            media_type="application/pdf",
            headers={
                "Content-Disposition": (
                    "attachment; filename="
                    f'"contrato_aprobado_{borrador_id}.pdf"'
                ),
                "Cache-Control": "no-store",
                "X-Content-Type-Options": "nosniff"
            }
        )

    except HTTPException:
        raise

    except Exception:
        raise HTTPException(
            status_code=500,
            detail="No se pudo exportar el contrato a PDF."
        )


# ============================================================
# ETAPA 24 - CONSTANCIA DE APROBACION HUMANA
# ============================================================

@app.get("/api/borradores/{borrador_id}/constancia-aprobacion")
def descargar_constancia_aprobacion(
    borrador_id: int,
    usuario: dict = Depends(requerir_rrhh)
):
    """
    Genera una constancia PDF separada del contrato.

    No modifica el DOCX aprobado ni representa
    una firma digital.
    """

    # Reutilizamos las comprobaciones anteriores.
    contenido_docx, nombre, contrato_id = obtener_docx_aprobado(
        borrador_id
    )

    try:
        # Recuperamos la decisión humana registrada.
        with conectar() as db:

            fila = db.execute(
                """
                SELECT
                    b.version,
                    d.decision,
                    d.motivo,
                    d.usuario,
                    d.fecha,
                    d.huella_archivo
                FROM borradores b
                JOIN decisiones_borrador d
                    ON d.borrador_id = b.id
                    AND d.contrato_id = b.contrato_id
                WHERE b.id = ?
                """,
                (borrador_id,)
            ).fetchone()

        if fila is None:
            raise HTTPException(
                status_code=409,
                detail="No existe una decisión de aprobación."
            )

        (
            version,
            decision,
            motivo,
            responsable,
            fecha_aprobacion,
            huella_registrada
        ) = fila

        if decision != "aprobar":
            raise HTTPException(
                status_code=409,
                detail="La versión no fue aprobada."
            )

        # Verificamos por última vez el archivo revisado.
        huella_docx = hashlib.sha256(
            contenido_docx
        ).hexdigest()

        if huella_docx != huella_registrada:
            raise HTTPException(
                status_code=409,
                detail="La huella del DOCX no coincide."
            )

        # Convertimos la fecha UTC para presentarla.
        fecha_legible = datetime.fromisoformat(
            fecha_aprobacion
        ).strftime("%d/%m/%Y %H:%M:%S UTC")

        # Creamos el PDF en memoria.
        memoria = BytesIO()

        documento = SimpleDocTemplate(
            memoria,
            pagesize=(21 * cm, 29.7 * cm),
            rightMargin=2 * cm,
            leftMargin=2 * cm,
            topMargin=2.3 * cm,
            bottomMargin=2.3 * cm
        )

        estilos = getSampleStyleSheet()

        titulo = ParagraphStyle(
            "TituloHumanIA",
            parent=estilos["Title"],
            alignment=TA_CENTER,
            fontSize=16,
            leading=21,
            spaceAfter=14
        )

        texto = ParagraphStyle(
            "TextoHumanIA",
            parent=estilos["Normal"],
            fontSize=10,
            leading=15,
            spaceAfter=12
        )

        pequeno = ParagraphStyle(
            "PequenoHumanIA",
            parent=estilos["Normal"],
            fontSize=8,
            leading=12,
            spaceAfter=8,
            wordWrap="CJK"
        )

        elementos = [
            Paragraph(
                "HumanIA S.A.",
                titulo
            ),
            Paragraph(
                "CONSTANCIA DE APROBACIÓN HUMANA",
                titulo
            ),
            Paragraph(
                (
                    "Esta constancia documenta una decisión "
                    "de aprobación registrada en el sistema "
                    "HumanIA sobre una versión específica "
                    "de un contrato laboral ficticio."
                ),
                texto
            )
        ]

        def valor_seguro(valor):
            # Evitamos interpretar valores de la base
            # de datos como etiquetas del PDF.
            return escape(str(valor))

        filas = [
            ["Dato", "Valor"],
            ["Contrato", contrato_id],
            ["Borrador", str(borrador_id)],
            ["Versión", str(version)],
            ["Estado", "APROBADO"],
            ["Responsable", responsable],
            ["Fecha", fecha_legible],
            ["Archivo DOCX", nombre]
        ]

        tabla = Table(
            [
                [
                    Paragraph(valor_seguro(a), pequeno),
                    Paragraph(valor_seguro(b), pequeno)
                ]
                for a, b in filas
            ],
            colWidths=[4.2 * cm, 12.3 * cm],
            repeatRows=1
        )

        tabla.setStyle(TableStyle([
            (
                "BACKGROUND",
                (0, 0),
                (-1, 0),
                colors.HexColor("#E8EDF3")
            ),
            ("GRID", (0, 0), (-1, -1), 0.4, colors.grey),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LEFTPADDING", (0, 0), (-1, -1), 8),
            ("RIGHTPADDING", (0, 0), (-1, -1), 8),
            ("TOPPADDING", (0, 0), (-1, -1), 7),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 7)
        ]))

        elementos.append(tabla)
        elementos.append(Spacer(1, 0.6 * cm))

        elementos.append(
            Paragraph(
                "<b>Motivo de la aprobación</b>",
                texto
            )
        )

        elementos.append(
            Paragraph(
                valor_seguro(motivo or "Sin observaciones registradas."),
                texto
            )
        )

        elementos.append(
            Paragraph(
                "<b>Huella SHA-256 del DOCX aprobado</b>",
                texto
            )
        )

        elementos.append(
            Paragraph(
                valor_seguro(huella_docx),
                pequeno
            )
        )

        elementos.append(Spacer(1, 0.5 * cm))

        elementos.append(
            Paragraph(
                (
                    "<b>Importante:</b> esta constancia "
                    "documenta una aprobación interna "
                    "registrada por HumanIA. No constituye "
                    "una firma digital, no reemplaza el "
                    "documento contractual ni acredita por "
                    "sí sola su formalización legal."
                ),
                pequeno
            )
        )

        documento.build(elementos)

        contenido_pdf = memoria.getvalue()
        memoria.close()

        if not contenido_pdf.startswith(b"%PDF-"):
            raise HTTPException(
                status_code=500,
                detail="No se generó una constancia PDF válida."
            )

        # Registramos esta emisión en SQLite.
        fecha_emision = datetime.now(
            timezone.utc
        ).isoformat()

        huella_constancia = hashlib.sha256(
            contenido_pdf
        ).hexdigest()

        with conectar() as db:

            db.execute("""
                CREATE TABLE IF NOT EXISTS constancias_aprobacion (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    contrato_id TEXT NOT NULL,
                    borrador_id INTEGER NOT NULL,
                    usuario_emision TEXT NOT NULL,
                    fecha_emision TEXT NOT NULL,
                    huella_docx TEXT NOT NULL,
                    huella_constancia TEXT NOT NULL
                )
            """)

            db.execute(
                """
                INSERT INTO constancias_aprobacion (
                    contrato_id,
                    borrador_id,
                    usuario_emision,
                    fecha_emision,
                    huella_docx,
                    huella_constancia
                )
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    contrato_id,
                    borrador_id,
                    usuario["usuario"],
                    fecha_emision,
                    huella_docx,
                    huella_constancia
                )
            )

        # Entregamos la constancia separada.
        return Response(
            content=contenido_pdf,
            media_type="application/pdf",
            headers={
                "Content-Disposition": (
                    "attachment; filename="
                    f'"constancia_aprobacion_{borrador_id}.pdf"'
                ),
                "Cache-Control": "no-store",
                "X-Content-Type-Options": "nosniff"
            }
        )

    except HTTPException:
        raise

    except Exception:
        raise HTTPException(
            status_code=500,
            detail="No se pudo generar la constancia."
        )


# Rutas adicionales para la interfaz web HumanIA.
from api.frontend_bridge import router as frontend_router
app.include_router(frontend_router)

# Flujo contractual conversacional supervisado.
from api.flujo_conversacional import router as flujo_router
app.include_router(flujo_router)

# Descarga autenticada previa a la aprobacion.
from api.descarga_borrador import router as descarga_revision_router
app.include_router(descarga_revision_router)

# Documentos ficticios adjuntos al chat.
from api.adjuntos_chat import router as adjuntos_router
app.include_router(adjuntos_router)

# Historial persistente y autenticado de conversaciones.
from api.historial_chat import router as historial_router
app.include_router(historial_router)
