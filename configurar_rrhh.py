"""Crear el primer responsable de RR. HH. para uso académico local.

Ejecutar una sola vez desde la raíz del proyecto:
    python configurar_rrhh.py

No imprime ni guarda la contraseña en texto plano.
"""
from getpass import getpass
from humania.seguridad.autenticacion import crear_responsable


def main() -> None:
    print("HumanIA — Configurar acceso inicial de RR. HH.")
    print("Este proceso solo permite crear el primer usuario de la base local.")

    usuario = input("Nombre de usuario: ").strip()
    clave = getpass("Contraseña (12 a 128 caracteres): ")
    confirmar = getpass("Confirmar contraseña: ")

    if clave != confirmar:
        print("ERROR: Las contraseñas no coinciden.")
        raise SystemExit(1)

    resultado = crear_responsable(usuario, clave)
    print(resultado.get("mensaje", "No se pudo completar la operación."))

    if resultado.get("estado") != "correcto":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
