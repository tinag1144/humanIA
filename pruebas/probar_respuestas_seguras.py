
# Importamos SimpleNamespace para simular contextos de ADK.
from types import SimpleNamespace

# Importamos los tipos necesarios.
from google.genai import types
from google.adk.models.llm_response import LlmResponse

# Importamos nuestros controles.
from humania.seguridad.respuestas import (
    registrar_conflicto,
    controlar_respuesta
)

# Importamos la herramienta real.
from humania.tools.agente import comparar_domicilios


# Simulamos el estado de una sesión.
contexto = SimpleNamespace(state={})

# Ejecutamos nuestra herramienta.
resultado = comparar_domicilios(
    "Calle Falsa 742",
    "Calle Falsa 850"
)

# Simulamos que ADK recibió el resultado.
registrar_conflicto(
    tool=SimpleNamespace(name="comparar_domicilios"),
    args={},
    tool_context=contexto,
    tool_response=resultado
)

# Simulamos una respuesta incorrecta del modelo.
respuesta_incorrecta = LlmResponse(
    content=types.Content(
        role="model",
        parts=[
            types.Part(
                text="Elegí Calle Falsa 850 y lo confirmé."
            )
        ]
    )
)

# Ejecutamos el guardrail de salida.
respuesta_segura = controlar_respuesta(
    callback_context=contexto,
    llm_response=respuesta_incorrecta
)

print("Estado de conflicto:")
print(contexto.state["domicilio_en_conflicto"])

print("\nRespuesta final:")
print(respuesta_segura.content.parts[0].text)

# Comprobaciones automáticas.
assert contexto.state["domicilio_en_conflicto"] is True
assert "Ninguno de los domicilios está confirmado" in (
    respuesta_segura.content.parts[0].text
)

print("\nPRUEBA SUPERADA")
