export function soles(p) {
  const n = Number(p)
  return Number.isFinite(n) && p != null && p !== '' ? 'S/ ' + (n % 1 ? n.toFixed(2) : n) : 'S/ —'
}

const conCoordenadas = (d) => typeof d.lat === 'number' && typeof d.lng === 'number'

export default function DishCard({ dish, rank }) {
  const donde = [dish.lugar, dish.distrito].filter(Boolean)
  const tags = Array.isArray(dish.tags) ? dish.tags.slice(0, 6) : []

  return (
    <li className="dish">
      <span className="rank" aria-hidden="true">{rank}</span>
      <h3>{dish.nombre || 'Plato sin nombre'}</h3>

      <div className="meta">
        <span className="price">{soles(dish.precio)}</span>
        {donde.length > 0 && (
          <span className="place">
            <b>{donde[0]}</b>{donde[1] ? ' · ' + donde[1] : ''}
          </span>
        )}
      </div>

      {tags.length > 0 && (
        <ul className="tags">{tags.map((t, i) => <li key={i}>{t}</li>)}</ul>
      )}

      {conCoordenadas(dish) && (
        <a
          className="map" target="_blank" rel="noopener noreferrer"
          href={`https://www.google.com/maps/search/?api=1&query=${dish.lat},${dish.lng}`}
        >
          Ver en el mapa<span aria-hidden="true"> ↗</span>
        </a>
      )}
    </li>
  )
}
