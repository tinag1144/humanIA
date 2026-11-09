# HumanIA · Espacio inteligente de Recursos Humanos

**Prototipo académico local** de asistencia para la preparación de contratos laborales, con inteligencia artificial, revisión humana y trazabilidad documental.

> **Alcance:** trabajo práctico «Problemática 05 — HumanIA S.A.». Utilizar únicamente información ficticia o autorizada. El sistema **no firma ni formaliza contratos**, no reemplaza asesoramiento legal y no debe exponerse directamente a Internet.

## Qué permite hacer

- Conversar en español con un asistente de IA para recopilar progresivamente **13 campos** de un contrato por tiempo indeterminado.
- Informar campos faltantes, validar identificadores (DNI y CUIT) y detectar contradicciones que necesitan resolución humana.
- Adjuntar documentos PDF y DOCX para recuperar texto; las imágenes tienen **transcripción provisional no confiable** y requieren comprobación manual.
- Consultar documentación institucional con **RAG** (embeddings locales y SQLite).
- Confirmar datos, registrar el contrato, generar una versión DOCX mediante plantilla autorizada y revisarla.
- Aprobar o rechazar una versión con usuario autenticado de Recursos Humanos.
- Descargar DOCX, PDF y una **constancia de aprobación interna**. Se utiliza SHA-256 para verificar la integridad del borrador aprobado.

## Arquitectura

| Capa | Tecnología | Ubicación |
| --- | --- | --- |
| Interfaz web | React, TypeScript, Vite, Lucide | `frontend/` |
| API y autenticación | FastAPI, Pydantic, tokens, SQLite | `api/` |
| Agente IA | Google ADK, LiteLLM, Ollama (`qwen2.5:7b`) | `humania/agent.py` |
| RAG | `nomic-embed-text`, búsqueda vectorial en SQLite | `indexar.py`, `humania/tools/consultar.py` |
| Plantillas | DOCX + `docxtpl` | `plantillas/` |
| Pruebas | Python, casos de seguridad y negocio | `pruebas/` |

**Arquitectura de ejecución local:** navegador (puerto **5173**) → FastAPI (**8001**) → ADK (**8000**) / Ollama (**11434**). El frontend se comunica con FastAPI, y las decisiones sensibles se autorizan en el servidor, no mediante instrucciones del modelo.

## Requisitos del entorno

- **Windows**, con **Python 3.12**, Node.js y npm instalados.
- Microsoft Word para la conversión a PDF mediante `docx2pdf` / COM.
- Ollama ejecutándose localmente.
- Dependencias Python de `requirements.txt` y dependencias del frontend de `frontend/package.json`.

## Instalación desde cero (PowerShell)

Desde la raíz del repositorio:

```powershell
py -3.12 -m venv env
.\env\Scripts\Activate.ps1
uv pip install -r requirements.txt
```

Si no usás `uv`, podés instalar con `python -m pip install -r requirements.txt` si `pip` está disponible en tu entorno.

En el directorio `frontend`:

```powershell
cd frontend
npm install
npm run build
cd ..
```

Prepará Ollama:

```powershell
ollama pull qwen2.5:7b
ollama pull nomic-embed-text
ollama pull llava:7b
ollama list
```

La descarga de `llava:7b` es opcional si no se van a probar imágenes. **No implica que su lectura de documentos sea fiable**.

### Inicialización

1. Crear el primer usuario RR. HH. ejecutando `python configurar_rrhh.py`; el asistente pide nombre de usuario y contraseña sin mostrarla (la base local y las credenciales no se incluyen en GitHub).
2. Indexar los documentos de ejemplo con `python indexar.py` (requiere Ollama).
3. Verificar que las plantillas v1 y v2 estén presentes e íntegras. El archivo `humania/servicios/contratos.py` define la versión activa; no editar las plantillas autorizadas sobre sus huellas registradas.

### Iniciar los servicios (tres terminales)

**Terminal 1: API**

```powershell
python -m uvicorn api.main:app --reload --host 127.0.0.1 --port 8001
```

**Terminal 2: agente ADK**

```powershell
adk api_server --host 127.0.0.1 --port 8000
```

**Terminal 3: interfaz**

```powershell
cd frontend
npm run dev
```

