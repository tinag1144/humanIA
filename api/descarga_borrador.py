"""Descarga autenticada y de solo lectura de borradores para revision humana."""
from pathlib import Path
import hashlib

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse

from api.main import requerir_rrhh
from humania.servicios.estado_contrato import conectar

router = APIRouter(tags=["Revision humana de borradores"])
DIRECTORIO = Path(__file__).resolve().parents[1] / "contratos_generados"


def _sha256(ruta: Path) -> str:
    resumen = hashlib.sha256()
    with ruta.open("rb") as archivo:
        for bloque in iter(lambda: archivo.read(1024 * 1024), b""):
            resumen.update(bloque)
    return resumen.hexdigest()


@router.get("/api/borradores/{borrador_id}/revision-docx")
def descargar_borrador_para_revision(
    borrador_id: int,
    usuario: dict = Depends(requerir_rrhh),
):
    """Permite revisar un DOCX sin aprobarlo, alterarlo ni formalizarlo."""
    if borrador_id < 1:
        raise HTTPException(status_code=404, detail="Borrador no encontrado.")

    with conectar() as db:
        fila = db.execute(
            "SELECT archivo, huella_archivo FROM borradores WHERE id = ?",
            (borrador_id,),
        ).fetchone()

    if fila is None:
        raise HTTPException(status_code=404, detail="Borrador no encontrado.")

    nombre, huella_esperada = fila
    if not isinstance(nombre, str) or not nombre or Path(nombre).name != nombre:
        raise HTTPException(status_code=409, detail="Ruta del borrador no valida.")
    if not nombre.lower().endswith(".docx"):
        raise HTTPException(status_code=409, detail="El archivo registrado no es DOCX.")
    if not isinstance(huella_esperada, str) or len(huella_esperada) != 64:
        raise HTTPException(status_code=409, detail="Falta la huella de integridad del borrador.")

    ruta = DIRECTORIO / nombre
    if not ruta.is_file() or ruta.is_symlink():
        raise HTTPException(status_code=404, detail="El archivo DOCX no esta disponible.")
    try:
        huella_actual = _sha256(ruta)
    except OSError:
        raise HTTPException(status_code=500, detail="No se pudo leer el archivo.")
    if huella_actual.lower() != huella_esperada.lower():
        raise HTTPException(status_code=409, detail="El DOCX no supera la verificacion SHA-256.")

    return FileResponse(
        path=str(ruta),
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        filename=f"revision_borrador_{borrador_id}_" + nombre,
        headers={"Cache-Control": "no-store", "X-Content-Type-Options": "nosniff"},
    )
