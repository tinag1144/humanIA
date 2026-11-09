"""Historial persistente de conversaciones por usuario de RR. HH.

Almacena solo el contenido conversacional; nunca adjuntos binarios.
El historial es independiente de las sesiones efímeras de ADK.
"""
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from api.main import requerir_rrhh

DB = Path(__file__).resolve().parents[1] / "datos" / "historial_chat.db"
router = APIRouter(prefix="/api/historial", tags=["Historial HumanIA"])


class MensajeGuardado(BaseModel):
    role: str = Field(pattern="^(user|agent)$")
    text: str = Field(min_length=1, max_length=18000)
    herramientas: list[str] = Field(default_factory=list, max_length=20)


class GuardarTurno(BaseModel):
    sesion_id: UUID
    titulo: str = Field(min_length=1, max_length=100)
    mensajes: list[MensajeGuardado] = Field(min_length=1, max_length=2)


def conectar():
    DB.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(str(DB), timeout=20)
    db.execute("""CREATE TABLE IF NOT EXISTS sesiones (
        usuario TEXT NOT NULL, sesion TEXT NOT NULL, titulo TEXT NOT NULL,
        actualizado TEXT NOT NULL, PRIMARY KEY(usuario, sesion)
    )""")
    db.execute("""CREATE TABLE IF NOT EXISTS mensajes (
        id INTEGER PRIMARY KEY AUTOINCREMENT, usuario TEXT NOT NULL,
        sesion TEXT NOT NULL, role TEXT NOT NULL, text TEXT NOT NULL,
        herramientas TEXT NOT NULL DEFAULT '[]', fecha TEXT NOT NULL
    )""")
    db.commit()
    return db


def nombre_usuario(usuario: dict) -> str:
    nombre = str(usuario.get("usuario", "")).strip()
    if not nombre:
        raise HTTPException(403, "Usuario no autorizado")
    return nombre


@router.get("")
def listar(usuario: dict = Depends(requerir_rrhh)):
    nombre = nombre_usuario(usuario)
    with conectar() as db:
        filas = db.execute(
            "SELECT sesion, titulo, actualizado FROM sesiones "
            "WHERE usuario=? ORDER BY actualizado DESC LIMIT 100", (nombre,)
        ).fetchall()
    return [{"sesion_id": f[0], "titulo": f[1], "actualizado": f[2]} for f in filas]


@router.get("/{sesion_id}")
def obtener(sesion_id: UUID, usuario: dict = Depends(requerir_rrhh)):
    nombre = nombre_usuario(usuario)
    with conectar() as db:
        existe = db.execute(
            "SELECT titulo FROM sesiones WHERE usuario=? AND sesion=?",
            (nombre, str(sesion_id)),
        ).fetchone()
        if not existe:
            raise HTTPException(404, "Conversación no encontrada")
        mensajes = db.execute(
            "SELECT role, text, herramientas FROM mensajes "
            "WHERE usuario=? AND sesion=? ORDER BY id LIMIT 1000",
            (nombre, str(sesion_id)),
        ).fetchall()
    return {
        "sesion_id": str(sesion_id), "titulo": existe[0],
        "mensajes": [{"role": f[0], "text": f[1], "herramientas": json.loads(f[2])}
                     for f in mensajes],
    }


@router.post("/turno")
def guardar_turno(cuerpo: GuardarTurno, usuario: dict = Depends(requerir_rrhh)):
    nombre = nombre_usuario(usuario)
    momento = datetime.now(timezone.utc).isoformat()
    sesion = str(cuerpo.sesion_id)
    with conectar() as db:
        db.execute(
            "INSERT INTO sesiones(usuario,sesion,titulo,actualizado) "
            "VALUES(?,?,?,?) ON CONFLICT(usuario,sesion) "
            "DO UPDATE SET actualizado=excluded.actualizado",
            (nombre, sesion, cuerpo.titulo.strip(), momento),
        )
        db.executemany(
            "INSERT INTO mensajes(usuario,sesion,role,text,herramientas,fecha) "
            "VALUES(?,?,?,?,?,?)",
            [(nombre, sesion, m.role, m.text,
              json.dumps(m.herramientas, ensure_ascii=False), momento)
             for m in cuerpo.mensajes],
        )
        db.commit()
    return {"guardado": True, "sesion_id": sesion}
