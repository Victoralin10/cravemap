"""Genera seed/dishes.json desde fuentes publicas. Uso: python3 seed/build_dishes.py

Platos  -> Wikipedia ES "Anexo:Platos tipicos del Peru" (CC BY-SA 4.0).
Locales -> OpenStreetMap via Overpass, provincia de Lima (ODbL).
Precio  -> estimado con la heuristica de precio() (no hay fuente publica).
Detalle en seed/FUENTES.md. Solo stdlib.
"""
import json, pathlib, re, unicodedata, urllib.request

WIKI = ("https://es.wikipedia.org/w/api.php?action=parse&format=json&prop=wikitext"
        "&page=Anexo:Platos_t%C3%ADpicos_del_Per%C3%BA")
OVERPASS = "https://overpass-api.de/api/interpreter"

# Una sola query (fair-use de Overpass): locales con nombre + los 43 distritos
# de la provincia de Lima (pe:ubigeo 1501) para el join espacial.
QUERY = """
[out:json][timeout:900];
area["boundary"="administrative"]["admin_level"="6"]["pe:ubigeo"="1501"]->.lima;
nwr["amenity"~"^(restaurant|fast_food|cafe)$"]["name"](area.lima);
out center tags;
rel["boundary"="administrative"]["admin_level"="8"](area.lima);
out geom;
"""

# ponytail: el techo de 180 es el tamano del prompt, no la base de datos.
# buscar_platos() en agent/agent.py hace scan completo y mete UNA LINEA POR PLATO
# en el prompt del LLM: con miles de items el prompt explota en costo y latencia.
# Para pasar de aqui hay que filtrar en DynamoDB (GSI por distrito / por banda de
# precio) y que la tool consulte, en vez de volcar el catalogo entero al prompt.
MAX_ITEMS = 180
CUPO_DISTRITO = 14  # variedad: ningun distrito acapara el catalogo
CUPO_PLATO = 14     # variedad: ni un plato tampoco

# cuisine de OSM -> banda de precio + platos que ese local puede ofrecer.
# "chinese" entra en chifa: en Lima el chifa se etiqueta de las dos formas.
BUCKETS = {
    "marino": (["seafood", "fish"],
               ["ceviche", "leche de tigre", "parihuela", "jalea", "tiradito",
                "choritos a la chalaca"]),
    "pollo": (["chicken"],
              ["pollo a la brasa", "arroz con pollo", "caldo de gallina",
               "escabeche de pollo", "aguadito de pollo"]),
    "chifa": (["chifa", "chinese"], ["arroz chaufa"]),
    "criollo": (["peruvian", "regional", "criollo"],
                ["lomo saltado", "aji de gallina", "causa a la limena", "anticuchos",
                 "tacutacu", "cau cau", "carapulcra", "seco de cabrito",
                 "papa a la huancaina", "rocoto relleno", "sancochado",
                 "chanfainita", "lomo a la chorrillana"]),
    "postre": (["coffee_shop", "cafe", "dessert", "ice_cream"],
               ["suspiro de limena", "picarones", "mazamorra morada", "arroz zambito",
                "turron de dona pepa", "ranfanote", "champus"]),
}

# Banda base en soles por tipo de plato: punto medio de los rangos de carta que se
# ven en Lima (cevicheria 30-45, menu criollo 18-30, 1/4 de pollo 18-26, plato
# personal de chifa 16-24, postre 8-12). NO hay fuente publica de precio por plato:
# el IPC del INEI solo publica variaciones porcentuales, no niveles. Por eso cada
# item sale marcado con precio_estimado: true.
BASE = {"marino": 34, "criollo": 24, "pollo": 22, "chifa": 20, "postre": 10}

# Multiplicador por distrito: zonas caras/turisticas arriba, conos y periferia abajo.
# Criterio: nivel socioeconomico predominante (APEIM) y concentracion de carta turistica.
MULT = {
    "San Isidro": 1.4, "Miraflores": 1.35, "Barranco": 1.25, "Santiago de Surco": 1.15,
    "La Molina": 1.15, "San Borja": 1.1, "Magdalena del Mar": 1.05,
    "Los Olivos": 0.9, "San Martin de Porres": 0.85, "Santa Anita": 0.8, "Ate": 0.8,
    "Rimac": 0.8, "Independencia": 0.8, "San Juan de Miraflores": 0.8, "Lurigancho": 0.8,
    "San Juan de Lurigancho": 0.75, "Comas": 0.75, "Villa El Salvador": 0.75,
    "Villa Maria del Triunfo": 0.75, "Carabayllo": 0.75, "Puente Piedra": 0.75,
    "El Agustino": 0.75,
}


def precio(banda, distrito):
    """Estimacion determinista en soles. Ver BASE y MULT para el origen de cada numero."""
    return round(BASE[banda] * MULT.get(distrito, 1.0))


def limpio(s):
    """Sin tildes ni enie: el repo entero es asi."""
    return "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn")


def en_poligono(lng, lat, segs):
    """Ray casting. segs es una sopa de aristas (x1,y1,x2,y2) que cierran anillos;
    no hace falta ordenarlas, la paridad de cruces es la misma."""
    dentro = False
    for x1, y1, x2, y2 in segs:
        if (y1 > lat) != (y2 > lat) and lng < x1 + (lat - y1) * (x2 - x1) / (y2 - y1):
            dentro = not dentro
    return dentro


