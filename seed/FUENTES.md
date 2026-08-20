# Fuentes de seed/platos.json y seed/locales.json

Todo lo genera `python3 seed/build_dishes.py` (solo stdlib, una sola query a
Overpass). Nada esta escrito a mano: si una fuente se cae, el script para tras 2
intentos y no rellena con datos inventados.

## Modelo de dos niveles

| Archivo | Que es | Donde vive | Tamano |
|---|---|---|---|
| `platos.json` | Catalogo: 32 platos con `id`, `nombre`, `tipo`, `tags`. Solo platos que tienen al menos un local. | Empaquetado en la imagen del Lambda, **no** va a DynamoDB. | 3.9 KB |
| `locales.json` | Los 35.259 pares plato-local, sin tope. | DynamoDB, via `python3 seed/seed.py <NombreTabla>`. | 11.4 MB |

Claves de DynamoDB: partition key `plato` (= el `id` del catalogo), sort key
`local` con el formato exacto `"{distrito}#{osm_id}"`. Los `tags` de cada par son
los del plato, duplicados ahi para que la UI no tenga que hacer un join.

El tope de 180 items que habia antes existia porque la tool del agente hacia scan
completo y metia una linea por plato en el prompt del LLM. Con el catalogo aparte,
la tool ya no necesita volcar la tabla al prompt y el tope desaparece.

## Que aporta cada fuente

| Campo | Fuente |
|---|---|
| `nombre`, `tipo`, `tags` | Wikipedia ES, [Anexo:Platos tipicos del Peru](https://es.wikipedia.org/wiki/Anexo:Platos_t%C3%ADpicos_del_Per%C3%BA) via `action=parse&prop=wikitext`. `tipo` es la columna *Tipo*; los `tags` son la banda del plato mas el sustantivo cabeza de cada ingrediente corto de la columna *Ingredientes* (maximo 5, los que sirven para matchear un antojo). |
| `lugar`, `lat`, `lng`, `osm_id` | OpenStreetMap, una sola query a Overpass: `amenity=restaurant\|fast_food\|cafe` con `name` dentro de la provincia de Lima (`admin_level=6`, `pe:ubigeo=1501`). |
| `distrito` | OpenStreetMap: los 43 poligonos `admin_level=8` de la misma query, con join espacial punto-en-poligono (ray casting, sin dependencias). Fallback a `addr:city`; si tampoco cae en un distrito conocido, el local se descarta. |
| `precio` | **Estimado.** Ver abajo. |
| `cuisine_fuente` | `"osm"` o `"inferido"`. Ver abajo. |

## El emparejamiento plato-local, y donde deja de ser un dato

**`cuisine_fuente: "osm"`** (8.563 pares). El tag `cuisine` de OSM dice que cocina
es: `seafood`/`fish` -> marinos, `chicken` -> pollo a la brasa y afines,
`chifa`/`chinese` -> chaufa, `peruvian`/`regional`/`criollo` -> criollos,
`coffee_shop`/`cafe`/`dessert`/`ice_cream` -> postres. El local se empareja con
todos los platos de esa banda.

**`cuisine_fuente: "inferido"`** (26.696 pares). **Esto es una inferencia nuestra,
no un dato de OpenStreetMap.** Mas de la mitad de los locales de Lima no tienen el
tag `cuisine`. A los que son `amenity=restaurant` les colgamos una carta generica
de criollos comunes (lomo saltado, aji de gallina, arroz chaufa, pollo a la brasa,
causa a la limena, papa a la huancaina, arroz con pollo, tacutacu), porque en Lima
el restaurante sin etiquetar es casi siempre un menu criollo. Puede fallar en
casos concretos: un local marcado asi puede no servir ese plato. Los `cafe` y
`fast_food` sin `cuisine` **si** se descartan: no hay base para adivinar que sirven.

Resultado: 4.705 locales unicos en los 43 distritos de la provincia de Lima.

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
