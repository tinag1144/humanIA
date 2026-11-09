
# Importamos la función para consultar contratos en SQLite.
from humania.servicios.estado_contrato import consultar_registro


def obtener_revision_pendiente(contrato_id: str) -> dict:
    """
    Recupera la información pendiente de revisión.

    No confirma datos ni modifica contratos.
    """

    # Validamos que el identificador sea texto.
    if not isinstance(contrato_id, str):
        return {
            "estado": "error",
            "mensaje": "El identificador debe ser texto."
        }

    # Comprobamos que no esté vacío.
    if not contrato_id.strip():
        return {
            "estado": "error",
            "mensaje": "Debés indicar un contrato."
        }

    # Consultamos el registro almacenado.
    contrato = consultar_registro(contrato_id)

    # Comprobamos que exista y se haya podido consultar.
    if contrato.get("estado") in ("error", "no_encontrado"):
        return contrato

    # Si existen conflictos, los mostramos.
    if contrato["estado"] == "en_conflicto":
        return {
            "estado": "requiere_revision",
            "contrato_id": contrato["id"],
            "conflictos": contrato["inconsistencias"],
            "mensaje": (
                "Existen datos contradictorios. "
                "Un responsable autorizado debe revisarlos."
            )
        }

    # Si no hay conflictos, verificamos que los datos
    # todavía necesitan confirmación humana.
    if contrato["estado"] == "pendiente_confirmacion":
        return {
            "estado": "pendiente_confirmacion",
            "contrato_id": contrato["id"],
            "mensaje": (
                "No hay conflictos registrados, pero "
                "los datos todavía no están confirmados."
            )
        }

    # Para otros estados no realizamos modificaciones.
    return {
        "estado": contrato["estado"],
        "contrato_id": contrato["id"],
        "mensaje": "El contrato no requiere esta revisión."
    }
