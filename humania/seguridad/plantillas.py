"""Comprobación de integridad de una plantilla histórica, sin modificarla."""
import hashlib
from pathlib import Path

from humania.servicios.contratos import PLANTILLAS_AUTORIZADAS


def verificar_huella_plantilla_aprobada(huella: str) -> bool:
    """Admite v1 y v2 ya autorizadas, cada una únicamente con su SHA-256."""
    if not isinstance(huella, str) or len(huella) != 64:
        return False

    huella = huella.upper()
    for ruta, esperada in PLANTILLAS_AUTORIZADAS.values():
        if huella != esperada.upper():
            continue
        if not isinstance(ruta, Path) or not ruta.is_file() or ruta.is_symlink():
            return False
        try:
            actual = hashlib.sha256(ruta.read_bytes()).hexdigest().upper()
        except OSError:
            return False
        return actual == esperada.upper()
    return False
