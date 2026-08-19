import { useRef, useState } from 'react'

const LIMITE = 300   // mismo tope que valida el backend

const SUGERENCIAS = [
  'tengo resaca',
  'algo caldoso y barato',
  'picante para compartir',
  'algo dulce para la noche',
  'ligero y fresco para el calor',
]

export default function CravingForm({ busy, onSearch }) {
  const [texto, setTexto] = useState('')
  const input = useRef(null)
  const quedan = LIMITE - texto.length

  const enviar = (valor) => {
    const t = valor.trim()
    if (!t) input.current.focus()
    onSearch(t)
  }

  const elegirChip = (s) => {
    setTexto(s)
    enviar(s)
  }

  return (
    <>
      <form onSubmit={(e) => { e.preventDefault(); if (!busy) enviar(texto) }} noValidate>
        <div className="field">
          <label htmlFor="craving">Tu antojo, en tus palabras</label>
          <textarea
            id="craving" name="craving" ref={input}
            value={texto} onChange={(e) => setTexto(e.target.value)}
            maxLength={LIMITE} autoComplete="off"
            placeholder="algo picante y reconfortante, bajo 25 soles"
          />
          <span className={'count' + (quedan <= 20 ? ' over' : '')}>
            quedan {quedan} de {LIMITE}
          </span>
        </div>
        <button className="go" type="submit" disabled={busy}>
          {busy ? 'Buscando…' : 'Girar la brújula'}
        </button>
      </form>

      <nav className="chips" aria-labelledby="chips-title">
        <p id="chips-title">O prueba con uno de estos</p>
        <ul>
          {SUGERENCIAS.map((s) => (
            <li key={s}>
              <button type="button" className="chip" disabled={busy} onClick={() => elegirChip(s)}>{s}</button>
            </li>
          ))}
        </ul>
      </nav>
    </>
  )
}
