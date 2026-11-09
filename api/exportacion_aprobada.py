"""Genera copias informativas de documentos aprobados sin modificar el DOCX auditado."""
from io import BytesIO
from datetime import datetime
from docx import Document
from fastapi import HTTPException
from humania.servicios.estado_contrato import conectar


def _reescribir(parrafo, nuevo: str) -> None:
    if not parrafo.runs:
        parrafo.add_run(nuevo)
        return
    parrafo.runs[0].text = nuevo
    for run in parrafo.runs[1:]:
        run.text = ""


def crear_copia_presentacion(contenido_original: bytes, borrador_id: int) -> bytes:
    """Aplica una leyenda de aprobación a una copia temporal; no toca el original."""
    with conectar() as db:
        fila = db.execute(
            """SELECT decision, usuario, fecha
               FROM decisiones_borrador
               WHERE borrador_id = ?""",
            (borrador_id,)
        ).fetchone()

    if not fila or fila[0] != "aprobar" or not fila[1] or not fila[2]:
        raise HTTPException(status_code=409, detail="No existe aprobación humana registrada.")

    _, responsable, fecha = fila
    try:
        etiqueta_fecha = datetime.fromisoformat(
            fecha.replace("Z", "+00:00")
        ).strftime("%d/%m/%Y %H:%M UTC")

        documento = Document(BytesIO(contenido_original))
        encabezados = 0
        aprobaciones = 0

        for seccion in documento.sections:
            for parrafo in seccion.header.paragraphs:
                texto = parrafo.text.upper()
                if "BORRADOR - SIN APROBACION FINAL" in texto or "BORRADOR - SIN APROBACIÓN FINAL" in texto:
                    _reescribir(parrafo, "COPIA DE PRESENTACIÓN - APROBACIÓN INTERNA REGISTRADA")
                    encabezados += 1
            for parrafo in seccion.footer.paragraphs:
                if "Su generación no implica aprobación" in parrafo.text or "Su generación no implica aprobaci" in parrafo.text:
                    _reescribir(
                        parrafo,
                        "Documento ficticio de prueba - Aprobación interna registrada; no constituye firma ni formalización legal."
                    )

        for parrafo in documento.paragraphs:
            texto = parrafo.text.strip()
            if texto.startswith("Datos validados por RR. HH."):
                _reescribir(parrafo, "Datos validados por RR. HH.    Sí (confirmación registrada en el sistema)")
            elif texto.startswith("Responsable que revisó"):
                _reescribir(parrafo, f"Responsable que revisó    {responsable} - {etiqueta_fecha}")
            elif texto.startswith("Aprobación final"):
                _reescribir(parrafo, "Aprobación interna    APROBADO (registro del sistema HumanIA)")
                aprobaciones += 1

        if not encabezados or not aprobaciones:
            raise HTTPException(
                status_code=409,
                detail="Formato del DOCX no reconocido; exportación detenida."
            )

        salida = BytesIO()
        documento.save(salida)
        return salida.getvalue()

    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail="No se pudo preparar la copia aprobada."
        ) from exc
