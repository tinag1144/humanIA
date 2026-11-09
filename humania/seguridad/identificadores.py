"""Validación común para identificadores contractuales en HumanIA.

Modo académico: DNI de 7 a 9 dígitos; CUIT de 11 dígitos.
No comprueba dígito verificador de CUIT ni identidad real.
"""
from __future__ import annotations

import re

CAMPOS_IDENTIFICADORES = ("dni_empleado", "cuit_empleador")


def validar_identificador(campo: str, valor: object) -> str | None:
    if campo not in CAMPOS_IDENTIFICADORES:
        return None
    if not isinstance(valor, str) or not valor.strip():
        return f"{etiqueta(campo)}: ingresá un valor de texto válido."
    texto = valor.strip()
    if campo == "dni_empleado":
        if not re.fullmatch(r"[0-9.]+", texto):
            return "DNI inválido: solo se permiten números y puntos."
        if texto.count(".") and not re.fullmatch(r"[0-9]{1,3}(?:\.[0-9]{3}){2}", texto):
            return "DNI inválido: usá números sin separadores o formato 00.000.004."
        cantidad = len(texto.replace(".", ""))
        if cantidad not in (7, 8, 9):
            return "DNI inválido: debe tener 7, 8 o 9 dígitos (modo académico)."
        return None
    if not re.fullmatch(r"(?:[0-9]{11}|[0-9]{2}-[0-9]{8}-[0-9])", texto):
        return "CUIT inválido: usá exactamente 11 dígitos, con formato XX-XXXXXXXX-X o sin guiones."
    return None


def etiqueta(campo: str) -> str:
    return "DNI" if campo == "dni_empleado" else "CUIT"


def validar_datos_identificacion(datos: dict) -> list[str]:
    return [error for campo in CAMPOS_IDENTIFICADORES
            if campo in datos and (error := validar_identificador(campo, datos[campo]))]


def filtrar_identificadores(propuesta: dict) -> tuple[dict, list[str]]:
    """Devuelve propuesta segura y errores, sin tocar el diccionario original."""
    aceptados = {}
    errores = []
    for campo, valor in propuesta.items():
        error = validar_identificador(campo, valor)
        if error:
            errores.append(error)
        else:
            aceptados[campo] = valor
    return aceptados, errores


def errores_en_mensaje(mensaje: str) -> list[str]:
    """Detecta identificadores explícitos inválidos sin depender del LLM.

    Abarca expresiones tipo 'DNI es ABC123', 'CUIT: 30-ABC...' y
    'DNI del empleado ...'. No pretende interpretar documentos completos.
    """
    errores = []
    patrones = (
        ("dni_empleado", r"\bDNI\b(?:\s+(?:del?\s+)?(?:emplead[oa]|trabajador|es))?\s*(?:es|:|=|n[uú]mero)?\s*['\"]?([^\s,;\n'\"]+)"),
        ("cuit_empleador", r"\bCUIT\b(?:\s+(?:del?\s+)?(?:empleador|empresa|es))?\s*(?:es|:|=|n[uú]mero)?\s*['\"]?([^\s,;\n'\"]+)"),
    )
    for campo, patron in patrones:
        for match in re.finditer(patron, mensaje, re.IGNORECASE):
            candidato = match.group(1).rstrip(".")
            if candidato.lower() in {"del", "de", "es", "empleado", "empleador", "la", "el"}:
                continue
            error = validar_identificador(campo, candidato)
            if error and error not in errores:
                errores.append(error)
    return errores
