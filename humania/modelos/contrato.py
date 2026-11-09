# Antes de programar el agente, tenemos que identificar cuáles son los datos necesarios.
# Lo representamos como un modelo de datos

from datetime import date
from pydantic import BaseModel, Field, ConfigDict


# Definimos la estructura de datos de un contrato laboral.
class DatosContrato(BaseModel):

    # Rechazamos campos que no estén definidos en el modelo.
    model_config = ConfigDict(extra="forbid")

    # Datos del contrato.
    tipo_contrato: str | None = None

    # Datos del empleador.
    empleador: str | None = None
    cuit_empleador: str | None = None
    domicilio_empleador: str | None = None

    # Datos del empleado.
    nombre_empleado: str | None = None
    dni_empleado: str | None = None
    fecha_nacimiento: date | None = None
    domicilio_empleado: str | None = None

    # Condiciones laborales.
    puesto: str | None = None
    fecha_inicio: date | None = None
    jornada_laboral: str | None = None

    # La remuneración debe ser mayor que cero.
    remuneracion_bruta: float | None = Field(default=None, gt=0)

    lugar_trabajo: str | None = None