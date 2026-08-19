const API = window.CRAVEMAP_API || '/api/craving'

// modo demo: bandera global o ?demo=1 en la url, para probar sin backend
export const DEMO = !!window.CRAVEMAP_DEMO || new URLSearchParams(location.search).has('demo')

const PLATOS_DEMO = [
  { id: 'parihuela-04', nombre: 'Parihuela', precio: 35, distrito: 'Callao', lugar: 'Chalaquita',
    lat: -12.0566, lng: -77.1181, tags: ['caldoso', 'picante', 'reconfortante', 'marino', 'resaca'] },
  { id: 'aji-gallina-07', nombre: 'Ají de gallina', precio: 20, distrito: 'Jesús María', lugar: 'Menú de barrio',
    lat: -12.0748, lng: -77.0489, tags: ['cremoso', 'suave', 'reconfortante', 'clásico', 'económico'] },
  { id: 'anticucho-08', nombre: 'Anticuchos de corazón', precio: 18, distrito: 'Barranco', lugar: 'Carretilla de Grau',
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
