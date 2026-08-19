import { useEffect, useState } from 'react'
import Compass, { bearing } from './Compass.jsx'
import CravingForm from './CravingForm.jsx'
import DishCard, { soles } from './DishCard.jsx'
import { buscar, errorVacio, errorSinPlatos } from './api.js'

// el agente tarda varios segundos: mejor contar que esta pasando que fingir que es instantaneo
const ESPERA = [
  'Girando la brújula…',
  'Olfateando la ciudad: sabores, precios y distritos…',
  'El agente sigue trabajando, suele tomar unos segundos…',
  'Ya casi: quedándonos con los tres mejores…',
]

const resumen = (craving, platos) =>
  `${platos.length} platos para “${craving}”. El primero: ${platos[0].nombre}, ` +
  `${soles(platos[0].precio)}${platos[0].distrito ? ', en ' + platos[0].distrito : ''}.`

export default function App() {
  const [busy, setBusy] = useState(false)
  const [estado, setEstado] = useState('')   // string = informativo, objeto {title,detail} = error
  const [platos, setPlatos] = useState([])
  const [heading, setHeading] = useState(null)

  // mensajes de espera rotativos mientras dura la consulta
  useEffect(() => {
    if (!busy) return
    let i = 0
    setEstado(ESPERA[0])
    const id = setInterval(() => {
      i = Math.min(i + 1, ESPERA.length - 1)
      setEstado(ESPERA[i])
    }, 3500)
    return () => clearInterval(id)
  }, [busy])

  const onSearch = async (craving) => {
    if (busy) return
    setPlatos([])
    setHeading(null)
    if (!craving) { setEstado(errorVacio()); return }

    setBusy(true)
    try {
      const data = await buscar(craving)
      const encontrados = Array.isArray(data && data.dishes) ? data.dishes.filter(Boolean).slice(0, 3) : []
      if (!encontrados.length) throw errorSinPlatos()
      setPlatos(encontrados)
      setHeading(bearing(encontrados[0]))
      setEstado(resumen((data && data.craving) || craving, encontrados))
    } catch (e) {
      setEstado(e && e.title
        ? e
        : { title: 'La brújula perdió el norte', detail: 'La respuesta del servicio vino rota. Vuelve a intentar.' })
    } finally {
      setBusy(false)
    }
  }

  const esError = estado && typeof estado === 'object'

  return (
    <div className="wrap">
      <header>
        <span className="badge">Lima · Perú</span>
        <h1>Crave<em>Map</em></h1>
        <p className="tagline">
          Dinos qué se te antoja. La brújula apunta a <strong>3 platos</strong>, no a 3 restaurantes.
        </p>
      </header>

      {/* decorativa: el estado real se anuncia por la region aria-live de abajo */}
      <Compass spinning={busy} heading={heading} />

      <CravingForm busy={busy} onSearch={onSearch} />

      <p className={'status' + (esError ? ' error' : '')} role="status" aria-live="polite">
        {esError ? <><strong>{estado.title}</strong>{estado.detail}</> : estado}
      </p>

      {platos.length > 0 && (
        <ul className="results">
          {platos.map((d, i) => <DishCard key={d.id || i} dish={d} rank={i + 1} />)}
        </ul>
      )}

      <footer>
        <p>Los locales son ilustrativos; los platos y precios son referenciales.</p>
        <p>La brújula apunta al rumbo real del primer plato desde el centro de Lima.</p>
      </footer>
    </div>
  )
}
