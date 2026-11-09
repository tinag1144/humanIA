
"""
Servicio de generación segura de borradores de HumanIA.

Controles:
- Confirmación integral por RR. HH.
- Integridad de los datos contractuales.
- Ausencia de contradicciones.
- Validación de campos obligatorios.
- Integridad de la plantilla DOCX.
- Registro automático de la versión generada.

Este servicio no aprueba ni firma contratos.
"""

import re
import hashlib

from datetime import date
from pathlib import Path
from uuid import uuid4

from docxtpl import DocxTemplate
from docx import Document
from pydantic import ValidationError

from humania.modelos.contrato import DatosContrato
from humania.seguridad.identificadores import validar_datos_identificacion

from humania.servicios.estado_contrato import (
    consultar_registro,
    calcular_huella
)

from humania.servicios.aprobaciones import CAMPOS_OBLIGATORIOS

from humania.seguridad.auditoria import (
    registrar_borrador,
    verificar_borrador
)


# Rutas existentes del proyecto.
RAIZ = Path(__file__).resolve().parents[2]

# Solo activar v2 cuando RR. HH. haya revisado y autorizado su clausula octava.
# La version v1 y los archivos historicos se conservan sin cambios.
PLANTILLA_ACTIVA = "v2"  # Cambiar a "v2" despues de la autorizacion.
PLANTILLAS_AUTORIZADAS = {
    "v1": (RAIZ / "plantillas" / "indeterminado_v1.docx", "6AE8D8481DC599F41706876DAA6EEC295399E4DFB9514791E3625F1E3D0274E8"),
    "v2": (RAIZ / "plantillas" / "indeterminado_v2.docx", "632127B239A1C86F2BFF3D166C5392B1AE8B00C95D1967DA272D74706CB6B7D4"),
}
PLANTILLA, HUELLA_PLANTILLA = PLANTILLAS_AUTORIZADAS[PLANTILLA_ACTIVA]
DESTINO = RAIZ / "contratos_generados"



# Variables permitidas en el DOCX.
VARIABLES_PLANTILLA = set(CAMPOS_OBLIGATORIOS) - {
    "tipo_contrato"
}

VARIABLES_PLANTILLA.update({
    "ciudad_firma",
    "dia_firma",
    "mes_firma",
    "anio_firma"
})


def verificar_plantilla() -> dict:
    """
    Comprueba que la plantilla coincida con
    la versión de referencia.
    """

    if not PLANTILLA.is_file():
        return {
            "estado": "bloqueado",
            "mensaje": "No se encontró la plantilla DOCX."
        }

    try:
        huella_actual = hashlib.sha256(
            PLANTILLA.read_bytes()
        ).hexdigest().upper()

    except OSError:
        return {
            "estado": "bloqueado",
            "mensaje": "No se pudo leer la plantilla."
        }

    if huella_actual != HUELLA_PLANTILLA:
        return {
            "estado": "bloqueado",
            "mensaje": (
                "La plantilla fue modificada o no coincide "
                "con la versión de referencia."
            )
        }

    return {
        "estado": "valida",
        "mensaje": "Integridad de plantilla verificada."
    }


def obtener_texto_documento(documento: Document) -> str:
    """
    Recupera el texto principal, tablas,
    encabezados y pies del DOCX.
    """

    textos = []

    for parrafo in documento.paragraphs:
        textos.append(parrafo.text)

    for tabla in documento.tables:
        for fila in tabla.rows:
            for celda in fila.cells:
                for parrafo in celda.paragraphs:
                    textos.append(parrafo.text)

    for seccion in documento.sections:
        for parrafo in seccion.header.paragraphs:
            textos.append(parrafo.text)

        for parrafo in seccion.footer.paragraphs:
            textos.append(parrafo.text)

    return "\n".join(textos)


