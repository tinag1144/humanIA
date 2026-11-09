# HumanIA — Cierre técnico y pruebas

**Fecha:** 09/11/2026  
**Proyecto:** Problemática 05 — HumanIA S.A.  
**Alcance:** entorno académico, documentos y datos ficticios.

## Diagnóstico verificado

Se revisaron los tres archivos del contrato ficticio de Pedro Gómez: DOCX de borrador #6 versión 1, PDF descargado tras la aprobación y constancia de aprobación. La huella SHA-256 del DOCX **coincide exactamente** con la incluida en la constancia: `771f2e5faab69396695610e39da9fe48a523b874eca7598aa9eeca2e80783732`. Los datos principales coinciden entre DOCX/PDF. La constancia registra el contrato `cc0512e7-d3e3-43d0-b9ca-7399676554c9` como aprobado por `responsable_prueba`.

**Incidencia abierta:** tanto el DOCX como el PDF distribuidos después de aprobar conservan la leyenda «BORRADOR - SIN APROBACION FINAL». La aprobación consta en el sistema y en la constancia, pero los documentos no reflejan visualmente ese estado. **No modificar directamente el DOCX aprobado**, porque rompería su huella y la trazabilidad; corregir el procedimiento de exportación para generar una representación aprobada separada, preservando el original y la auditoría. Las casillas de revisión impresas siguen vacías; una nueva exportación debería indicar el estado interno registrado sin simular una firma electrónica.

## Matriz de requisitos F01–F10

| Requisito | Evidencia observada | Estado |
|---|---|---|
| F01 Lenguaje natural | Conversación para contrato Pedro Gómez | Verificado en ejemplo |
| F02 Modalidad y plantilla | Tiempo indeterminado; plantilla v2 | Verificado para una modalidad |
| F03 PDF, DOCX, imágenes | PDF leído; fotos imprecisas; entrada DOCX pendiente de regresión | Parcial |
| F04 Recopilación | 13 campos de Pedro | Verificado |
| F05 Faltantes | Listados por agente | Verificado |
| F06 Contradicciones | Prueba de domicilio realizada | Verificado en ejemplo |
| F07 Generación | DOCX #6 desde agente | Verificado |
| F08 Base documental | Prueba previa de RAG | Repetir regresión final |
| F09 Revisión humana | Constancia de aprobación por responsable | Verificado en ejemplo |
| F10 Exportación | DOCX, PDF y constancia | Descarga verificada, presentación pendiente |

## Pruebas de cierre propuestas

1. **Documento aprobado:** descargar DOCX/PDF desde contrato aprobado; comprobar que no se presenta como «borrador sin aprobación», que no se altera el histórico aprobado y que la constancia refiere al archivo correcto.
2. **Validaciones:** DNI con letras y CUIT inválido desde formulario, chat y adjuntos. Verificar respuesta HTTP 4xx o rechazo explicado sin registro.
3. **Imágenes:** probar fotografía nítida con datos ficticios; si la lectura no es confiable, mantener validación humana y registrar requisito F03 como parcial.
4. **DOCX de entrada:** adjuntar formulario DOCX con datos ficticios y confirmar que extrae solo los presentes, que muestra faltantes y que no registra sin autorización.
5. **RAG:** hacer una pregunta soportada por documento institucional, verificar referencia a la fuente, y otra no soportada (no debe inventar normativa).
6. **Autorización:** usuario sin permisos no puede aprobar, y borradores pendientes no deben habilitar descarga «aprobada».
7. **Regresión de identidad:** generar con Valentina y con Lucía; no cruzar ID de contrato ni borradores. 
8. **Persistencia:** reiniciar servidor e iniciar sesión de nuevo; comprobar estados, historial de versiones y hashes.
9. **Rechazos:** mantener una decisión de rechazo registrada sin permitir aprobación automática por el agente.

## Criterio de DONE

Marcar DONE únicamente cuando las pruebas críticas pasen y las limitaciones pendientes se declaren explícitamente. La funcionalidad F03 de imágenes no debe contarse como exitosa sin nueva evidencia. La constancia de aprobación **no equivale a firma digital ni formalización legal**.


---

## Avance de cierre — 09/11/2026 (versión publicada en main)

Esta sección actualiza la incidencia de exportación descrita arriba. **No afirma que la ejecución final en Windows ya haya sido validada**.

### Cambios implementados

1. Las descargas aprobadas `/api/borradores/{id}/descargar-docx` y `/descargar-pdf` generan una **copia de presentación** con el responsable, la fecha y la aprobación interna. El original DOCX auditado no se reescribe y mantiene su SHA-256; la constancia referencia ese original.
2. El frontend distingue **«Original para revisión»** de **«DOCX aprobado»** y **«PDF aprobado»**. El original de revisión conserva correctamente la leyenda «BORRADOR - SIN APROBACION FINAL».
3. Se verifican las plantillas históricas v1/v2 por su huella autorizada individual; una nueva versión activa no invalida por sí misma una exportación histórica.
4. Se añadieron pruebas automáticas independientes de Ollama y Word: `pruebas/probar_cierre_final.py` y `pruebas/probar_rag_sin_ollama.py`.
5. Diagnóstico de solo lectura: `python pruebas/diagnostico_humania.py`.

### Evidencia técnica de exportación

Se ejecutó una prueba aislada del generador de copias con los bytes del DOCX ficticio de **Sofía Martínez** (borrador 7), simulando la lectura de la decisión aprobada. La copia mostró el encabezado «COPIA DE PRESENTACIÓN - APROBACIÓN INTERNA REGISTRADA», el responsable `responsable_prueba` y el estado `APROBADO`. Se comprobó que el original siguió teniendo la huella registrada en la constancia. Se renderizó e inspeccionó visualmente la copia DOCX de dos páginas. **Esto prueba el transformador, no la descarga HTTP y conversión por Word desde la instalación del usuario**.

### Verificación final pendiente en Windows

- Actualizar a `main`, reiniciar FastAPI y comprobar el endpoint de **DOCX aprobado** (nombre esperado: `copia_aprobada_7.docx`) y el de **PDF aprobado**; la descarga de revisión continuará como borrador.
- Ejecutar `python -m unittest pruebas.probar_cierre_final pruebas.probar_rag_sin_ollama -v` y `python pruebas/diagnostico_humania.py`.
- Repetir pruebas manuales de RAG con Ollama y transcripción de imágenes. **F03 imágenes sigue parcial hasta demostrar lectura fiable**, sin incorporación autónoma.
- Validar en la interfaz una cuenta sin rol RR. HH., persistencia tras reinicio y que el agente no pueda aprobar por chat.
- Verificar el PDF exportado con Microsoft Word en el Windows real.

**Estado de cierre:** implementaciones y controles de regresión añadidos; aceptación integral pendiente de evidencia de la ejecución final. La constancia representa una aprobación interna, no una firma digital.