def platos(wikitext):
    """{clave sin tildes: (nombre, [tags])} de las tablas Nombre|Tipo|Ingredientes|Imagen."""
    out = {}
    for bloque in wikitext.split("|-"):
        celdas = [l[1:].strip() for l in bloque.splitlines()
                  if l.startswith("|") and not l.startswith("|}")]
        if len(celdas) < 3:
            continue
        nombre = re.sub(r"\[\[([^\]|]*\|)?([^\]]*)\]\]", r"\2", celdas[0]).replace("'''", "").strip()
        tipo = re.sub(r"\(.*?\)", "", celdas[1])
        tags = [limpio(t.strip().lower()) for t in tipo.split("/") if t.strip()]
        # de los ingredientes solo los trozos cortos: los largos son prosa, no ingredientes
        for ing in celdas[2].split(",")[:6]:
            ing = limpio(re.sub(r"\(.*?\)|\[|\]", "", ing).strip(" .").lower())
            if ing and len(ing.split()) <= 3 and len(tags) < 6:
                tags.append(ing)
        out.setdefault(limpio(nombre).lower(), (limpio(nombre), tags))
    return out


def get(url, data=None):
    for intento in (1, 2):
        try:
            # Wikipedia responde 403 sin User-Agent propio (su politica de UA).
            req = urllib.request.Request(url, data=data.encode() if data else None,
                                         headers={"User-Agent": "CraveMap/1.0 (seed script)"})
            return json.loads(urllib.request.urlopen(req, timeout=900).read())
        except Exception as e:
            err = e
    raise SystemExit(f"fuente caida tras 2 intentos: {url}: {err}")


def main():
    catalogo = platos(get(WIKI)["parse"]["wikitext"]["*"])
    elems = get(OVERPASS, QUERY)["elements"]

    # distritos: aristas + bbox para descartar rapido
    distritos = []
    for r in elems:
        if r.get("tags", {}).get("admin_level") == "8":
            segs = [(g1["lon"], g1["lat"], g2["lon"], g2["lat"])
                    for m in r["members"] if m.get("role") in ("outer", "") and "geometry" in m
                    for g1, g2 in zip(m["geometry"], m["geometry"][1:])]
            xs, ys = [s[0] for s in segs], [s[1] for s in segs]
            distritos.append((limpio(r["tags"]["name"]), segs,
                              (min(xs), min(ys), max(xs), max(ys))))
    nombres = {d[0] for d in distritos}

    def distrito_de(lng, lat, tags):
        for n, segs, (x0, y0, x1, y1) in distritos:
            if x0 <= lng <= x1 and y0 <= lat <= y1 and en_poligono(lng, lat, segs):
                return n
        ciudad = limpio(tags.get("addr:city", "")).lower()
        return next((n for n in nombres if n.lower() == ciudad), None)

    # locales candidatos: los que tienen una cuisine que sabemos mapear
    cands = []
    for e in elems:
        t = e.get("tags", {})
        if t.get("amenity") not in ("restaurant", "fast_food", "cafe"):
            continue
        cocinas = t.get("cuisine", "").lower().split(";")
        banda = next((b for b, (cs, _) in BUCKETS.items() if set(cs) & set(cocinas)), None)
        if not banda and t["amenity"] == "cafe":
            banda = "postre"
        if not banda:
            continue
        c = e.get("center", e)
        meta = sum(k in t for k in ("website", "phone", "opening_hours"))
        cands.append((-meta, e["type"], e["id"], banda, t, c["lat"], c["lon"]))

    # mas metadata primero (id como desempate para que la salida sea reproducible)
    cands.sort()
    items, por_distrito, por_plato, i = [], {}, {}, 0
    for meta, tipo, oid, banda, t, lat, lng in cands:
        if len(items) >= MAX_ITEMS:
            break
        distrito = distrito_de(lng, lat, t)
        if not distrito or por_distrito.get(distrito, 0) >= CUPO_DISTRITO:
            continue
        menu = BUCKETS[banda][1]
        cuantos = min(3, 1 - meta)  # meta viene negado del sort: mas metadata, mas platos (1-3)
        elegidos = [p for p in menu[i % len(menu):] + menu[:i % len(menu)]
                    if p in catalogo and por_plato.get(p, 0) < CUPO_PLATO][:min(cuantos, MAX_ITEMS - len(items))]
        for p in elegidos:
            nombre, tags = catalogo[p]
            i += 1
            items.append({
                "id": f"{re.sub(r'[^a-z0-9]+', '-', p)}-{i:03d}",
                "nombre": nombre,
                "precio": float(precio(banda, distrito)),
                "distrito": distrito,
                "lugar": limpio(t["name"]),
                "lat": round(lat, 6),
                "lng": round(lng, 6),
                "tags": tags + [banda],
                "precio_estimado": True,
                "osm_id": f"{tipo}/{oid}",
                "fuente": "OpenStreetMap (local) + Wikipedia (plato)",
            })
            por_distrito[distrito] = por_distrito.get(distrito, 0) + 1
            por_plato[p] = por_plato.get(p, 0) + 1

    salida = pathlib.Path(__file__).with_name("dishes.json")
    salida.write_text("[\n" + ",\n".join(json.dumps(d, ensure_ascii=False) for d in items) + "\n]\n")
    print(f"{len(items)} platos | {len(por_distrito)} distritos | {len(por_plato)} platos distintos")


if __name__ == "__main__":
    main()
