
# Herramientas de seguridad y almacenamiento.
import hashlib
import hmac
import secrets
import sqlite3

from datetime import datetime, timedelta, timezone
from getpass import getpass

# Reutilizamos la ubicación de SQLite del proyecto.
from humania.servicios.estado_contrato import (
    conectar
)


# Número de iteraciones para proteger contraseñas.
ITERACIONES = 600000


def inicializar_usuarios():
    """
    Crea las tablas de usuarios y sesiones.
    """

    with conectar() as db:

        db.execute("""
            CREATE TABLE IF NOT EXISTS usuarios (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                usuario TEXT UNIQUE NOT NULL,
                sal BLOB NOT NULL,
                clave_hash BLOB NOT NULL,
                rol TEXT NOT NULL
            )
        """)

        db.execute("""
            CREATE TABLE IF NOT EXISTS sesiones (
                token_hash TEXT PRIMARY KEY,
                usuario_id INTEGER NOT NULL,
                vencimiento TEXT NOT NULL,
                FOREIGN KEY(usuario_id) REFERENCES usuarios(id)
            )
        """)

        db.commit()


def calcular_hash(clave: str, sal: bytes) -> bytes:
    """
    Deriva una clave protegida a partir de una contraseña.
    """

    return hashlib.pbkdf2_hmac(
        "sha256",
        clave.encode("utf-8"),
        sal,
        ITERACIONES
    )


def crear_responsable(usuario: str, clave: str) -> dict:
    """
    Crea el primer responsable de prueba.

    No existe un endpoint público para registrar usuarios.
    """

    if not isinstance(usuario, str):
        return {"estado": "error", "mensaje": "Usuario inválido."}

    usuario = usuario.strip().lower()

    if not usuario or len(usuario) > 50:
        return {"estado": "error", "mensaje": "Usuario inválido."}

    if not isinstance(clave, str) or not 12 <= len(clave) <= 128:
        return {
            "estado": "error",
            "mensaje": "La contraseña debe tener entre 12 y 128 caracteres."
        }

    inicializar_usuarios()

    # Generamos una sal diferente para la contraseña.
    sal = secrets.token_bytes(16)
    clave_hash = calcular_hash(clave, sal)

    try:
        with conectar() as db:

            # Esta función solo permite crear el primer usuario.
            total = db.execute(
                "SELECT COUNT(*) FROM usuarios"
            ).fetchone()[0]

            if total != 0:
                return {
                    "estado": "error",
                    "mensaje": "Ya existe un usuario. Registro cerrado."
                }

            db.execute(
                """
                INSERT INTO usuarios
                (usuario, sal, clave_hash, rol)
                VALUES (?, ?, ?, ?)
                """,
                (usuario, sal, clave_hash, "rrhh")
            )

            db.commit()

        return {
            "estado": "correcto",
            "mensaje": "Responsable creado."
        }

    except sqlite3.Error:
        return {
            "estado": "error",
            "mensaje": "No se pudo crear el usuario."
        }


def iniciar_sesion(usuario: str, clave: str) -> dict:
    """
    Verifica las credenciales y crea un token temporal.
    """

    if not isinstance(usuario, str) or not isinstance(clave, str):
        return {"estado": "error", "mensaje": "Credenciales inválidas."}

    inicializar_usuarios()

    with conectar() as db:
        fila = db.execute(
            """
            SELECT id, usuario, sal, clave_hash, rol
            FROM usuarios
            WHERE usuario = ?
            """,
            (usuario.strip().lower(),)
        ).fetchone()

    if fila is None:
        return {"estado": "error", "mensaje": "Credenciales inválidas."}

    usuario_id, nombre, sal, hash_guardado, rol = fila

    if not hmac.compare_digest(
        calcular_hash(clave, sal),
        hash_guardado
    ):
        return {"estado": "error", "mensaje": "Credenciales inválidas."}

    # Creamos un token aleatorio.
    token = secrets.token_urlsafe(32)

    # Solo guardamos su hash en la base.
    token_hash = hashlib.sha256(
        token.encode("utf-8")
    ).hexdigest()

    # La sesión dura una hora.
    vencimiento = datetime.now(timezone.utc) + timedelta(hours=1)

    with conectar() as db:
        db.execute(
            """
            INSERT INTO sesiones
            (token_hash, usuario_id, vencimiento)
            VALUES (?, ?, ?)
            """,
            (token_hash, usuario_id, vencimiento.isoformat())
        )

        db.commit()

    return {
        "estado": "correcto",
        "access_token": token,
        "token_type": "bearer",
        "expires_in": 3600,
        "rol": rol
    }


def verificar_token(token: str) -> dict | None:
    """
    Comprueba que un token exista y no haya vencido.
    """

    if not isinstance(token, str) or not token:
        return None

    token_hash = hashlib.sha256(
        token.encode("utf-8")
    ).hexdigest()

    with conectar() as db:
        fila = db.execute(
            """
            SELECT u.id, u.usuario, u.rol, s.vencimiento
            FROM sesiones s
            JOIN usuarios u ON u.id = s.usuario_id
            WHERE s.token_hash = ?
            """,
            (token_hash,)
        ).fetchone()

    if fila is None:
        return None

    usuario_id, nombre, rol, vencimiento = fila

    if datetime.now(timezone.utc) >= datetime.fromisoformat(vencimiento):
        return None

    return {
        "id": usuario_id,
        "usuario": nombre,
        "rol": rol
    }


# Ejecutamos este bloque solo cuando iniciamos el archivo
# como programa, no cuando lo importamos desde la API.
if __name__ == "__main__":

    nombre = input("Nombre de usuario de RR. HH.: ")
    clave = getpass("Contraseña (mínimo 12 caracteres): ")

    resultado = crear_responsable(nombre, clave)

    print(resultado["mensaje"])
