
from pathlib import Path
from datetime import datetime
import re
import sys

ruta = Path("frontend/src/App.tsx")

if not ruta.is_file():
    sys.exit("ERROR: no se encontro frontend/src/App.tsx")

s = ruta.read_text(encoding="utf-8")
original = s


def cambiar(patron, reemplazo, descripcion):
    global s

    nuevo, cantidad = re.subn(
        patron,
        lambda _: reemplazo,
        s,
        count=1,
        flags=re.S,
    )

    if cantidad != 1:
        sys.exit(
            "No se modifico el archivo. Falta: "
            + descripcion
        )

    s = nuevo


cambiar(
    r"const \[drafts, setDrafts\] = useState<Draft\[\]>\(\[\]\)",
    """const [drafts, setDrafts] = useState<Draft[]>([])
  const [draftsFor, setDraftsFor] = useState<string | null>(null)""",
    "estado de borradores",
)

cambiar(
    r"const \[signDate, setSignDate\] = useState\([^\n]*\)",
    "const [signDate, setSignDate] = useState('')",
    "fecha de firma",
)

cambiar(
    r"""useEffect\(\(\) => \{\s*
    if \(!token \|\| !selected\) \{ setDrafts\(\[\]\); return \}\s*
    request<Draft\[\]>\(`/api/interfaz/contratos/\$\{encodeURIComponent\(selected\)\}/borradores`, token\)\s*
    \.then\(setDrafts\)\.catch\(e => setError\(\(e as Error\)\.message\)\)\s*
    \}, \[selected, token, contracts\]\)""",
    """useEffect(() => {
    let vigente = true

    setDrafts([])
    setDraftsFor(null)

    if (token && selected) {
      const contratoId = selected

      request<Draft[]>(
        `/api/interfaz/contratos/${encodeURIComponent(contratoId)}/borradores`,
        token
      )
        .then(lista => {
          if (!vigente) return

          if (
            !Array.isArray(lista) ||
            lista.some(d => d.contrato_id !== contratoId)
          ) {
            setError(
              'El servidor devolvio borradores de otro contrato.'
            )
            return
          }

          setDrafts(lista)
          setDraftsFor(contratoId)
        })
        .catch(e => {
          if (vigente) setError((e as Error).message)
        })
    }

    return () => {
      vigente = false
    }
  }, [selected, token, contracts])""",
    "carga de borradores",
)

cambiar(
    r"""const selectContract = \(id: string\) => \{ resetMessages\(\); setSelected\(id\); setPage\('contratos'\); setMobileOpen\(false\) \}""",
    """const selectContract = (id: string) => {
    resetMessages()
    setDrafts([])
    setDraftsFor(null)
    setCity('')
    setSignDate('')
    setSelected(id)
    setPage('contratos')
    setMobileOpen(false)
  }""",
    "seleccion de contrato",
)

cambiar(
    r"const current = contracts\.find\(c => c\.id === selected\)",
    """const current = selected
    ? contracts.find(c => c.id === selected)
    : undefined

  const visibleDrafts =
    draftsFor === selected ? drafts : []""",
    "contrato actual",
)

cambiar(
    r"""const go = \(next: Page\) => \{ setPage\(next\); setSelected\(null\); setMobileOpen\(false\); resetMessages\(\) \}""",
    """const go = (next: Page) => {
    setPage(next)
    setSelected(null)
    setDrafts([])
    setDraftsFor(null)
    setMobileOpen(false)
    resetMessages()
  }""",
    "navegacion",
)

marcador = "const doSend = async (message = chatInput) => {"

if s.count(marcador) != 1:
    sys.exit("No se encontro la funcion de chat.")

funcion = """const generarBorradorSeleccionado = async (
    contrato: Contract
  ) => {
    if (!token || !selected || contrato.id !== selected) {
      throw new Error(
        'La seleccion del contrato cambio. Volve a abrir la ficha.'
      )
    }

    const ciudad = city.trim()

    if (!ciudad || !signDate) {
      throw new Error('Ingresa ciudad y fecha de firma.')
    }

    const original = await request<Contract>(
      `/api/contratos/${encodeURIComponent(contrato.id)}`,
      token
    )

    if (
      original.id !== selected ||
      original.id !== contrato.id ||
      getName(original) !== getName(contrato) ||
      String(original.datos.dni_empleado || '') !==
        String(contrato.datos.dni_empleado || '')
    ) {
      throw new Error(
        'Los datos del contrato no coinciden con el servidor.'
      )
    }

    if (original.estado !== 'datos_confirmados') {
      throw new Error(
        'El contrato ya no esta en estado datos_confirmados.'
      )
    }

    const aceptado = window.confirm(
      `Vas a generar un borrador de:\\n${getName(original)}\\n` +
      `DNI: ${String(original.datos.dni_empleado || '—')}\\n` +
      `Contrato: ${original.id}\\n` +
      `Ciudad: ${ciudad}\\nFecha: ${signDate}\\n\\n¿Continuar?`
    )

    if (!aceptado) {
      throw new Error('Generacion cancelada.')
    }

    await request(
      `/api/interfaz/contratos/${encodeURIComponent(original.id)}/borradores`,
      token,
      {
        method: 'POST',
        body: JSON.stringify({
          ciudad_firma: ciudad,
          fecha_firma: signDate
        })
      }
    )
  }

  """

