"""Endpoints adicionales para la interfaz local de HumanIA.

Se incorpora al final de api/main.py sin reemplazar sus rutas existentes.
El agente ADK se comunica exclusivamente mediante una pasarela autenticada.
"""

import json
from datetime import date
from typing import Optional
from urllib.parse import quote
from uuid import UUID, uuid4

import httpx
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, model_validator

from api.main import requerir_rrhh
from humania.modelos.contrato import DatosContrato
from humania.servicios.estado_contrato import conectar, crear_registro
from humania.seguridad.auditoria import inicializar_auditoria
from humania.servicios.contratos import generar_borrador

router = APIRouter(prefix="/api/interfaz", tags=["Interfaz HumanIA"])
ADK_LOCAL = "http://127.0.0.1:8000"


class SolicitudContrato(BaseModel):
    datos: DatosContrato

    @model_validator(mode="after")
    def validar_documentos(self):
        import re

        dni = str(self.datos.dni_empleado).strip()
        cuit = str(self.datos.cuit_empleador).strip()

        if not re.fullmatch(r"(?:[0-9]{7,9}|[0-9]{1,3}(?:\.[0-9]{3}){2})", dni):
            raise ValueError("El DNI solo admite numeros y puntos, con 7 a 9 digitos (9 solo para pruebas ficticias).")
        if not re.fullmatch(r"(?:[0-9]{11}|[0-9]{2}-[0-9]{8}-[0-9])", cuit):
            raise ValueError("El CUIT debe tener exactamente 11 digitos en formato XX-XXXXXXXX-X.")
        return self


class SolicitudBorrador(BaseModel):
    ciudad_firma: str = Field(min_length=2, max_length=100)
    fecha_firma: date


class MensajeChat(BaseModel):
    mensaje: str = Field(min_length=1, max_length=3000)
    sesion_id: Optional[str] = None


def comprobar_sesion(sesion_id: str) -> str:
    try:
        UUID(sesion_id)
        return sesion_id
    except (ValueError, AttributeError):
        raise HTTPException(status_code=422, detail="Identificador de sesión inválido.")


@router.get("/resumen")
def resumen(usuario: dict = Depends(requerir_rrhh)):
    # Primera ejecución: las tablas aún pueden no existir.
    inicializar_auditoria()
    with conectar() as db:
        filas = db.execute("SELECT estado, COUNT(*) FROM contratos GROUP BY estado").fetchall()
        borradores = db.execute("SELECT COUNT(*) FROM borradores").fetchone()[0]
    por_estado = {estado: total for estado, total in filas}
    return {"total": sum(por_estado.values()), "por_estado": por_estado, "borradores": borradores}


@router.get("/contratos")
def listar_contratos(usuario: dict = Depends(requerir_rrhh)):
    inicializar_auditoria()
    with conectar() as db:
        filas = db.execute(
            "SELECT id, estado, datos, aprobado_por, confirmado_por "
            "FROM contratos ORDER BY rowid DESC LIMIT 100"
        ).fetchall()
    return [{
        "id": fila[0], "estado": fila[1],
        "datos": json.loads(fila[2]) if fila[2] else {},
        "aprobado_por": fila[3], "confirmado_por": fila[4]
    } for fila in filas]


@router.post("/contratos", status_code=201)
def nuevo_contrato(solicitud: SolicitudContrato, usuario: dict = Depends(requerir_rrhh)):
    # Solo se registran datos íntegros y explícitos. No confirma ni aprueba.
    return crear_registro(
        datos=solicitud.datos.model_dump(mode="json"),
        inconsistencias=[]
    )