def generar_borrador(
    contrato_id: str,
    ciudad_firma: str,
    fecha_firma: date
) -> dict:
    """
    Genera y registra un borrador DOCX.

    El resultado solo se informa como exitoso
    cuando su auditoría quedó registrada.
    """

    # Validamos los parámetros.
    if not isinstance(contrato_id, str) or not contrato_id.strip():
        return {
            "estado": "bloqueado",
            "mensaje": "Identificador de contrato inválido."
        }

    if (
        not isinstance(ciudad_firma, str)
        or not ciudad_firma.strip()
        or len(ciudad_firma) > 100
    ):
        return {
            "estado": "bloqueado",
            "mensaje": "Ciudad de firma inválida."
        }

    if not isinstance(fecha_firma, date):
        return {
            "estado": "bloqueado",
            "mensaje": "Fecha de firma inválida."
        }

    # Consultamos el contrato existente.
    registro = consultar_registro(contrato_id)

    if not isinstance(registro, dict) or "datos" not in registro:
        return {
            "estado": "bloqueado",
            "mensaje": "No se encontró el contrato."
        }

    # Exigimos confirmación humana integral.
    if registro.get("estado") != "datos_confirmados":
        return {
            "estado": "bloqueado",
            "mensaje": (
                "Los datos del contrato deben estar "
                "confirmados integralmente por RR. HH."
            )
        }

    if (
        not registro.get("confirmado_por")
        or not registro.get("fecha_confirmacion")
    ):
        return {
            "estado": "bloqueado",
            "mensaje": "Falta la confirmación humana registrada."
        }

    # Comprobamos la integridad de los datos.
    if registro.get("integridad_confirmada") is not True:
        return {
            "estado": "bloqueado",
            "mensaje": "Los datos confirmados fueron modificados."
        }

    datos_originales = registro["datos"]

    if not isinstance(datos_originales, dict):
        return {
            "estado": "bloqueado",
            "mensaje": "Datos contractuales inválidos."
        }

    errores_id = validar_datos_identificacion(datos_originales)
    if errores_id:
        return {
            "estado": "bloqueado",
            "mensaje": " ".join(errores_id),
        }

    if (
        registro.get("huella_confirmacion")
        != calcular_huella(datos_originales)
    ):
        return {
            "estado": "bloqueado",
            "mensaje": "La huella de los datos no coincide."
        }

    # No admitimos contradicciones abiertas.
    if registro.get("inconsistencias") != []:
        return {
            "estado": "bloqueado",
            "mensaje": "Existen contradicciones pendientes."
        }

    # La aprobación final debe continuar vacía.
    if (
        registro.get("aprobado_por") is not None
        or registro.get("fecha_aprobacion") is not None
    ):
        return {
            "estado": "bloqueado",
            "mensaje": "El contrato ya tiene datos de aprobación."
        }

    try:
        contrato = DatosContrato.model_validate(datos_originales)

    except (ValidationError, ValueError, TypeError):
        return {
            "estado": "bloqueado",
            "mensaje": "Los datos no superaron la validación."
        }

    datos = contrato.model_dump(mode="json")

    # Comprobamos los campos obligatorios.
    faltantes = [
        campo
        for campo in CAMPOS_OBLIGATORIOS
        if datos.get(campo) is None
        or (
            isinstance(datos.get(campo), str)
            and not datos[campo].strip()
        )
    ]

    if faltantes:
        return {
            "estado": "bloqueado",
            "mensaje": "Faltan datos obligatorios.",
            "campos_faltantes": faltantes
        }

    # Solo admitimos contratos por tiempo indeterminado.
    tipo = str(datos["tipo_contrato"]).strip().lower()

    if tipo not in (
        "indeterminado",
        "tiempo indeterminado",
        "por tiempo indeterminado",
        "contrato por tiempo indeterminado"
    ):
        return {
            "estado": "bloqueado",
            "mensaje": "La modalidad no corresponde a la plantilla."
        }

    # Verificamos la plantilla antes de utilizarla.
    control_plantilla = verificar_plantilla()

    if control_plantilla["estado"] != "valida":
        return control_plantilla

    # Preparamos los valores permitidos.
    contexto = {
        campo: datos[campo]
        for campo in VARIABLES_PLANTILLA
        if campo in datos
    }

    contexto["fecha_nacimiento"] = (
        contrato.fecha_nacimiento.strftime("%d/%m/%Y")
    )

    contexto["fecha_inicio"] = (
        contrato.fecha_inicio.strftime("%d/%m/%Y")
    )

    importe = contrato.remuneracion_bruta

    contexto["remuneracion_bruta"] = (
        "$ " + f"{importe:,.2f}"
        .replace(",", "X")
        .replace(".", ",")
        .replace("X", ".")
    )

    meses = (
        "enero", "febrero", "marzo", "abril",
        "mayo", "junio", "julio", "agosto",
        "septiembre", "octubre", "noviembre", "diciembre"
    )

    contexto.update({
        "ciudad_firma": ciudad_firma.strip(),
        "dia_firma": fecha_firma.day,
        "mes_firma": meses[fecha_firma.month - 1],
        "anio_firma": fecha_firma.year
    })

    ruta = None

    try:
        # Abrimos la plantilla original.
        documento = DocxTemplate(str(PLANTILLA))

        variables = documento.get_undeclared_template_variables()

        if variables != VARIABLES_PLANTILLA:
            return {
                "estado": "bloqueado",
                "mensaje": "La plantilla tiene variables no válidas.",
                "faltantes": sorted(
                    VARIABLES_PLANTILLA - variables
                ),
                "desconocidas": sorted(
                    variables - VARIABLES_PLANTILLA
                )
            }

        # Reemplazamos únicamente los marcadores.
        documento.render(contexto, autoescape=True)

        DESTINO.mkdir(parents=True, exist_ok=True)

        nombre = f"borrador_{uuid4().hex}.docx"
        ruta = DESTINO / nombre

        documento.save(str(ruta))

        # Marcamos el archivo como borrador.
        borrador = Document(str(ruta))

        encabezado = borrador.sections[0].header
        encabezado.paragraphs[0].text = (
            "BORRADOR - SIN APROBACION FINAL"
        )

        borrador.save(str(ruta))

        # Comprobamos el resultado final.
        documento_final = Document(str(ruta))
        texto = obtener_texto_documento(documento_final)

        if re.search(r"{{|}}|{%|%}", texto):
            ruta.unlink(missing_ok=True)

            return {
                "estado": "bloqueado",
                "mensaje": "Quedaron variables sin resolver."
            }

        # NUEVO: registramos el archivo en auditoría.
        auditoria = registrar_borrador(
            contrato_id=contrato_id,
            ruta_archivo=str(ruta),
            huella_plantilla=HUELLA_PLANTILLA
        )

        if auditoria.get("estado") != "registrado":
            ruta.unlink(missing_ok=True)

            return {
                "estado": "error",
                "mensaje": (
                    "El borrador no pudo registrarse "
                    "en auditoría."
                ),
                "detalle": auditoria.get("mensaje")
            }

        # Verificamos el DOCX registrado.
        verificacion = verificar_borrador(
            auditoria["borrador_id"]
        )

        if verificacion.get("estado") != "integro":
            # El registro ya existe en SQLite.
            # No informamos éxito ni eliminamos
            # automáticamente la evidencia auditada.
            return {
                "estado": "error",
                "mensaje": (
                    "El borrador registrado no superó "
                    "la comprobación de integridad."
                ),
                "borrador_id": auditoria["borrador_id"]
            }

        return {
            "estado": "borrador_generado",
            "contrato_id": contrato_id,
            "borrador_id": auditoria["borrador_id"],
            "version": auditoria["version"],
            "archivo": nombre,
            "ruta": str(ruta),
            "huella_archivo": auditoria["huella_archivo"],
            "confirmado_por": registro["confirmado_por"],
            "integridad_confirmada": True,
            "plantilla_verificada": True,
            "auditoria_registrada": True,
            "aprobado": False,
            "mensaje": (
                "Borrador generado, registrado y verificado. "
                "Requiere aprobación final."
            )
        }

    except (OSError, ValueError, KeyError, TypeError):
        # Si todavía no quedó registrado, borramos
        # el archivo generado de manera incompleta.
        if ruta is not None:
            ruta.unlink(missing_ok=True)

        return {
            "estado": "error",
            "mensaje": "No se pudo generar el borrador DOCX."
        }
