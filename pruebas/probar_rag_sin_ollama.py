"""Regresión local de integridad RAG sin llamar a Ollama.

    python -m unittest pruebas.probar_rag_sin_ollama -v
"""
import hashlib
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from humania.tools.consultar import similitud_coseno, documento_integro
from humania.seguridad.identificadores import validar_identificador


class PruebasRAGSinOllama(unittest.TestCase):
    def test_similitud_coseno(self):
        self.assertAlmostEqual(similitud_coseno([1, 0], [1, 0]), 1.0)
        self.assertAlmostEqual(similitud_coseno([1, 0], [0, 1]), 0.0)
        self.assertEqual(similitud_coseno([], [1]), 0.0)
        self.assertEqual(similitud_coseno([1], [1, 2]), 0.0)

    def test_fuente_indexada_integra_y_cambio_detectado(self):
        with tempfile.TemporaryDirectory() as temporal:
            carpeta = Path(temporal)
            documento = carpeta / "procedimiento_demo.txt"
            documento.write_text("Política ficticia RRHH", encoding="utf-8")
            huella = hashlib.sha256(documento.read_bytes()).hexdigest()
            with patch("humania.tools.consultar.DOCUMENTOS", carpeta):
                self.assertTrue(documento_integro(documento.name, huella))
                documento.write_text("Texto modificado", encoding="utf-8")
                self.assertFalse(documento_integro(documento.name, huella))
                self.assertFalse(documento_integro("../archivo.txt", huella))

    def test_identificadores_no_comprueban_identidad_real(self):
        self.assertIsNone(validar_identificador("cuit_empleador", "30-00000001-1"))
        self.assertIsNotNone(validar_identificador("cuit_empleador", "30-ABC-9"))


if __name__ == "__main__":
    unittest.main()
