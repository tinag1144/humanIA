import { useCallback, useEffect, useRef, useState } from 'react'

import type { FormEvent } from 'react'

import {

  Activity, ArrowDownToLine, ArrowLeft, ArrowRight, BadgeCheck, Bot, BriefcaseBusiness,

  Check, CheckCircle2, ChevronDown, CircleAlert, Clock3, Database, FileCheck2,

  FileClock, FilePlus2, FileSearch, FileText, Files, Fingerprint, LayoutDashboard,

  LoaderCircle, LockKeyhole, LogOut, Menu, MessageCircle, Plus, RefreshCw,

  Search, Send, Paperclip, ShieldCheck, Sparkles, UserRound, WandSparkles, X

} from 'lucide-react'

import { ApiError, ChatResult, Contract, Draft, download, login, request } from './api'



type Page = 'inicio' | 'agente' | 'contratos' | 'documentacion'

type ChatLine = { id: number; role: 'user' | 'agent'; text: string; herramientas?: string[] }

type HistoryItem = { sesion_id: string; titulo: string; actualizado: string }
type SavedChat = { sesion_id: string; titulo: string; mensajes: { role: 'user' | 'agent'; text: string; herramientas: string[] }[] }

type FormData = Record<string, string>



const fields: { name: string; label: string; placeholder?: string; type?: string; full?: boolean }[] = [

  { name: 'tipo_contrato', label: 'Tipo de contrato', placeholder: 'indeterminado' },

  { name: 'nombre_empleado', label: 'Nombre del empleado', placeholder: 'Martina López' },

  { name: 'dni_empleado', label: 'DNI del empleado', placeholder: '00.000.001' },

  { name: 'fecha_nacimiento', label: 'Fecha de nacimiento', type: 'date' },

  { name: 'domicilio_empleado', label: 'Domicilio del empleado', placeholder: 'Calle Ejemplo 456', full: true },

  { name: 'puesto', label: 'Puesto / función', placeholder: 'Analista de Sistemas' },

  { name: 'fecha_inicio', label: 'Fecha de inicio', type: 'date' },

  { name: 'jornada_laboral', label: 'Jornada laboral', placeholder: '40 horas semanales' },

  { name: 'remuneracion_bruta', label: 'Remuneración mensual bruta (ARS)', type: 'number', placeholder: '1800000' },

  { name: 'lugar_trabajo', label: 'Lugar de trabajo', placeholder: 'Córdoba, Argentina', full: true },

  { name: 'empleador', label: 'Razón social', placeholder: 'HumanIA S.A.' },

  { name: 'cuit_empleador', label: 'CUIT', placeholder: '30-00000000-0' },

  { name: 'domicilio_empleador', label: 'Domicilio del empleador', placeholder: 'Av. Ejemplo 1234', full: true }

]

// Validaciones de identificadores para el formulario manual.
// DNI de produccion: 7 u 8 digitos. Se admiten hasta 9 para datos ficticios
// previamente utilizados en las demostraciones (ej.: 00.000.004).
const soloDigitos = (valor: string) => valor.replace(/\D/g, '')

function formatearDni(valor: string): string {
  const digitos = soloDigitos(valor).slice(0, 9)
  return digitos.replace(/\B(?=(\d{3})+(?!\d))/g, '.')
}

function formatearCuit(valor: string): string {
  const n = soloDigitos(valor).slice(0, 11)
  return n.length <= 2 ? n : n.length <= 10
    ? `${n.slice(0, 2)}-${n.slice(2)}`
    : `${n.slice(0, 2)}-${n.slice(2, 10)}-${n.slice(10)}`
}

function validarIdentificadores(datos: FormData): string | null {
  const dni = soloDigitos(datos.dni_empleado || '')
  const cuit = soloDigitos(datos.cuit_empleador || '')
  if (!/^\d{7,9}$/.test(dni)) return 'El DNI debe tener entre 7 y 9 digitos (9 solo para pruebas ficticias).'
  if (!/^\d{11}$/.test(cuit)) return 'El CUIT debe tener exactamente 11 digitos.'
  return null
}

const initialForm = Object.fromEntries(fields.map(f => [f.name, f.name === 'tipo_contrato' ? 'indeterminado' : f.name === 'empleador' ? 'HumanIA S.A.' : ''])) as FormData



const labels: Record<string, string> = {

  en_conflicto: 'En conflicto', pendiente_confirmacion: 'Pendiente de confirmar',

  datos_confirmados: 'Datos confirmados', aprobado: 'Aprobado', rechazado: 'Rechazado'

}

function titleCase(value: string) { return labels[value] || value.replaceAll('_', ' ') }

function formatDate(value?: string | null) {

  if (!value) return '—'

  const d = new Date(value)

  return Number.isNaN(d.getTime()) ? value : new Intl.DateTimeFormat('es-AR', { day: '2-digit', month: 'short', year: 'numeric' }).format(d)

}

function getName(c: Contract) { return String(c.datos.nombre_empleado || 'Sin nombre') }

function money(value: unknown) {

  const n = Number(value)

  return Number.isFinite(n) ? new Intl.NumberFormat('es-AR', { style: 'currency', currency: 'ARS', maximumFractionDigits: 0 }).format(n) : '—'

}

const prompts = [

  '¿Qué datos necesito para preparar un contrato laboral?',

  '¿Quién puede aprobar un contrato según la documentación?',

  '¿Qué sucede cuando dos domicilios son contradictorios?'

]



