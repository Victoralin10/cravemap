import { useEffect, useRef, useState } from 'react'

const LIMA = { lat: -12.0464, lng: -77.0428 }   // centro de referencia para el rumbo
const REDUCED = window.matchMedia('(prefers-reduced-motion: reduce)').matches

// rumbo geografico real (grados desde el norte) del plato visto desde el centro de Lima
export function bearing(d) {
  if (!d || typeof d.lat !== 'number' || typeof d.lng !== 'number') return -18
  const r = Math.PI / 180
  const f1 = LIMA.lat * r, f2 = d.lat * r, dl = (d.lng - LIMA.lng) * r
  const y = Math.sin(dl) * Math.cos(f2)
  const x = Math.cos(f1) * Math.sin(f2) - Math.sin(f1) * Math.cos(f2) * Math.cos(dl)
  return Math.atan2(y, x) / r
}

// las 60 marcas de la rosa: una cada 6 grados, mayor cada 30
const TICKS = Array.from({ length: 60 }, (_, i) => {
  const major = i % 5 === 0
  const a = (i * 6 - 90) * Math.PI / 180
  const r1 = major ? 74 : 80
  return {
    major,
    x1: +(100 + r1 * Math.cos(a)).toFixed(1), y1: +(100 + r1 * Math.sin(a)).toFixed(1),
    x2: +(100 + 88 * Math.cos(a)).toFixed(1), y2: +(100 + 88 * Math.sin(a)).toFixed(1),
  }
})

/*
  spinning: true mientras se consulta -> la aguja gira buscando.
  heading:  al soltar spinning, grados a los que asentarse; null = quedarse donde este
            (asi el error deja la aguja rendida en su sitio).
*/
export default function Compass({ spinning, heading }) {
  const needle = useRef(null)
  const anim = useRef({ angle: -18, vel: 0, target: null, raf: 0, timer: 0, spinStart: 0 })
  const [settled, setSettled] = useState(false)

  useEffect(() => {
    const a = anim.current
    const draw = () => {
      if (needle.current) needle.current.setAttribute('transform', `rotate(${a.angle.toFixed(2)} 100 100)`)
    }
    draw()

    // ponytail: resorte amortiguado a ojo, no simulacion fisica.
    // Si alguien quiere realismo, tocar las constantes 13 / 0.014 / 0.87.
    const frame = () => {
      if (a.target === null) {              // buscando: acelera hasta velocidad de crucero
        a.vel += (13 - a.vel) * 0.05
        a.angle += a.vel
      } else {                              // encontrado: cae hacia el rumbo y rebota
        const d = ((a.target - a.angle) % 360 + 540) % 360 - 180
        a.vel = (a.vel + d * 0.014) * 0.87
        a.angle += a.vel
        if (Math.abs(d) < 0.08 && Math.abs(a.vel) < 0.08) {
          a.angle = a.target; a.vel = 0; a.raf = 0
          draw(); setSettled(true)
          return
        }
      }
      draw()
      a.raf = requestAnimationFrame(frame)
    }

    const settle = (deg) => {
      a.target = ((deg % 360) + 360) % 360 + Math.round(a.angle / 360) * 360
      if (REDUCED) { a.angle = a.target; a.vel = 0; draw(); setSettled(true); return }
      if (!a.raf) a.raf = requestAnimationFrame(frame)
    }

    if (spinning) {
      setSettled(false)
      a.target = null
      a.spinStart = Date.now()
      if (!REDUCED && !a.raf) a.raf = requestAnimationFrame(frame)
      return
    }

    if (!a.spinStart) return                // arranque en frio: nada que asentar todavia

    // el giro debe durar lo suficiente para que se lea como busqueda
    const wait = Math.max(0, 750 - (Date.now() - a.spinStart))
    a.timer = setTimeout(() => settle(heading == null ? a.angle : heading), wait)
    return () => clearTimeout(a.timer)
  }, [spinning, heading])

  useEffect(() => () => {
    cancelAnimationFrame(anim.current.raf)
    clearTimeout(anim.current.timer)
  }, [])

  return (
    <svg
      className={'compass' + (settled ? ' is-settled' : '')}
      viewBox="0 0 200 200" aria-hidden="true" focusable="false"
    >
      <circle className="ring" cx="100" cy="100" r="92" />
      <circle className="ring-inner" cx="100" cy="100" r="76" />
      <circle className="glow" cx="100" cy="100" r="97" />
      <g>
        {TICKS.map((t, i) => (
          <line key={i} className={'tick' + (t.major ? ' major' : '')} x1={t.x1} y1={t.y1} x2={t.x2} y2={t.y2} />
        ))}
      </g>
      <text className="card-letter n" x="100" y="38">N</text>
      <text className="card-letter" x="162" y="100">E</text>
      <text className="card-letter" x="100" y="162">S</text>
      <text className="card-letter" x="38" y="100">O</text>
      <g ref={needle}>
        <polygon className="needle-n" points="100,50 109,104 100,96 91,104" />
        <polygon className="needle-s" points="100,150 91,96 100,104 109,96" />
      </g>
      <circle className="hub" cx="100" cy="100" r="9" />
    </svg>
  )
}
