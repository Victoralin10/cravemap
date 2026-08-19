"""Check minimo: python3 seed/test_build.py"""
from build_dishes import en_poligono, precio, platos, limpio

# --- ray casting punto-en-poligono ---
# cuadrado (0,0)-(10,10) con las aristas DESORDENADAS: el algoritmo no depende del orden
cuadrado = [(10, 0, 10, 10), (0, 0, 10, 0), (10, 10, 0, 10), (0, 10, 0, 0)]
assert en_poligono(5, 5, cuadrado) is True
assert en_poligono(15, 5, cuadrado) is False, "a la derecha, fuera"
assert en_poligono(-5, 5, cuadrado) is False, "a la izquierda, fuera"
assert en_poligono(5, 15, cuadrado) is False, "arriba, fuera"

# L concava: sin la mordida (6..10, 6..10) el punto (8,8) caeria dentro
ele = [(0, 0, 10, 0), (10, 0, 10, 6), (10, 6, 6, 6), (6, 6, 6, 10), (6, 10, 0, 10), (0, 10, 0, 0)]
assert en_poligono(3, 8, ele) is True, "brazo largo de la L"
assert en_poligono(8, 3, ele) is True, "brazo corto de la L"
assert en_poligono(8, 8, ele) is False, "la mordida concava queda fuera"

# dos anillos (multipoligono): la sopa de aristas los resuelve igual
lejos = cuadrado + [(20, 0, 30, 0), (30, 0, 30, 10), (30, 10, 20, 10), (20, 10, 20, 0)]
assert en_poligono(25, 5, lejos) is True and en_poligono(15, 5, lejos) is False

# --- heuristica de precio ---
assert precio("marino", "Miraflores") > precio("marino", "Lince") > precio("marino", "Comas"), \
    "caro en zona turistica, barato en cono"
assert precio("criollo", "Distrito Que No Existe") == 24, "sin multiplicador conocido, banda base"
assert precio("postre", "San Isidro") == 14 and precio("chifa", "San Isidro") == 28
assert precio("marino", "Lince") > precio("pollo", "Lince") > precio("postre", "Lince"), \
    "el marino es la banda cara, el postre la barata"

# --- parseo de la tabla de Wikipedia ---
tabla = """{| class="wikitable sortable"
!Nombre
!Tipo
!Ingredientes
!Imagen
|-
|[[Cebiche|Ceviche]]
|Entrada fría
|Pescado fresco crudo, limón, cebolla roja.

|[[Archivo:x.jpg|180x180px]]
|-
|[[Arroz chaufa]]
|Plato de fondo (Cocina Chifa)
|Arroz cocido salteado al wok a fuego alto con muchas palabras, sillao.
|[[Archivo:y.jpg|180x180px]]
|}"""
p = platos(tabla)
assert p["ceviche"][0] == "Ceviche", "resuelve [[destino|texto]] y quita tildes"
assert p["ceviche"][1] == ["entrada fria", "pescado fresco crudo", "limon", "cebolla roja"]
assert p["arroz chaufa"][1] == ["plato de fondo", "sillao"], "el tipo sin parentesis, la prosa larga fuera"
assert limpio("Breña Ñaña") == "Brena Nana"
print("ok")
