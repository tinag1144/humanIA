"""Regresión: inicio de HumanIA con una base SQLite recién creada.

Desde la raíz del proyecto:
    python -m unittest pruebas.probar_primera_ejecucion -v
No modifica los datos reales.
"""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from api.frontend_bridge import resumen, listar_contratos, listar_borradores


class PrimeraEjecucion(unittest.TestCase):
    def test_panel_sin_contratos_ni_tablas_previas(self):
        with tempfile.TemporaryDirectory() as temporal:
            ruta = Path(temporal) / "humania.db"
            with patch("humania.servicios.estado_contrato.RUTA_DB", ruta), \
                 patch("humania.servicios.estado_contrato.CARPETA_DATOS", Path(temporal)):
                usuario = {"id": 1, "usuario": "responsable_prueba", "rol": "rrhh"}
                self.assertEqual(listar_contratos(usuario=usuario), [])
                resumen_panel = resumen(usuario=usuario)
                self.assertEqual(resumen_panel["total"], 0)
                self.assertEqual(resumen_panel["borradores"], 0)
                self.assertEqual(
                    listar_borradores("contrato-inexistente", usuario=usuario), []
                )
                # Un segundo acceso debe seguir funcionando; no recrea datos.
                self.assertEqual(resumen(usuario=usuario)["total"], 0)


if __name__ == "__main__":
    unittest.main()
