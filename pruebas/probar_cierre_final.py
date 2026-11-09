"""Pruebas de regresión de HumanIA que no necesitan Ollama ni Word.

Desde la raíz del repositorio:
    python -m unittest pruebas.probar_cierre_final -v
"""
import hashlib
import io
import sqlite3
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from docx import Document
from fastapi import HTTPException

from humania.seguridad.identificadores import (
    validar_identificador, filtrar_identificadores,
)
from api.exportacion_aprobada import crear_copia_presentacion
from api.adjuntos_chat import (
    extraer_texto_documento, validar_archivo, comparar_y_actualizar,
)


def _docx_ficticio() -> bytes:
    documento = Document()
    documento.sections[0].header.paragraphs[0].text = (
        "BORRADOR - SIN APROBACION FINAL"
    )
    documento.add_heading("CONTRATO DE PRUEBA", level=1)
    documento.add_paragraph("Empleado: Sofía Martínez")
    documento.add_paragraph("Datos validados por RR. HH.    ☐ Sí    ☐ No")
    documento.add_paragraph(
        "Responsable que revisó    Nombre: ______ Fecha: ___"
    )
    documento.add_paragraph(
        "Aprobación final    ☐ Aprobado    ☐ Requiere cambios"
    )
    documento.sections[0].footer.paragraphs[0].text = (
        "Su generación no implica aprobación legal ni formalización."
    )
    memoria = io.BytesIO()
    documento.save(memoria)
    return memoria.getvalue()


class PruebasCierreFinal(unittest.TestCase):
    def setUp(self):
        self.temporal = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporal.cleanup)
        self.ruta_db = Path(self.temporal.name) / "aprobaciones.db"
        with sqlite3.connect(self.ruta_db) as db:
            db.execute(
                """CREATE TABLE decisiones_borrador (
                    borrador_id INTEGER PRIMARY KEY,
                    decision TEXT NOT NULL,
                    usuario TEXT NOT NULL,
                    fecha TEXT NOT NULL
                )"""
            )
            db.execute(
                "INSERT INTO decisiones_borrador VALUES (?, ?, ?, ?)",
                (
                    7, "aprobar", "responsable_prueba",
                    "2026-11-09T04:54:45+00:00",
                ),
            )
            db.execute(
                "INSERT INTO decisiones_borrador VALUES (?, ?, ?, ?)",
                (
                    8, "rechazar", "responsable_prueba",
                    "2026-11-09T04:55:00+00:00",
                ),
            )

    def _conexion(self):
        return sqlite3.connect(self.ruta_db)

    def test_copia_aprobada_no_modifica_original_ni_sha(self):
        original = _docx_ficticio()
        huella = hashlib.sha256(original).hexdigest()
        with patch(
            "api.exportacion_aprobada.conectar",
            side_effect=self._conexion,
        ):
            copia = crear_copia_presentacion(original, 7)
        self.assertEqual(hashlib.sha256(original).hexdigest(), huella)
        self.assertNotEqual(original, copia)

        documento = Document(io.BytesIO(copia))
        self.assertIn(
            "APROBACIÓN INTERNA REGISTRADA",
            documento.sections[0].header.paragraphs[0].text,
        )
        texto = "\n".join(parrafo.text for parrafo in documento.paragraphs)
        self.assertIn("Sofía Martínez", texto)
        self.assertIn("responsable_prueba", texto)
        self.assertIn("APROBADO", texto)
        self.assertNotIn("☐ Aprobado", texto)
        self.assertIn("BORRADOR", Document(io.BytesIO(original)).sections[0].header.paragraphs[0].text)

    def test_rechazo_no_permite_copia_aprobada(self):
        with patch(
            "api.exportacion_aprobada.conectar",
            side_effect=self._conexion,
        ):
            with self.assertRaises(HTTPException) as error:
                crear_copia_presentacion(_docx_ficticio(), 8)
        self.assertEqual(error.exception.status_code, 409)

    def test_borrador_inexistente_no_permite_copia(self):
        with patch(
            "api.exportacion_aprobada.conectar",
            side_effect=self._conexion,
        ):
            with self.assertRaises(HTTPException) as error:
                crear_copia_presentacion(_docx_ficticio(), 999)
        self.assertEqual(error.exception.status_code, 409)

    def test_docx_adjuntado_se_puede_leer(self):
        contenido = _docx_ficticio()
        self.assertEqual(validar_archivo("prueba.docx", contenido), ".docx")
        texto = extraer_texto_documento(contenido, ".docx")
        self.assertIn("Sofía Martínez", texto)

    def test_pdf_adjuntado_se_puede_leer(self):
        from reportlab.pdfgen import canvas
        memoria = io.BytesIO()
        pdf = canvas.Canvas(memoria)
        pdf.drawString(40, 790, "HumanIA prueba PDF 2026")
        pdf.save()
        contenido = memoria.getvalue()
        self.assertEqual(validar_archivo("prueba.pdf", contenido), ".pdf")
        self.assertIn(
            "HumanIA prueba PDF 2026",
            extraer_texto_documento(contenido, ".pdf"),
        )

    def test_rechaza_contenido_disfrazado(self):
        with self.assertRaises(HTTPException) as error:
            validar_archivo("falso.pdf", b"Esto no es un PDF")
        self.assertEqual(error.exception.status_code, 415)

    def test_identificadores_invalidos_se_filtran(self):
        correctos, errores = filtrar_identificadores(
            {"dni_empleado": "ABC1234", "cuit_empleador": "30-ABC-9", "puesto": "Analista"}
        )
        self.assertEqual(correctos, {"puesto": "Analista"})
        self.assertEqual(len(errores), 2)
        self.assertIsNone(validar_identificador("dni_empleado", "00.000.007"))

    def test_contradicciones_requieren_revision(self):
        estado = {
            "datos": {"domicilio_empleado": "Belgrano 320"},
            "conflictos": {},
            "confirmado": True,
        }
        incorporados, conflictos = comparar_y_actualizar(
            estado, {"domicilio_empleado": "Belgrano 450"}
        )
        self.assertEqual(incorporados, [])
        self.assertTrue(conflictos)
        self.assertEqual(estado["datos"]["domicilio_empleado"], "Belgrano 320")
        self.assertFalse(estado["confirmado"])


if __name__ == "__main__":
    unittest.main()
