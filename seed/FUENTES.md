# Fuentes de seed/dishes.json

Todo el catalogo lo genera `python3 seed/build_dishes.py` (solo stdlib). Nada esta
escrito a mano: si una fuente se cae, el script para y no rellena con datos inventados.

## Que aporta cada fuente

| Campo | Fuente |
|---|---|
| `nombre`, `tags` | Wikipedia ES, [Anexo:Platos tipicos del Peru](https://es.wikipedia.org/wiki/Anexo:Platos_t%C3%ADpicos_del_Per%C3%BA) via `action=parse&prop=wikitext`. Los tags salen de las columnas *Tipo* e *Ingredientes*. |
| `lugar`, `lat`, `lng`, `osm_id` | OpenStreetMap, una sola query a Overpass: `amenity=restaurant\|fast_food\|cafe` con `name` dentro de la provincia de Lima (`admin_level=6`, `pe:ubigeo=1501`). |
| `distrito` | OpenStreetMap: los 43 poligonos `admin_level=8` de la misma query, con join espacial punto-en-poligono (ray casting, sin dependencias). Fallback a `addr:city`; si tampoco cae en un distrito conocido, el local se descarta. |
| `precio` | **Estimado.** Ver abajo. |

Emparejamiento plato-local: por el tag `cuisine` de OSM (`seafood`/`fish` -> marinos,
`chicken` -> pollo a la brasa y afines, `chifa`/`chinese` -> chaufa, `peruvian`/`regional`
-> criollos, cafes -> postres). Un local aporta 1-3 platos segun cuanta metadata tenga
(`website`, `phone`, `opening_hours`). El catalogo se corta en 180 items porque
`buscar_platos` mete una linea por plato en el prompt del LLM.

## El precio es una estimacion

No existe fuente publica de precio por plato en Lima: el IPC del INEI publica
variaciones porcentuales, no niveles. Por eso `precio` sale de una funcion
determinista `f(banda del plato, distrito)` documentada en `precio()` de
`seed/build_dishes.py`, y **todos los items llevan `precio_estimado: true`**.

- Banda base en soles, punto medio de rangos de carta observados en Lima:
  marino 34, criollo 24, pollo 22, chifa 20, postre 10.
- Multiplicador por distrito segun nivel socioeconomico y carta turistica:
  San Isidro 1.4, Miraflores 1.35, Barranco 1.25, Surco/La Molina 1.15 ... y a la
  baja SJL, Comas, VES, Carabayllo, Puente Piedra, El Agustino 0.75. Resto 1.0.

## Licencias

- OpenStreetMap: ODbL. Atribucion obligatoria: **(c) OpenStreetMap contributors**.
- Wikipedia: CC BY-SA 4.0.