@router.get("/contratos/{contrato_id}/borradores")
def listar_borradores(contrato_id: str, usuario: dict = Depends(requerir_rrhh)):
    inicializar_auditoria()
    with conectar() as db:
        # La tabla de decisiones se crea al realizar la primera aprobación.
        # Antes de eso, devolver los borradores pendientes sin fallar con 500.
        existe_decisiones = db.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='decisiones_borrador'"
        ).fetchone() is not None
        union_decisiones = (
            "LEFT JOIN decisiones_borrador d ON d.borrador_id = b.id"
            if existe_decisiones else ""
        )
        columna_decision = "d.decision" if existe_decisiones else "NULL"
        filas = db.execute(
            f"""SELECT b.id, b.contrato_id, b.version, b.archivo, b.fecha_generacion,
                      {columna_decision}
               FROM borradores b
               {union_decisiones}
               WHERE b.contrato_id = ?
               ORDER BY b.version DESC LIMIT 30""",
            (contrato_id,)
        ).fetchall()
    return [{
        "id": f[0], "contrato_id": f[1], "version": f[2],
        "archivo": f[3], "fecha_generacion": f[4], "decision": f[5]
    } for f in filas]


@router.post("/contratos/{contrato_id}/borradores")
def nuevo_borrador(
    contrato_id: str,
    solicitud: SolicitudBorrador,
    usuario: dict = Depends(requerir_rrhh)
):
    resultado = generar_borrador(
        contrato_id=contrato_id,
        ciudad_firma=solicitud.ciudad_firma,
        fecha_firma=solicitud.fecha_firma
    )
    if resultado.get("estado") != "borrador_generado":
        raise HTTPException(status_code=409, detail=resultado.get("mensaje", "No se pudo generar."))
    return resultado


@router.post("/chat")
def chat(solicitud: MensajeChat, usuario: dict = Depends(requerir_rrhh)):
    """Pasarela hacia ADK: solo el backend autorizado puede acceder al agente.

    ADK debe ejecutarse localmente y no exponerse a redes públicas.
    """
    nombre = str(usuario.get("usuario", ""))
    if not nombre:
        raise HTTPException(status_code=403, detail="Usuario inválido.")
    user_path = quote(nombre, safe="")
    sesion = comprobar_sesion(solicitud.sesion_id) if solicitud.sesion_id else str(uuid4())
    sesion_path = quote(sesion, safe="")
    url_sesion = f"/apps/humania/users/{user_path}/sessions/{sesion_path}"

    try:
        with httpx.Client(base_url=ADK_LOCAL, timeout=180.0) as cliente:
            if solicitud.sesion_id is None:
                creada = cliente.post(url_sesion, json={})
                if not creada.is_success:
                    raise HTTPException(status_code=502, detail="ADK no pudo iniciar la sesión.")
            else:
                existente = cliente.get(url_sesion)
                if not existente.is_success:
                    raise HTTPException(status_code=409, detail="La sesión de chat no existe. Iniciá una nueva.")

            respuesta = cliente.post("/run", json={
                "appName": "humania", "userId": nombre, "sessionId": sesion,
                "newMessage": {"role": "user", "parts": [{"text": solicitud.mensaje}]}
            })
            respuesta.raise_for_status()
            eventos = respuesta.json()
    except HTTPException:
        raise
    except httpx.TimeoutException:
        raise HTTPException(status_code=504, detail="Ollama tardó demasiado en responder.")
    except (httpx.HTTPError, ValueError):
        raise HTTPException(status_code=503, detail="No se pudo consultar el agente ADK local (puerto 8000).")

    if not isinstance(eventos, list):
        raise HTTPException(status_code=502, detail="ADK devolvió un resultado inesperado.")
    mensajes = []
    herramientas = []
    for evento in eventos:
        if not isinstance(evento, dict):
            continue
        partes = (evento.get("content") or {}).get("parts") or []
        for parte in partes:
            if not isinstance(parte, dict):
                continue
            fc = parte.get("functionCall")
            if isinstance(fc, dict) and isinstance(fc.get("name"), str):
                herramientas.append(fc["name"])
            if evento.get("author") == "humania" and isinstance(parte.get("text"), str):
                mensajes.append(parte["text"])
    return {
        "mensaje": mensajes[-1] if mensajes else "El agente no devolvió una respuesta de texto.",
        "sesion_id": sesion,
        "herramientas": list(dict.fromkeys(herramientas))
    }