function App() {

  const [token, setToken] = useState<string | null>(() => sessionStorage.getItem('humania_token'))

  const [page, setPage] = useState<Page>('inicio')

  const [usuario, setUsuario] = useState('')

  const [password, setPassword] = useState('')

  const [authError, setAuthError] = useState('')

  const [authLoading, setAuthLoading] = useState(false)

  const [me, setMe] = useState<{ usuario: string; rol: string } | null>(null)

  const [mobileOpen, setMobileOpen] = useState(false)

  const [contracts, setContracts] = useState<Contract[]>([])

  const [summary, setSummary] = useState<{ total: number; borradores: number; por_estado: Record<string, number> }>({ total: 0, borradores: 0, por_estado: {} })

  const [selected, setSelected] = useState<string | null>(null)

  const [drafts, setDrafts] = useState<Draft[]>([])
  const [draftsFor, setDraftsFor] = useState<string | null>(null)

  const [loadingData, setLoadingData] = useState(false)

  const [action, setAction] = useState('')

  const [error, setError] = useState('')

  const [notice, setNotice] = useState('')

  const [search, setSearch] = useState('')

  const [showForm, setShowForm] = useState(false)

  const [form, setForm] = useState<FormData>(initialForm)

  const [city, setCity] = useState('')

  const [signDate, setSignDate] = useState('')

  const [reason, setReason] = useState('Documento revisado y aprobado por Recursos Humanos para demostración académica.')

  const [chatLines, setChatLines] = useState<ChatLine[]>([{ id: 1, role: 'agent', text: '¡Hola! Soy HumanIA, tu asistente de Recursos Humanos. Puedo ayudarte a revisar datos contractuales y consultar la documentación disponible. ¿Qué necesitás hacer hoy?' }])

  const [chatInput, setChatInput] = useState('')

  const [chatSession, setChatSession] = useState<string | null>(null)
  const [history, setHistory] = useState<HistoryItem[]>([])
  const [historyTitle, setHistoryTitle] = useState('')
  const [dragging, setDragging] = useState(false)

  const [sending, setSending] = useState(false)

  const [adjunto, setAdjunto] = useState<File | null>(null)

  const [subiendoAdjunto, setSubiendoAdjunto] = useState(false)

  const adjuntoInput = useRef<HTMLInputElement>(null)

  const bottomRef = useRef<HTMLDivElement>(null)



  const refreshHistory = useCallback(async () => {
    if (!token) return
    try {
      const items = await request<HistoryItem[]>('/api/historial', token)
      setHistory(items)
    } catch { /* el historial no debe interrumpir el chat */ }
  }, [token])

  useEffect(() => { void refreshHistory() }, [refreshHistory])

  const openHistory = async (sesionId: string) => {
    if (!token || sending || subiendoAdjunto) return
    try {
      const saved = await request<SavedChat>(`/api/historial/${sesionId}`, token)
      setChatSession(saved.sesion_id)
      setHistoryTitle(saved.titulo)
      setChatLines(saved.mensajes.map((m, i) => ({
        id: i + 1, role: m.role, text: m.text, herramientas: m.herramientas
      })))
      setAdjunto(null)
      setError('')
    } catch (e) { setError((e as Error).message) }
  }

  const newConversation = () => {
    if (sending || subiendoAdjunto) return
    setChatSession(null)
    setHistoryTitle('')
    setChatInput('')
    setAdjunto(null)
    if (adjuntoInput.current) adjuntoInput.current.value = ''
    setChatLines([{ id: Date.now(), role: 'agent', text: '¡Hola! Iniciamos una nueva conversación. ¿En qué puedo ayudarte?' }])
  }

  const persistTurn = async (
    sesionId: string, title: string,
    messages: { role: 'user' | 'agent'; text: string; herramientas?: string[] }[]
  ) => {
    if (!token) return
    try {
      await request('/api/historial/turno', token, {
        method: 'POST',
        body: JSON.stringify({ sesion_id: sesionId, titulo: title, mensajes: messages })
      })
      void refreshHistory()
    } catch (e) {
      setNotice('La respuesta llegó, pero no se pudo guardar en el historial: ' + (e as Error).message)
    }
  }

  const acceptDrop = (file?: File | null) => {
    if (!file) return
    if (!/\.(pdf|docx|png|jpg|jpeg|webp)$/i.test(file.name)) {
      setError('Formato no admitido. Usá PDF, DOCX, PNG, JPG o WEBP.')
      return
    }
    if (file.size > 8 * 1024 * 1024) {
      setError('El archivo supera los 8 MB permitidos.')
      return
    }
    setError('')
    setAdjunto(file)
  }

  const resetMessages = () => { setError(''); setNotice('') }

  const signOut = useCallback(() => {

    sessionStorage.removeItem('humania_token')

    setToken(null); setMe(null); setSelected(null); setChatSession(null); setHistory([]); setHistoryTitle('')

  }, [])

  const loadAll = useCallback(async (currentToken: string) => {

    setLoadingData(true)

    try {

      const [list, total] = await Promise.all([

        request<Contract[]>('/api/interfaz/contratos', currentToken),

        request<typeof summary>('/api/interfaz/resumen', currentToken)

      ])

      setContracts(list); setSummary(total)

    } catch (e) {

      if (e instanceof ApiError && e.status === 401) signOut()

      else setError((e as Error).message)

    } finally { setLoadingData(false) }

  }, [signOut])



  useEffect(() => {

    if (!token) return

    request<{ usuario: string; rol: string }>('/api/yo', token)

      .then(data => { setMe(data); void loadAll(token) })

      .catch(() => signOut())

  }, [token, loadAll, signOut])

  useEffect(() => {
    // Ignorar respuestas tardias de otro contrato.
    let vigente = true
    setDrafts([])
    setDraftsFor(null)
    if (token && selected) {
      const contratoId = selected
      request<Draft[]>(`/api/interfaz/contratos/${encodeURIComponent(contratoId)}/borradores`, token)
        .then(lista => {
          if (!vigente) return
          if (!Array.isArray(lista) || lista.some(d => d.contrato_id !== contratoId)) {
            setError('El servidor devolvio borradores de otro contrato. Se bloqueo la visualizacion.')
            return
          }
          setDrafts(lista)
          setDraftsFor(contratoId)
        })
        .catch(e => { if (vigente) setError((e as Error).message) })
    }
    return () => { vigente = false }
  }, [selected, token, contracts])

  useEffect(() => { bottomRef.current?.scrollIntoView({ behavior: 'smooth' }) }, [chatLines, sending])



  const runAction = async (key: string, fn: () => Promise<unknown>, success: string) => {

    resetMessages(); setAction(key)

    try { await fn(); setNotice(success); if (token) await loadAll(token) }

    catch (e) { setError((e as Error).message) }

    finally { setAction('') }

  }

  const doLogin = async (event: FormEvent) => {

    event.preventDefault(); setAuthError(''); setAuthLoading(true)

    try { const t = await login(usuario.trim(), password); sessionStorage.setItem('humania_token', t); setToken(t); setPassword('') }

    catch (e) { setAuthError((e as Error).message) }

    finally { setAuthLoading(false) }

  }

  const doCreate = async (event: FormEvent) => {

    event.preventDefault()

    if (!token) return

    const mensajeValidacion = validarIdentificadores(form)
    if (mensajeValidacion) {
      setError(mensajeValidacion)
      return
    }

    await runAction('create', async () => {

      const datos = { ...form, remuneracion_bruta: Number(form.remuneracion_bruta) }

      const result = await request<{ contrato_id: string; estado: string }>('/api/interfaz/contratos', token, {

        method: 'POST', body: JSON.stringify({ datos })

      })

      if (!result.contrato_id) throw new Error('El servidor no devolvió el identificador del contrato.')

      setShowForm(false); setForm(initialForm); setSelected(result.contrato_id); setPage('contratos')

    }, 'Contrato creado. Los datos aún requieren confirmación humana.')

  }

  const selectContract = (id: string) => { resetMessages(); setDrafts([]); setDraftsFor(null); setCity(''); setSignDate(''); setSelected(id); setPage('contratos'); setMobileOpen(false) }

  const current = selected ? contracts.find(c => c.id === selected) : undefined
  const visibleDrafts = draftsFor === selected ? drafts : []

  const filtered = contracts.filter(c => `${getName(c)} ${c.id} ${c.estado}`.toLowerCase().includes(search.toLowerCase()))

  const go = (next: Page) => { setPage(next); setSelected(null); setDrafts([]); setDraftsFor(null); setMobileOpen(false); resetMessages() }

  const generarBorradorSeleccionado = async (contrato: Contract) => {
    if (!token || !selected || contrato.id !== selected) {
      throw new Error('La seleccion del contrato cambio. Volve a abrir la ficha.')
    }
    const ciudad = city.trim()
    if (!ciudad || !signDate) {
      throw new Error('Ingresa ciudad y fecha de firma.')
    }
    // Contrastar el registro autentico en el servidor antes de escribir.
    const original = await request<Contract>(`/api/contratos/${encodeURIComponent(contrato.id)}`, token)
    if (original.id !== selected || original.id !== contrato.id ||
        getName(original) !== getName(contrato) ||
        String(original.datos.dni_empleado || '') !== String(contrato.datos.dni_empleado || '')) {
      throw new Error('Los datos del contrato no coinciden con los del servidor. Operacion cancelada.')
    }
    if (original.estado !== 'datos_confirmados') {
      throw new Error('El contrato ya no esta en estado datos_confirmados. Actualiza la pantalla.')
    }
    const aceptado = window.confirm(
      `Vas a generar un borrador de:\n${getName(original)}\n` +
      `DNI: ${String(original.datos.dni_empleado || '—')}\n` +
      `Contrato: ${original.id}\nCiudad: ${ciudad}\nFecha: ${signDate}\n\n¿Continuar?`
    )
    if (!aceptado) throw new Error('Generacion cancelada. No se creo ningun borrador.')
    await request(`/api/interfaz/contratos/${encodeURIComponent(original.id)}/borradores`, token, {
      method: 'POST',
      body: JSON.stringify({ ciudad_firma: ciudad, fecha_firma: signDate })
    })
  }

  const doSend = async (message = chatInput) => {

    const texto = message.trim(); if (!texto || !token || sending) return

    setChatInput(''); setSending(true); setError('')

    setChatLines(lines => [...lines, { id: Date.now(), role: 'user', text: texto }])

    try {

      const result = await request<ChatResult>('/api/flujo/chat', token, {

        method: 'POST', body: JSON.stringify({ mensaje: texto, sesion_id: chatSession })

      })

      setChatSession(result.sesion_id)
      const title = historyTitle || texto.slice(0, 80)
      setHistoryTitle(title)
      await persistTurn(result.sesion_id, title, [
        { role: 'user', text: texto },
        { role: 'agent', text: result.mensaje, herramientas: result.herramientas }
      ])

      setChatLines(lines => [...lines, { id: Date.now() + 1, role: 'agent', text: result.mensaje, herramientas: result.herramientas }])

    } catch (e) {

      setChatLines(lines => [...lines, { id: Date.now() + 2, role: 'agent', text: `No pude completar la consulta: ${(e as Error).message}` }])

    } finally { setSending(false) }

  }



  const subirAdjunto = async () => {

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
      const title = historyTitle || ('Archivo: ' + file.name).slice(0, 90)
      setHistoryTitle(title)
      await persistTurn(parsed.sesion_id, title, [
        { role: 'user', text: 'Adjunto: ' + file.name },
        { role: 'agent', text: parsed.mensaje, herramientas: parsed.herramientas }
      ])

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



  if (!token) return (

    <div className="login-page">

      <div className="login-left">

        <div className="brand brand-light"><div className="brand-mark"><Sparkles size={22} /></div><span>Human<span className="brand-accent">IA</span><small>INTELLIGENT HR WORKSPACE</small></span></div>

        <div className="login-hero"><div className="eyebrow dark"><span className="eyebrow-dot"/> RECURSOS HUMANOS · IA LOCAL</div><h1>Personas primero.<br/><em>Inteligencia</em> para todo lo demás.</h1><p>Una forma más inteligente y segura de gestionar contratos laborales, con el control siempre en manos de las personas.</p><div className="hero-pills"><span><ShieldCheck size={17}/> Validación humana</span><span><Fingerprint size={17}/> Integridad SHA-256</span><span><Bot size={17}/> Ollama + RAG</span></div></div>

        <div className="login-footer">HUMANIA S.A. <span>·</span> ENTORNO ACADÉMICO DE DEMOSTRACIÓN</div>

        <div className="hero-orb orb-a"/><div className="hero-orb orb-b"/><div className="hero-grid"/>

      </div>

      <div className="login-right"><div className="login-card"><div className="login-symbol"><LockKeyhole size={26}/></div><div className="eyebrow">ACCESO AL SISTEMA</div><h2>Bienvenido de nuevo</h2><p>Ingresá con tu cuenta de Recursos Humanos para continuar.</p><form onSubmit={doLogin}><label>Usuario<input value={usuario} onChange={e=>setUsuario(e.target.value)} required autoComplete="username" placeholder="Tu usuario de RR. HH." /></label><label>Contraseña<input type="password" value={password} onChange={e=>setPassword(e.target.value)} required autoComplete="current-password" placeholder="••••••••" /></label>{authError&&<div className="error-box"><CircleAlert size={17}/>{authError}</div>}<button className="btn primary full" type="submit" disabled={authLoading}>{authLoading?<LoaderCircle className="spin" size={18}/>:<ArrowRight size={18}/>} Ingresar al espacio</button></form><div className="login-hint"><ShieldCheck size={16}/> Acceso exclusivo para responsables autorizados</div></div><div className="right-footer">HumanIA <span>© 2026 · Proyecto académico</span></div></div>

    </div>

  )



  const nav = [

    { id: 'inicio' as Page, label: 'Resumen', Icon: LayoutDashboard },

    { id: 'agente' as Page, label: 'Asistente IA', Icon: MessageCircle },

    { id: 'contratos' as Page, label: 'Contratos', Icon: Files },

    { id: 'documentacion' as Page, label: 'Base de conocimiento', Icon: Database }

  ]



  return <div className="app-shell">

    {mobileOpen && <div className="mobile-overlay" onClick={()=>setMobileOpen(false)}/>}

    <aside className={`sidebar ${mobileOpen?'open':''}`}>

      <div className="brand"><div className="brand-mark"><Sparkles size={22}/></div><span>Human<span className="brand-accent">IA</span><small>HR INTELLIGENCE</small></span></div>

      <div className="sidebar-section-label">ESPACIO DE TRABAJO</div>

      <nav className="sidebar-nav">{nav.map(({id,label,Icon})=><button key={id} className={`nav-link ${page===id?'active':''}`} onClick={()=>go(id)}><Icon size={19}/><span>{label}</span>{page===id&&<span className="nav-active-dot"/>}</button>)}</nav>

      <div className="sidebar-spacer"/>

      <div className="sidebar-secure"><div className="secure-bubble"><ShieldCheck size={19}/></div><div><strong>Entorno protegido</strong><p>Operaciones con revisión humana y trazabilidad.</p></div></div>

      <div className="sidebar-user"><div className="user-avatar">{(me?.usuario || usuario || 'R').charAt(0).toUpperCase()}</div><div className="sidebar-user-info"><strong>{me?.usuario || 'Responsable RR. HH.'}</strong><span>{me?.rol?.toUpperCase() || 'RR. HH.'}</span></div><button className="icon-button logout" aria-label="Cerrar sesión" title="Cerrar sesión" onClick={signOut}><LogOut size={19}/></button></div>

    </aside>

    <div className="main-area"><header className="topbar"><div className="topbar-left"><button className="icon-button mobile-menu" aria-label="Menú" onClick={()=>setMobileOpen(true)}><Menu size={23}/></button><div className="breadcrumb">HumanIA <span>/</span> <strong>{nav.find(n=>n.id===page)?.label}</strong></div></div><div className="topbar-right"><div className="system-status"><span/> Sistema local</div><span className="topbar-divider"/><div className="top-avatar">{(me?.usuario || 'R').charAt(0).toUpperCase()}</div></div></header>

      <main className={`page-content ${page==='agente'?'chat-page':''}`}>

        {(error||notice) && <div className={`toast ${error?'is-error':'is-success'}`}><span>{error?<CircleAlert size={19}/>:<CheckCircle2 size={19}/>}</span><p>{error||notice}</p><button aria-label="Cerrar aviso" onClick={resetMessages}><X size={17}/></button></div>}

        {page==='inicio' && <>

          <div className="page-head"><div><div className="eyebrow">PANEL GENERAL</div><h1>Tu espacio de trabajo<span className="heading-dot">.</span></h1><p>Supervisá contratos, revisiones y consultas desde un solo lugar.</p></div><button className="btn primary" onClick={()=>{setShowForm(true);resetMessages()}}><Plus size={18}/> Nuevo contrato</button></div>

          <section className="welcome-banner"><div className="banner-copy"><div className="banner-eyebrow"><span/> HUMANIA INTELLIGENCE</div><h2>La tecnología acompaña.<br/><span>Las personas deciden.</span></h2><p>Un entorno de trabajo inteligente con trazabilidad, validación humana y control sobre cada documento.</p><button className="btn light" onClick={()=>go('agente')}>Conversar con HumanIA <ArrowRight size={17}/></button></div><div className="banner-art"><div className="banner-ring ring-1"/><div className="banner-ring ring-2"/><div className="banner-emblem"><Sparkles size={51}/></div></div></section>

          <div className="stat-grid"><Stat label="Contratos registrados" value={summary.total} Icon={Files} tone="blue" hint="En el sistema"/><Stat label="Aprobados" value={summary.por_estado.aprobado||0} Icon={BadgeCheck} tone="green" hint="Con revisión humana"/><Stat label="Pendientes" value={(summary.por_estado.pendiente_confirmacion||0)+(summary.por_estado.datos_confirmados||0)} Icon={Clock3} tone="amber" hint="Requieren atención"/><Stat label="Borradores generados" value={summary.borradores} Icon={FileText} tone="violet" hint="Versiones auditadas"/></div>

          <div className="two-column"><section className="panel"><div className="panel-head"><div><h3>Contratos recientes</h3><p>Últimos registros del sistema</p></div><button className="text-link" onClick={()=>go('contratos')}>Ver todos <ArrowRight size={15}/></button></div><div className="recent-list">{contracts.slice(0,5).map(c=><button className="recent-item" key={c.id} onClick={()=>selectContract(c.id)}><div className="doc-icon"><FileText size={21}/></div><div><strong>{getName(c)}</strong><span>{String(c.datos.puesto||'Sin puesto')} · {c.id.slice(0,8)}</span></div><Status value={c.estado}/><ArrowRight className="recent-arrow" size={18}/></button>)}{contracts.length===0&&<Empty Icon={Files} text="Todavía no hay contratos. Creá el primero."/>}</div></section><section className="panel quick-panel"><div className="panel-head"><div><h3>Accesos rápidos</h3><p>Continuá tu trabajo</p></div></div><button className="quick-link" onClick={()=>go('agente')}><span className="quick-icon purple"><Bot size={22}/></span><span><strong>Consultar al agente</strong><small>Preguntas, revisión de datos y RAG</small></span><ArrowRight size={18}/></button><button className="quick-link" onClick={()=>{setShowForm(true);resetMessages()}}><span className="quick-icon blue"><FilePlus2 size={22}/></span><span><strong>Preparar un contrato</strong><small>Registrar información laboral</small></span><ArrowRight size={18}/></button><button className="quick-link" onClick={()=>go('documentacion')}><span className="quick-icon mint"><Database size={22}/></span><span><strong>Base de conocimiento</strong><small>Fuentes y recuperación semántica</small></span><ArrowRight size={18}/></button></section></div>

        </>}

        {page==='agente' && <><div className="page-head chat-heading"><div><div className="eyebrow">ASISTENTE INTELIGENTE</div><h1>Conversá con HumanIA<span className="heading-dot">.</span></h1><p>Validá información y consultá documentación con inteligencia artificial local.</p></div><button className="btn secondary" onClick={newConversation} disabled={sending||subiendoAdjunto}><RefreshCw size={17}/> Nueva conversación</button></div><div className="chat-layout"><section className={dragging?'chat-card chat-drop-active':'chat-card'} onDragEnter={e=>{e.preventDefault();setDragging(true)}} onDragOver={e=>{e.preventDefault();e.dataTransfer.dropEffect='copy';setDragging(true)}} onDragLeave={e=>{e.preventDefault();if(!e.currentTarget.contains(e.relatedTarget as Node))setDragging(false)}} onDrop={e=>{e.preventDefault();e.stopPropagation();setDragging(false);acceptDrop(e.dataTransfer.files?.[0])}}><div className="chat-card-head"><div className="agent-avatar"><Sparkles size={22}/></div><div><strong>HumanIA Assistant</strong><span><i/> Agente local · Qwen 2.5 7B</span></div><span className="chat-head-badge"><ShieldCheck size={14}/> Supervisado</span></div><div className="history-strip"><div className="history-head"><strong>Conversaciones anteriores</strong><button type="button" onClick={()=>void refreshHistory()} title="Actualizar historial"><RefreshCw size={15}/></button></div><div className="history-items">{history.map(item=><button type="button" className={chatSession===item.sesion_id?'active':''} key={item.sesion_id} onClick={()=>void openHistory(item.sesion_id)} disabled={sending||subiendoAdjunto}><MessageCircle size={15}/><span>{item.titulo}</span></button>)}{history.length===0&&<small>Las próximas conversaciones aparecerán acá.</small>}</div></div><div className="chat-messages">{dragging&&<div className="drop-hint">Soltá el archivo para adjuntarlo</div>}{chatLines.map(line=><div key={line.id} className={`chat-line ${line.role}`}><div className="bubble-avatar">{line.role==='agent'?<Sparkles size={16}/>:<UserRound size={16}/>}</div><div className="bubble-body"><div className="bubble-name">{line.role==='agent'?'HumanIA':'Vos'}</div><div className="message-bubble">{line.text}</div>{line.herramientas&&line.herramientas.length>0&&<div className="tools-used"><Check size={14}/> Herramientas: {line.herramientas.join(', ')}</div>}</div></div>)}{sending&&<div className="chat-line agent"><div className="bubble-avatar"><Sparkles size={16}/></div><div className="bubble-body"><div className="bubble-name">HumanIA</div><div className="message-bubble thinking"><span/><span/><span/></div></div></div>}<div ref={bottomRef}/></div>{chatLines.length<3&&<div className="suggestions"><span>PROBÁ PREGUNTANDO</span><div>{prompts.map(prompt=><button key={prompt} onClick={()=>void doSend(prompt)} disabled={sending}>{prompt}<ArrowRight size={14}/></button>)}</div></div>}<div style={{display:'flex',gap:8,alignItems:'center',padding:'8px 12px',flexWrap:'wrap'}}>

  <input ref={adjuntoInput} type="file" accept=".pdf,.docx,.png,.jpg,.jpeg,.webp" style={{display:'none'}}

    onChange={e=>acceptDrop(e.target.files?.[0])} />

  <span className="drop-label">También podés arrastrar un archivo al chat · Máx. 8 MB</span><button type="button" className="btn secondary" disabled={sending||subiendoAdjunto}

    onClick={()=>adjuntoInput.current?.click()}><Paperclip size={16}/> Elegir PDF, Word o imagen</button>

  {adjunto&&<><span style={{fontSize:12,wordBreak:'break-all'}}>{adjunto.name}</span><button type="button" className="btn subtle" onClick={()=>{setAdjunto(null);if(adjuntoInput.current)adjuntoInput.current.value=''}} aria-label="Quitar archivo"><X size={16}/></button>

    <button type="button" className="btn primary" disabled={sending||subiendoAdjunto}

      onClick={()=>void subirAdjunto()}>{subiendoAdjunto?'Analizando…':'Analizar adjunto'}</button></>}

</div><form className="chat-input-box" onSubmit={e=>{e.preventDefault();void doSend()}}><input value={chatInput} onChange={e=>setChatInput(e.target.value)} placeholder="Escribí tu consulta sobre contratos..." disabled={sending} maxLength={3000}/><button type="submit" className="send-button" aria-label="Enviar mensaje" disabled={sending||!chatInput.trim()}>{sending?<LoaderCircle size={20} className="spin"/>:<Send size={19}/>}</button></form><div className="chat-disclaimer"><LockKeyhole size={13}/> Las respuestas del agente no constituyen aprobaciones ni asesoramiento legal.</div></section><aside className="chat-side"><div className="side-help"><div className="small-icon"><WandSparkles size={21}/></div><h3>¿Qué puede hacer?</h3><p>HumanIA te acompaña durante el proceso contractual.</p><ul><li><Check size={16}/> Detectar datos faltantes</li><li><Check size={16}/> Identificar contradicciones</li><li><Check size={16}/> Consultar fuentes RAG</li><li><Check size={16}/> Explicar procedimientos</li></ul></div><div className="side-protection"><ShieldCheck size={20}/><div><strong>Control humano obligatorio</strong><p>El agente no puede aprobar, firmar ni alterar contratos.</p></div></div></aside></div></>}

        {page==='contratos' && <><div className="page-head"><div><div className="eyebrow">GESTIÓN CONTRACTUAL</div><h1>{selected&&current?'Detalle del contrato':'Contratos laborales'}<span className="heading-dot">.</span></h1><p>{selected?'Validación, borradores y decisiones humanas.':'Administrá y supervisá las versiones de cada contrato.'}</p></div><div className="head-actions">{selected&&<button className="btn secondary" onClick={()=>setSelected(null)}><ArrowLeft size={18}/> Volver</button>}<button className="btn primary" onClick={()=>setShowForm(true)}><Plus size={18}/> Nuevo contrato</button></div></div>{selected&&current?<div className="detail-grid"><div className="detail-main"><section className="panel"><div className="detail-title"><div className="detail-icon"><FileText size={25}/></div><div><h3>{getName(current)}</h3><span>Contrato #{current.id.slice(0,8)}</span></div><Status value={current.estado}/></div><div className="details-section-title">INFORMACIÓN CONTRACTUAL</div><div className="details-fields">{fields.filter(f=>f.name!=='tipo_contrato').map(f=><div key={f.name}><span>{f.label}</span><strong>{f.name==='remuneracion_bruta'?money(current.datos[f.name]):String(current.datos[f.name]??'—')}</strong></div>)}</div></section><section className="panel"><div className="panel-head"><div><h3>Borradores y versiones</h3><p>Historial de archivos DOCX auditados</p></div><span className="count-badge">{visibleDrafts.length}</span></div>{visibleDrafts.map(d=><div className="draft-item" key={d.id}><div className="doc-icon"><FileCheck2 size={23}/></div><div className="draft-info"><strong>Borrador #{d.id} · Versión {d.version}</strong><span>{d.archivo}</span><small>{formatDate(d.fecha_generacion)}</small></div><button className="btn secondary" title="Descarga el archivo original, incluso después de la aprobación; no es la copia aprobada." disabled={!!action} onClick={() => { if (!token || !selected || d.contrato_id !== selected) { setError('Borrador no asociado al contrato seleccionado.'); return }; void runAction(`revision-${d.id}`, () => download(`/api/borradores/${d.id}/revision-docx`, token), "Borrador descargado para revisión. La aprobación sigue pendiente."); }}><ArrowDownToLine size={16}/> Original para revisión</button><Status value={d.decision || 'pendiente_confirmacion'}/></div>)}{visibleDrafts.length===0&&<Empty Icon={FileClock} text="No hay borradores generados para este contrato."/>}</section></div><aside className="detail-side"><section className="panel control-panel"><h3>Acciones disponibles</h3><p>Contrato seleccionado: <strong>{getName(current)}</strong> · {current.id.slice(0, 8)}</p><p>Las decisiones requieren autorización humana.</p>{current.estado==='pendiente_confirmacion'&&<button className="btn primary full" disabled={!!action} onClick={()=>{if(!window.confirm('¿Revisaste y confirmás manualmente todos los datos?'))return;void runAction('confirmar',()=>request(`/api/contratos/${current.id}/confirmar-datos`,token,{method:'POST'}),'Datos confirmados por Recursos Humanos.')}}><CheckCircle2 size={18}/> {action==='confirmar'?'Confirmando…':'Confirmar datos'}</button>}{current.estado==='datos_confirmados'&&<form className="action-form" onSubmit={e=>{e.preventDefault();void runAction('borrador',()=>generarBorradorSeleccionado(current),'Borrador creado y registrado. Revisá el archivo antes de aprobarlo.')}}><label>Ciudad de firma<input value={city} onChange={e=>setCity(e.target.value)} maxLength={100} required/></label><label>Fecha de firma<input type="date" value={signDate} onChange={e=>setSignDate(e.target.value)} required/></label><button className="btn primary full" disabled={!!action} type="submit"><FilePlus2 size={18}/>{action==='borrador'?'Generando…':'Generar borrador'}</button></form>}{current.estado==='en_conflicto'&&<div className="warning-note"><CircleAlert size={17}/> Hay inconsistencias. Resolvelas mediante el procedimiento autorizado antes de continuar.</div>}{visibleDrafts.length>0&&visibleDrafts[0].decision===null&&current.estado==='datos_confirmados'&&<div className="approval-area"><div className="section-separator"/><span className="form-kicker">REVISIÓN HUMANA · BORRADOR #{visibleDrafts[0].id}</span><label>Justificación<textarea rows={3} value={reason} onChange={e=>setReason(e.target.value)} required/></label><button className="btn success full" disabled={!!action} onClick={()=>{if(!selected || current.id!==selected || visibleDrafts[0]?.contrato_id!==selected) {setError('El borrador no corresponde al contrato seleccionado.');return;} if(!window.confirm('Confirmá que revisaste la versión del DOCX y autorizás la aprobación interna.'))return;void runAction('aprobar',()=>request(`/api/borradores/${visibleDrafts[0].id}/aprobar`,token,{method:'POST',body:JSON.stringify({motivo:reason})}),'Aprobación humana registrada.') }}><BadgeCheck size={18}/> Aprobar versión</button><button className="btn danger-outline full" disabled={!!action||reason.trim().length<10} onClick={()=>{if(!selected || current.id!==selected || visibleDrafts[0]?.contrato_id!==selected) {setError('El borrador no corresponde al contrato seleccionado.');return;} if(!window.confirm('¿Rechazar este borrador?'))return;void runAction('rechazar',()=>request(`/api/borradores/${visibleDrafts[0].id}/rechazar`,token,{method:'POST',body:JSON.stringify({motivo:reason})}),'Borrador rechazado.') }}><X size={18}/> Rechazar versión</button></div>}{current.estado==='aprobado'&&visibleDrafts.some(d=>d.decision==='aprobar')&&<><div className="section-separator"/><div className="approval-ok"><BadgeCheck size={20}/> Aprobación interna registrada</div><span className="form-kicker">COPIAS DE PRESENTACIÓN APROBADAS</span><p className="export-guidance">Usá estos botones para obtener la versión con aprobación interna. El botón «Original para revisión» conserva siempre el borrador auditado.</p>{(()=>{const d=visibleDrafts.find(x=>x.decision==='aprobar')!;return <><button className="btn secondary full" onClick={()=>void runAction('docx',()=>download(`/api/borradores/${d.id}/descargar-docx`,token),'Descarga DOCX iniciada.')}><ArrowDownToLine size={18}/> DOCX aprobado</button><button className="btn secondary full" onClick={()=>void runAction('pdf',()=>download(`/api/borradores/${d.id}/descargar-pdf`,token),'Descarga PDF iniciada.')}><ArrowDownToLine size={18}/> PDF aprobado</button><button className="btn secondary full" onClick={()=>void runAction('constancia',()=>download(`/api/borradores/${d.id}/constancia-aprobacion`,token),'Constancia descargada.')}><FileCheck2 size={18}/> Constancia de aprobación</button></>})()}</>}{current.estado==='rechazado'&&<div className="warning-note"><CircleAlert size={17}/> Este contrato fue rechazado. La versión rechazada no se puede descargar como aprobada.</div>}</section><div className="side-protection"><Fingerprint size={19}/><div><strong>Protegido con SHA-256</strong><p>Los documentos aprobados se comprueban antes de su descarga.</p></div></div></aside></div>:<section className="panel contracts-panel"><div className="list-toolbar"><div className="search-box"><Search size={18}/><input placeholder="Buscar por empleado, estado o identificador..." value={search} onChange={e=>setSearch(e.target.value)}/></div><button className="btn subtle" onClick={()=>token&&void loadAll(token)} disabled={loadingData}><RefreshCw size={17} className={loadingData?'spin':''}/> Actualizar</button></div><div className="table-wrap"><table className="contracts-table"><thead><tr><th>EMPLEADO</th><th>PUESTO</th><th>REMUNERACIÓN</th><th>ESTADO</th><th></th></tr></thead><tbody>{filtered.map(c=><tr key={c.id} onClick={()=>selectContract(c.id)}><td><div className="table-person"><span className="person-avatar">{getName(c).charAt(0)}</span><div><strong>{getName(c)}</strong><small>#{c.id.slice(0,8)}</small></div></div></td><td>{String(c.datos.puesto||'—')}</td><td>{money(c.datos.remuneracion_bruta)}</td><td><Status value={c.estado}/></td><td><ArrowRight size={17}/></td></tr>)}</tbody></table>{filtered.length===0&&<Empty Icon={FileSearch} text="No se encontraron contratos."/>}</div></section>}</>}

        {page==='documentacion'&&<><div className="page-head"><div><div className="eyebrow">CONOCIMIENTO INSTITUCIONAL</div><h1>Base documental<span className="heading-dot">.</span></h1><p>Recuperación semántica local conectada al agente de HumanIA.</p></div><button className="btn primary" onClick={()=>go('agente')}><MessageCircle size={18}/> Preguntar al agente</button></div><div className="knowledge-hero"><div className="knowledge-icon"><Database size={27}/></div><div><h2>Recuperación aumentada por generación</h2><p>HumanIA consulta fragmentos relevantes indexados con Ollama y SQLite. Los documentos recuperados son fuentes de datos, no instrucciones.</p></div><div className="knowledge-tag"><Activity size={15}/> RAG LOCAL</div></div><div className="knowledge-cards"><div className="knowledge-card"><div className="knowledge-symbol purple"><Database size={23}/></div><h3>Índice vectorial</h3><p>SQLite en <code>base_vectorial/rag.db</code>. Búsqueda mediante similitud del coseno.</p></div><div className="knowledge-card"><div className="knowledge-symbol blue"><Sparkles size={23}/></div><h3>Embeddings locales</h3><p>Modelo <code>nomic-embed-text:latest</code> a través de Ollama.</p></div><div className="knowledge-card"><div className="knowledge-symbol mint"><ShieldCheck size={23}/></div><h3>Fuentes protegidas</h3><p>Control de integridad SHA-256 y detección de contenido sospechoso.</p></div></div><section className="panel knowledge-note"><div className="doc-icon"><FileText size={24}/></div><div><h3>Documento de demostración</h3><p><strong>procedimiento_rrhh_demo.txt</strong> fue utilizado para comprobar la recuperación semántica. Es ficticio y no constituye una política oficial.</p><span>Para incorporar nuevos documentos, utilizá la carpeta <code>documentos/</code> y ejecutá <code>python indexar.py</code> desde el proyecto.</span></div></section><div className="knowledge-warning"><CircleAlert size={20}/><span>Las respuestas de la IA deben verificarse. Ningún documento del RAG puede otorgar permisos de aprobación o firma.</span></div></>}

      </main>

    </div>

    {showForm&&<div className="modal-backdrop" onMouseDown={e=>{if(e.target===e.currentTarget)setShowForm(false)}}><div className="modal-dialog"><div className="modal-head"><div><div className="eyebrow">NUEVO REGISTRO</div><h2>Preparar contrato</h2><p>Ingresá datos ficticios o autorizados. Se registrarán pendientes de confirmación.</p></div><button className="icon-button" onClick={()=>setShowForm(false)} aria-label="Cerrar"><X size={21}/></button></div><form onSubmit={doCreate}><div className="modal-body"><div className="form-section-label"><BriefcaseBusiness size={18}/> Información del contrato</div><div className="form-grid">{fields.map((f,i)=><div key={f.name} className={`field ${f.full?'field-full':''} ${i===10?'section-start':''}`}>{i===10&&<div className="form-section-label"><Files size={18}/> Datos del empleador</div>}<label htmlFor={f.name}>{f.label}</label>{f.name==='tipo_contrato'?<div className="select-wrap"><select id={f.name} value={form[f.name]} onChange={e=>setForm({...form,[f.name]:e.target.value})}><option value="indeterminado">Por tiempo indeterminado</option></select><ChevronDown size={16}/></div>:<input id={f.name} type={f.type||'text'} required step={f.type==='number'?'any':undefined} min={f.type==='number'?'0':undefined} placeholder={f.placeholder||''} value={form[f.name]} onChange={e=>setForm({...form,[f.name]:f.name==='dni_empleado' ? formatearDni(e.target.value) : f.name==='cuit_empleador' ? formatearCuit(e.target.value) : e.target.value})} maxLength={f.name==='dni_empleado'?11:f.name==='cuit_empleador'?13:undefined} inputMode={f.name==='dni_empleado'||f.name==='cuit_empleador'?'numeric':undefined} pattern={f.name==='dni_empleado'?'[0-9.]{7,11}':f.name==='cuit_empleador'?'[0-9]{2}-[0-9]{8}-[0-9]':undefined} title={f.name==='dni_empleado'?'DNI de 7 u 8 digitos; se aceptan 9 solo para pruebas ficticias':f.name==='cuit_empleador'?'CUIT de 11 digitos: XX-XXXXXXXX-X':undefined}/>}</div>)}</div></div><div className="modal-foot"><span><ShieldCheck size={16}/> Requiere confirmación humana posterior</span><button className="btn secondary" type="button" onClick={()=>setShowForm(false)}>Cancelar</button><button className="btn primary" type="submit" disabled={!!action}>{action==='create'?<LoaderCircle size={17} className="spin"/>:<Plus size={17}/>} Crear contrato</button></div></form></div></div>}

  </div>

}



function Status({value}:{value:string}) {

  const tone = value==='aprobado'||value==='aprobar'?'approved':value==='rechazado'||value==='rechazar'?'rejected':value==='en_conflicto'?'conflict':value==='datos_confirmados'?'confirmed':'pending'

  return <span className={`status ${tone}`}><span className="status-dot"/>{value==='aprobar'?'Aprobado':value==='rechazar'?'Rechazado':titleCase(value)}</span>

}

function Stat({label,value,Icon,tone,hint}:{label:string;value:number;Icon:typeof Files;tone:string;hint:string}) {

  return <div className="stat-card"><div className={`stat-icon ${tone}`}><Icon size={22}/></div><span className="stat-label">{label}</span><strong>{value}</strong><small>{hint}</small></div>

}

function Empty({Icon,text}:{Icon:typeof Files;text:string}) {

  return <div className="empty-state"><Icon size={26}/><p>{text}</p></div>

}

export default App
