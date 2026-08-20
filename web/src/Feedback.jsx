import { useEffect, useId, useRef, useState } from 'react'
import { enviarFeedback } from './api.js'

const LIMITE = 300   // mismo tope que valida el backend

// el usuario reporta en su idioma; los identificadores tecnicos se quedan aqui
const TIPOS = [
  ['no_existe', 'Ya no lo sirven'],
  ['precio', 'El precio cambió'],
  ['dato', 'Otro dato está mal'],
  ['agregar', 'Aquí sirven otro plato'],
]

// lo reportado sobrevive a una busqueda nueva: vive fuera del componente, no en el estado
const reportados = new Set()

// el backend manda plato y local sueltos; el id compuesto "{plato}#{distrito}#{osm_id}" es el respaldo
function claves(dish) {
  const partes = String(dish.id || '').split('#')
  return { plato: dish.plato || partes[0] || '', local: dish.local || partes.slice(1).join('#') }
}

export default function Feedback({ dish }) {
  const { plato, local } = claves(dish)
  const clave = plato + '#' + local

  const [abierto, setAbierto] = useState(false)
  const [enviado, setEnviado] = useState(() => reportados.has(clave))
  const [tipo, setTipo] = useState('')
  const [comentario, setComentario] = useState('')
  const [precio, setPrecio] = useState('')
  const [estado, setEstado] = useState(null)   // null | 'enviando' | {title,detail}

  const boton = useRef(null)
  const primerRadio = useRef(null)
  const gracias = useRef(null)
  const panelId = useId()
  const quedan = LIMITE - comentario.length

  // el foco sigue al panel al abrir, vuelve al boton al cerrar y aterriza en la confirmacion al enviar
  useEffect(() => { if (abierto) primerRadio.current?.focus() }, [abierto])
  useEffect(() => { if (enviado) gracias.current?.focus() }, [enviado])

  const cerrar = () => { setAbierto(false); setEstado(null); boton.current?.focus() }

  const enviar = async (e) => {
    e.preventDefault()
    if (estado === 'enviando') return
    if (!tipo) { setEstado({ title: 'Falta el motivo', detail: 'Elige qué está mal en este plato.' }); return }
    const soles = Number(precio)
    if (tipo === 'precio' && !(soles > 0)) {
      setEstado({ title: 'Falta el precio', detail: 'Escribe el precio que viste, en soles.' })
      return
    }

    setEstado('enviando')
    try {
      await enviarFeedback({
        local, plato, tipo,
        ...(comentario.trim() ? { comentario: comentario.trim() } : {}),
        ...(tipo === 'precio' ? { precio_sugerido: soles } : {}),
      })
      reportados.add(clave)
      setEnviado(true)
    } catch (err) {
      setEstado(err && err.title
        ? err
        : { title: 'No pudimos enviar tu reporte', detail: 'Vuelve a intentar en un momento.' })
    }
  }

  if (!local) return null   // sin local no hay nada que corregir

  if (enviado) {
    return (
      <p className="fb-ok" role="status" tabIndex={-1} ref={gracias}>
        Gracias, lo revisamos esta noche.
      </p>
    )
  }

  return (
    <div className="fb">
      <button
        type="button" className="fb-abrir" ref={boton}
        aria-expanded={abierto} aria-controls={abierto ? panelId : undefined}
        onClick={() => (abierto ? cerrar() : setAbierto(true))}
      >
        ¿Algo no cuadra con este plato?
      </button>

      {abierto && (
        <form
          className="fb-panel" id={panelId} noValidate onSubmit={enviar}
          onKeyDown={(e) => { if (e.key === 'Escape') cerrar() }}
        >
          <fieldset>
            <legend>¿Qué está mal?</legend>
            {TIPOS.map(([valor, texto], i) => (
              <label key={valor} className="fb-opcion">
                <input
                  type="radio" name={panelId + '-tipo'} value={valor}
                  ref={i === 0 ? primerRadio : undefined}
                  checked={tipo === valor}
                  onChange={() => { setTipo(valor); setEstado(null) }}
                />
                <span>{texto}</span>
              </label>
            ))}
          </fieldset>

          {tipo === 'precio' && (
            <div className="fb-campo">
              <label htmlFor={panelId + '-precio'}>Precio que viste (soles)</label>
              <input
                id={panelId + '-precio'} type="number" min="1" step="0.5" inputMode="decimal"
                value={precio} onChange={(e) => setPrecio(e.target.value)} autoComplete="off"
              />
            </div>
          )}

          <div className="fb-campo">
            <label htmlFor={panelId + '-com'}>Comentario (opcional)</label>
            <textarea
              id={panelId + '-com'} rows={2} maxLength={LIMITE} autoComplete="off"
              value={comentario} onChange={(e) => setComentario(e.target.value)}
              placeholder="lo que viste en el local"
            />
            <span className={'count' + (quedan <= 20 ? ' over' : '')}>quedan {quedan} de {LIMITE}</span>
          </div>

          <div className="fb-acciones">
            <button type="submit" className="fb-enviar" disabled={estado === 'enviando'}>
              {estado === 'enviando' ? 'Enviando…' : 'Enviar reporte'}
            </button>
            <button type="button" className="fb-cancelar" onClick={cerrar}>Cancelar</button>
          </div>

          <p className="fb-estado" role="status" aria-live="polite">
            {estado && estado !== 'enviando' && <><strong>{estado.title}</strong>{estado.detail}</>}
          </p>
        </form>
      )}
    </div>
  )
}
