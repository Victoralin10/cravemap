const API = window.CRAVEMAP_API || '/api/craving'
const API_FEEDBACK = window.CRAVEMAP_API_FEEDBACK || '/api/feedback'

const QS = new URLSearchParams(location.search)

// modo demo: bandera global o ?demo=1 en la url, para probar sin backend
export const DEMO = !!window.CRAVEMAP_DEMO || QS.has('demo')
// ?fail=1 dentro del demo: fuerza el camino de error del feedback para poder probarlo
const DEMO_FALLA = QS.has('fail')

const PLATOS_DEMO = [
  { id: 'parihuela#Callao#node/123', plato: 'parihuela', local: 'Callao#node/123',
    nombre: 'Parihuela', precio: 35, distrito: 'Callao', lugar: 'Chalaquita',
    lat: -12.0566, lng: -77.1181, tags: ['caldoso', 'picante', 'reconfortante', 'marino', 'resaca'] },
  { id: 'aji-gallina#Jesús María#node/456', plato: 'aji-gallina', local: 'Jesús María#node/456',
    nombre: 'Ají de gallina', precio: 20, distrito: 'Jesús María', lugar: 'Menú de barrio',
    lat: -12.0748, lng: -77.0489, tags: ['cremoso', 'suave', 'reconfortante', 'clásico', 'económico'] },
  { id: 'anticucho#Barranco#node/789', plato: 'anticucho', local: 'Barranco#node/789',
    nombre: 'Anticuchos de corazón', precio: 18, distrito: 'Barranco', lugar: 'Carretilla de Grau',
    lat: -12.1464, lng: -77.0206, tags: ['parrilla', 'picante', 'callejero', 'noche'] },
]

// error con titulo y detalle listos para pintar, sin perder el mensaje del backend
const falla = (title, detail) => Object.assign(new Error(title), { title, detail })

export const errorVacio = () => falla(
  'Nos falta el antojo',
  'Escribe qué se te antoja, aunque sea vago: “algo caliente”, “tengo resaca”.'
)

export const errorSinPlatos = () => falla(
  'La brújula giró en vano',
  'No encontramos platos para ese antojo. Prueba con algo más simple: un sabor, un precio, un momento del día.'
)

export async function buscar(craving) {
  if (DEMO) {
    await new Promise((ok) => setTimeout(ok, 1400))
    return { craving, dishes: PLATOS_DEMO }
  }

  let r
  try {
    r = await fetch(API, {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify({ craving }),
    })
  } catch {
    throw falla(
      'La brújula perdió el norte',
      'No pudimos llegar al servicio. Revisa tu conexión y vuelve a intentar.'
    )
  }

  if (!r.ok) {
    const body = await r.json().catch(() => null)   // 4xx trae {error}; 5xx a veces no trae nada
    const msg = body && typeof body.error === 'string' ? body.error : null
    if (r.status === 400) {
      throw falla('Ese antojo no pasó el filtro', msg || 'Hace falta un antojo y no puede pasar de 300 caracteres.')
    }
    throw falla(
      'La brújula perdió el norte',
      (msg || `El servicio respondió ${r.status}.`) + ' Vuelve a intentar en un momento.'
    )
  }

  return r.json()
}

// el catalogo es parcialmente inferido: esto es lo que lo corrige. 202 y nada mas que leer.
export async function enviarFeedback(cuerpo) {
  if (DEMO) {
    await new Promise((ok) => setTimeout(ok, 900))
    if (DEMO_FALLA) throw falla('No pudimos enviar tu reporte', 'El servicio no respondió. Vuelve a intentar.')
    return
  }

  let r
  try {
    r = await fetch(API_FEEDBACK, {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify(cuerpo),
    })
  } catch {
    throw falla('No pudimos enviar tu reporte', 'Revisa tu conexión y vuelve a intentar.')
  }

  if (!r.ok) {
    const body = await r.json().catch(() => null)
    const msg = body && typeof body.error === 'string' ? body.error : null
    throw falla('No pudimos enviar tu reporte', msg || `El servicio respondió ${r.status}. Vuelve a intentar.`)
  }
}