s = s.replace(marcador, funcion + marcador, 1)

inicio = s.index("{page==='contratos'")
fin = s.index("{page==='documentacion'", inicio)

antes = s[:inicio]
seccion = s[inicio:fin]
despues = s[fin:]

for viejo, nuevo in [
    ("drafts.length", "visibleDrafts.length"),
    ("drafts.map(", "visibleDrafts.map("),
    ("drafts[0]", "visibleDrafts[0]"),
    ("drafts.some(", "visibleDrafts.some("),
    ("drafts.find(", "visibleDrafts.find("),
]:
    seccion = seccion.replace(viejo, nuevo)

s = antes + seccion + despues

cambiar(
    r"""onSubmit=\{e=>\{e\.preventDefault\(\);void runAction\('borrador',\(\)=>request\(`/api/interfaz/contratos/\$\{current.id\}/borradores`,token,\{method:'POST',body:JSON.stringify\(\{ciudad_firma:city,fecha_firma:signDate\}\)\}\),'Borrador creado y registrado\. Revisá el archivo antes de aprobarlo\.'\)\}\}""",
    """onSubmit={e=>{
      e.preventDefault()
      void runAction(
        'borrador',
        () => generarBorradorSeleccionado(current),
        'Borrador creado y registrado. Revisá el archivo antes de aprobarlo.'
      )
    }}""",
    "accion generar borrador",
)

cambiar(
    r"""onClick=\{\(\) => \{ if \(!token\) return; void runAction\(`revision-\$\{d.id\}`, \(\) => download\(`/api/borradores/\$\{d.id\}/revision-docx`, token\), "Borrador descargado para revisión\. La aprobación sigue pendiente\."\); \}\}""",
    """onClick={() => {
      if (!token || !selected || d.contrato_id !== selected) {
        setError('Borrador no asociado al contrato seleccionado.')
        return
      }
      void runAction(
        `revision-${d.id}`,
        () => download(`/api/borradores/${d.id}/revision-docx`, token),
        'Borrador descargado para revisión. La aprobación sigue pendiente.'
      )
    }}""",
    "boton revisar DOCX",
)

cambiar(
    r"<h3>Acciones disponibles</h3><p>Las decisiones requieren autorización humana\.</p>",
    """<h3>Acciones disponibles</h3>
    <p>
      Contrato seleccionado:
      <strong> {getName(current)}</strong>
      {' · '}{current.id.slice(0, 8)}
    </p>
    <p>Las decisiones requieren autorización humana.</p>""",
    "cabecera acciones",
)

for texto in [
    "Confirmá que revisaste la versión del DOCX y autorizás la aprobación interna.",
    "¿Rechazar este borrador?",
]:
    viejo = (
        "onClick={()=>{if(!window.confirm('"
        + texto
        + "'))return;"
    )

    nuevo = (
        "onClick={()=>{"
        "if(!selected || current.id!==selected || "
        "visibleDrafts[0]?.contrato_id!==selected){"
        "setError('El borrador no corresponde al contrato seleccionado.');"
        "return;}"
        "if(!window.confirm('"
        + texto
        + "'))return;"
    )

    if viejo not in s:
        sys.exit(
            "No se modifico el archivo. Falta control de aprobacion."
        )

    s = s.replace(viejo, nuevo, 1)

respaldo = ruta.with_name(
    ruta.name
    + ".antes_corregir_"
    + datetime.now().strftime("%Y%m%d_%H%M%S")
    + ".bak"
)

respaldo.write_text(original, encoding="utf-8")
ruta.write_text(s, encoding="utf-8")

print("ACTUALIZADO:", ruta)
print("RESPALDO:", respaldo)
print("No se modificaron contratos, SQLite ni documentos.")