Abrí **http://127.0.0.1:5173**. Ollama debe permanecer en ejecución. No publicar los puertos de ADK o FastAPI en Internet.

## Demostración recomendada

1. Iniciar sesión como responsable de RR. HH.
2. Abrir **Asistente IA**; solicitar un contrato ficticio por tiempo indeterminado y facilitar los 13 datos.
3. Verificar que la IA enumera los datos y faltantes. Para el flujo guiado usar **CONFIRMO LOS DATOS** y **REGISTRAR CONTRATO**.
4. En la sección de contratos confirmar integralmente los datos registrados, si todavía aparecen pendientes.
5. En el chat usar **GENERAR BORRADOR; ciudad: Formosa; fecha: 2026-11-16**.
6. Abrir **Contratos**, descargar el DOCX para revisión y verificar datos, modalidad y cláusulas.
7. Solo un usuario humano autorizado puede aprobar o rechazar la versión.
8. Si se aprueba, comprobar las descargas de DOCX, PDF y constancia y su trazabilidad SHA-256.

No usar DNI/CUIT reales en la demostración. Los DNI de **9 dígitos** se admiten en este prototipo para los datos ficticios usados en las pruebas; no constituyen validación de identidad real.

## Seguridad y restricciones

- Las herramientas del agente no pueden aprobar ni firmar.
- Los fragmentos del RAG son **datos no confiables**, nunca autorizaciones ni nuevas instrucciones.
- Los documentos importados pueden contener errores: no suponer que sus campos fueron verificados por una persona.
- Los modelos de visión pueden inventar texto: la transcripción de imágenes es provisional y no debe incorporarse sin comprobación.
- Las bases `*.db`, los tokens, credenciales, el entorno virtual y `node_modules/` están excluidos del repositorio.
- La constancia **registra una decisión interna** y no equivale a firma digital ni a contrato formalizado.


## Validación integral de la entrega (un comando)

Con el entorno Python activado y las dependencias instaladas, desde la **raíz del proyecto**:

```powershell
python pruebas/validar_todo.py
```

La ejecución comprueba sintaxis Python, pruebas de exportación sin modificar el original, adjuntos PDF/DOCX, identificadores, contradicciones, integridad RAG, compilación del frontend y plantillas v1/v2. **No borra ni modifica los datos registrados**. Los errores se muestran por etapa.

Después queda la comprobación funcional de **la descarga aprobada** con Microsoft Word, el **RAG** con Ollama y la calidad de las imágenes: son tareas dependientes del entorno local. En el panel de contratos, el botón **«Original para revisión»** no cambia la leyenda del DOCX auditado; las copias aprobadas se descargan desde **«DOCX aprobado»** o **«PDF aprobado»**.

## Estado del proyecto

El circuito conversacional, la generación del borrador, su aprobación humana y las descargas se probaron con **datos ficticios**, incluyendo un caso de Pedro Gómez. El informe detallado y la matriz F01–F10 están en [`cierre_humania/ESTADO_Y_PRUEBAS.md`](cierre_humania/ESTADO_Y_PRUEBAS.md).

**Pendientes declarados:**
- La lectura automática de imágenes no es confiable: requisito multimodal **parcial**.
- Conviene repetir la regresión de DOCX de entrada, RAG y control de permisos en la instalación final.
- La exportación a PDF depende de Windows y Microsoft Word; no se puede asegurar desde un entorno de CI Linux.
- Si la representación descargada sigue diciendo «BORRADOR - SIN APROBACIÓN FINAL», comprobar el módulo de presentación aprobada antes de usarla como versión final.

## Estructura principal

```text
humanIA/
├── api/                    # FastAPI: sesiones, flujo, adjuntos y descargas
├── frontend/               # React + TypeScript + HumanIA Studio
├── humania/                # Agente ADK, herramientas, seguridad, servicios
├── plantillas/             # Plantillas contractuales autorizadas
├── documentos/             # Fuentes para RAG
├── documentos_prueba/      # Datos ficticios de demostración
├── pruebas/                # Scripts de prueba
├── cierre_humania/         # Evidencia y auditoría
├── indexar.py              # Construcción del índice RAG
└── requirements.txt        # Dependencias Python
```

---

Proyecto académico de demostración — **HumanIA S.A.** · 2026.
