"""Instala carga segura de adjuntos sin reemplazar módulos existentes.

Ejecutar en la raíz del proyecto: python instalar_adjuntos.py
Requiere copiar api/adjuntos_chat.py al proyecto antes de ejecutarlo.
"""
from __future__ import annotations

from datetime import datetime
from pathlib import Path
import shutil

raiz = Path(__file__).resolve().parent
main = raiz / "api" / "main.py"
front = raiz / "frontend" / "src" / "App.tsx"
module = raiz / "api" / "adjuntos_chat.py"
for ruta in (main, front, module):
    if not ruta.is_file():
        raise SystemExit(f"Falta {ruta}; no se modificó ningún archivo.")

old_main = main.read_text(encoding="utf-8")
old_front = front.read_text(encoding="utf-8")
new_main = old_main
new_front = old_front

main_import = "from api.adjuntos_chat import router as adjuntos_router"
main_include = "app.include_router(adjuntos_router)"
if main_include not in new_main:
    if "app.include_router(flujo_router)" not in new_main:
        raise SystemExit("No se encuentra el router del flujo conversacional; no se modificó nada.")
    new_main = new_main.rstrip() + "\n\n# Documentos ficticios adjuntos al chat.\n" + main_import + "\n" + main_include + "\n"

if "Paperclip" not in new_front:
    key = "  Search, Send, ShieldCheck, Sparkles, UserRound, WandSparkles, X"
    if new_front.count(key) != 1:
        raise SystemExit("Importaciones de App.tsx desconocidas; no se modificó nada.")
    new_front = new_front.replace(key, "  Search, Send, Paperclip, ShieldCheck, Sparkles, UserRound, WandSparkles, X", 1)

state_anchor = "  const [sending, setSending] = useState(false)"
state_patch = """  const [adjunto, setAdjunto] = useState<File | null>(null)
  const [subiendoAdjunto, setSubiendoAdjunto] = useState(false)
  const adjuntoInput = useRef<HTMLInputElement>(null)
"""
if "const [adjunto, setAdjunto]" not in new_front:
    if new_front.count(state_anchor) != 1:
        raise SystemExit("Estado del chat desconocido; no se modificó nada.")
    new_front = new_front.replace(state_anchor, state_anchor + "\n" + state_patch.rstrip(), 1)

method_anchor = "  if (!token) return ("
method_patch = """  const subirAdjunto = async () => {
    if (!adjunto || !token || subiendoAdjunto || sending) return
    setSubiendoAdjunto(true)
    const file = adjunto
    try {
      const data = new FormData()
      data.append('archivo', file)
      if (chatSession) data.append('sesion_id', chatSession)
      const response = await fetch('/api/flujo/adjunto', {
        method: 'POST',
        headers: { Authorization: `Bearer ${token}` },
        body: data
      })
      const result = await response.json()
      if (!response.ok) {
        const detail = result?.detail
        throw new Error(typeof detail === 'string' ? detail : `Error al procesar el archivo (HTTP ${response.status}).`)
      }
      const parsed = result as ChatResult
      setChatSession(parsed.sesion_id)
      setChatLines(lines => [
        ...lines,
        { id: Date.now(), role: 'user', text: `Adjunto: ${file.name}` },
        { id: Date.now() + 1, role: 'agent', text: parsed.mensaje, herramientas: parsed.herramientas }
      ])
      setAdjunto(null)
      if (adjuntoInput.current) adjuntoInput.current.value = ''
    } catch (e) {
      setChatLines(lines => [...lines, {
        id: Date.now() + 2, role: 'agent',
        text: `No se pudo analizar el adjunto: ${(e as Error).message}`
      }])
    } finally {
      setSubiendoAdjunto(false)
    }
  }

"""
if "const subirAdjunto = async () =>" not in new_front:
    if new_front.count(method_anchor) != 1:
        raise SystemExit("No se encuentra el comienzo del render del chat; no se modificó nada.")
    new_front = new_front.replace(method_anchor, method_patch + method_anchor, 1)

input_anchor = '<form className="chat-input-box" onSubmit={e=>{e.preventDefault();void doSend()}}>'
attachment_ui = """<div style={{display:'flex',gap:8,alignItems:'center',padding:'8px 12px',flexWrap:'wrap'}}>
  <input ref={adjuntoInput} type="file" accept=".pdf,.docx,.png,.jpg,.jpeg,.webp" style={{display:'none'}}
    onChange={e=>setAdjunto(e.target.files?.[0] || null)} />
  <button type="button" className="btn secondary" disabled={sending||subiendoAdjunto}
    onClick={()=>adjuntoInput.current?.click()}><Paperclip size={16}/> Elegir PDF, Word o imagen</button>
  {adjunto&&<><span style={{fontSize:12,wordBreak:'break-all'}}>{adjunto.name}</span>
    <button type="button" className="btn primary" disabled={sending||subiendoAdjunto}
      onClick={()=>void subirAdjunto()}>{subiendoAdjunto?'Analizando…':'Analizar adjunto'}</button></>}
</div>"""
if "Elegir PDF, Word o imagen" not in new_front:
    if new_front.count(input_anchor) != 1:
        raise SystemExit("No se encuentra el formulario del chat; no se modificó nada.")
    new_front = new_front.replace(input_anchor, attachment_ui + input_anchor, 1)

if old_main == new_main and old_front == new_front:
    print("Los adjuntos ya están instalados; no se modificó nada.")
    raise SystemExit(0)

stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
for ruta, antes, despues in ((main, old_main, new_main), (front, old_front, new_front)):
    if antes == despues:
        continue
    copia = ruta.with_name(ruta.name + f".antes_adjuntos_{stamp}.bak")
    shutil.copy2(ruta, copia)
    print("Respaldo:", copia)
    ruta.write_text(despues, encoding="utf-8")
    print("Actualizado:", ruta)
print("LISTO: /api/flujo/adjunto + carga de PDF, DOCX e imágenes desde el chat.")
print("No se modificaron SQLite, los contratos ni las plantillas.")
