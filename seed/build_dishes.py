"""Genera seed/platos.json y seed/locales.json desde fuentes publicas.
Uso: python3 seed/build_dishes.py

Platos  -> Wikipedia ES "Anexo:Platos tipicos del Peru" (CC BY-SA 4.0).
Locales -> OpenStreetMap via Overpass, provincia de Lima (ODbL).
Precio  -> estimado con la heuristica de precio() (no hay fuente publica).

Dos niveles: platos.json es el catalogo (pequeno, va empaquetado en la imagen del
Lambda) y locales.json son todos los pares plato-local (van a DynamoDB).
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
BANDA = {p: b for b, (_, ps) in BUCKETS.items() for p in ps}

# INFERENCIA, no dato de OSM: un amenity=restaurant sin tag cuisine en Lima
# casi siempre es un menu criollo. A esos les colgamos esta carta comun y los
# marcamos cuisine_fuente="inferido". Los cafe y fast_food sin cuisine se
# descartan: no hay base para adivinar que sirven.
GENERICOS = ["lomo saltado", "aji de gallina", "arroz chaufa", "pollo a la brasa",
             "causa a la limena", "papa a la huancaina", "arroz con pollo", "tacutacu"]

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

# Palabras que encabezan un ingrediente sin decir nada ("trozos de res"): con
# estas el tag discriminante es la ultima palabra, no la primera.
RELLENO = {"trozos", "abundante", "salsa", "bistec", "carne", "harina", "miel"}


def precio(banda, distrito):
    """Estimacion determinista en soles. Ver BASE y MULT para el origen de cada numero."""
    return round(BASE[banda] * MULT.get(distrito, 1.0))


def limpio(s):
    """Sin tildes ni enie: el repo entero es asi."""
    return "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn")


def clave(s):
    """kebab-case sin tildes: 'Aji de gallina' -> 'aji-de-gallina'."""
    return re.sub(r"[^a-z0-9]+", "-", limpio(s).lower()).strip("-")


def en_poligono(lng, lat, segs):
    """Ray casting. segs es una sopa de aristas (x1,y1,x2,y2) que cierran anillos;
    no hace falta ordenarlas, la paridad de cruces es la misma."""
    dentro = False
    for x1, y1, x2, y2 in segs:
        if (y1 > lat) != (y2 > lat) and lng < x1 + (lat - y1) * (x2 - x1) / (y2 - y1):
            dentro = not dentro
    return dentro


def platos(wikitext):
    """{clave sin tildes: (nombre, tipo, [tags])} de las tablas Nombre|Tipo|Ingredientes|Imagen."""
    out = {}
    for bloque in wikitext.split("|-"):
        celdas = [l[1:].strip() for l in bloque.splitlines()
                  if l.startswith("|") and not l.startswith("|}")]
        if len(celdas) < 3:
            continue
        nombre = re.sub(r"\[\[([^\]|]*\|)?([^\]]*)\]\]", r"\2", celdas[0]).replace("'''", "").strip()
        tipo = limpio(re.sub(r"\(.*?\)", "", celdas[1]).split("/")[0]).strip().capitalize()
        # tags = el sustantivo cabeza de cada ingrediente ("pescado fresco crudo" ->
        # "pescado"). Pocos y discriminantes: los que sirven para matchear un antojo.
        tags = ["caldoso"] if tipo.lower().startswith(("sopa", "caldo")) else []
        for ing in re.sub(r"\(.*?\)|\[|\]", "", celdas[2]).split(",")[:6]:
            palabras = limpio(ing).strip(" .").lower().split()
            if not palabras or len(palabras) > 3:
                continue  # los trozos largos son prosa, no ingredientes
            t = palabras[-1] if palabras[0] in RELLENO else palabras[0]
            if len(t) > 2 and t not in tags:
                tags.append(t)
        out.setdefault(limpio(nombre).lower(), (limpio(nombre), tipo, tags[:4]))
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


def escribe(nombre, items):
    p = pathlib.Path(__file__).with_name(nombre)
    # un objeto por linea: seed.py lo carga en streaming, sin meterlo todo en memoria
    p.write_text("[\n" + ",\n".join(json.dumps(d, ensure_ascii=False) for d in items) + "\n]\n")
    return p


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

    pares, usados = [], {}
    for e in sorted(elems, key=lambda e: (e.get("type", ""), e.get("id", 0))):
        t = e.get("tags", {})
        if t.get("amenity") not in ("restaurant", "fast_food", "cafe"):
            continue
        cocinas = set(t.get("cuisine", "").lower().split(";"))
        banda = next((b for b, (cs, _) in BUCKETS.items() if cocinas & set(cs)), None)
        if banda:
            menu, fuente = BUCKETS[banda][1], "osm"
        elif t["amenity"] == "restaurant":
            menu, fuente = GENERICOS, "inferido"
        else:
            continue
        c = e.get("center", e)
        lat, lng = c["lat"], c["lon"]
        distrito = distrito_de(lng, lat, t)
        if not distrito:
            continue
        osm_id = f"{e['type']}/{e['id']}"
        for p in menu:
            if p not in catalogo:
                continue
            nombre, tipo, tags = catalogo[p]
            tags = list(dict.fromkeys([BANDA[p]] + tags))  # la banda primero, sin repetir
            usados[clave(p)] = {"id": clave(p), "nombre": nombre, "tipo": tipo, "tags": tags}
            pares.append({
                "plato": clave(p),
                "local": f"{distrito}#{osm_id}",
                "nombre": nombre,
                "lugar": limpio(t["name"]),
                "distrito": distrito,
                "precio": float(precio(BANDA[p], distrito)),
                "lat": round(lat, 6),
                "lng": round(lng, 6),
                "tags": tags,
                "osm_id": osm_id,
                "precio_estimado": True,
                "cuisine_fuente": fuente,
            })

    a = escribe("platos.json", sorted(usados.values(), key=lambda d: d["id"]))
    b = escribe("locales.json", pares)
    inferidos = sum(1 for p in pares if p["cuisine_fuente"] == "inferido")
    print(f"{len(usados)} platos ({a.stat().st_size // 1024} KB) | {len(pares)} pares "
          f"({b.stat().st_size // 1024} KB) | {len({p['osm_id'] for p in pares})} locales | "
          f"{len({p['distrito'] for p in pares})} distritos | "
          f"osm {len(pares) - inferidos} / inferido {inferidos}")


if __name__ == "__main__":
    main()
