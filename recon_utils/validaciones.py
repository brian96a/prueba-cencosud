"""Las revisiones de cuadratura. Cada revisión devuelve un texto si hay problema, o None si está bien.

Hay tres grupos:
  1. Conteo entre capas  (validar_conteo)
  2. Calidad de los datos contra el esquema: llave primaria y nulos  (validar_calidad)
  3. Resultado del test de dbt  (registrar_tests_dbt)
"""
import json
from datetime import date, datetime

import pandas as pd

from recon_utils.traza import abrir_traza, registrar_conteo, promedio_historico, obtener_esquema
from recon_utils.alertas import enviar_alerta


class ValidacionFallida(Exception):
    """Se lanza cuando una capa no cuadra. Hace que el job termine en FAILED."""


# ---------- 1. Conteo entre capas ----------

def cargar_regla(tabla):
    """Las reglas de conteo viven en el esquema registrado de la tabla (en AWS: DynamoDB)."""
    return obtener_esquema(tabla)["reglas_conteo"]


def revisar_minimo(filas_salida, minimo_filas):
    if filas_salida == 0:
        return "cargó 0 filas"
    if filas_salida < minimo_filas:
        return f"cargó {filas_salida} filas y el mínimo es {minimo_filas}"


def revisar_igualdad(filas_salida, filas_esperadas, tolerancia_pct):
    if filas_esperadas is None:
        return "falta el dato de filas esperadas"
    diferencia = abs(filas_salida - filas_esperadas)
    permitido = filas_esperadas * tolerancia_pct / 100
    if diferencia > permitido:
        return f"salieron {filas_salida} filas y se esperaban {filas_esperadas}"


def revisar_filtro(filas_entrada, filas_salida, minimo_pct):
    if filas_salida > filas_entrada:
        return f"salieron más filas ({filas_salida}) que las que entraron ({filas_entrada})"
    if filas_entrada > 0:
        porcentaje = filas_salida * 100 / filas_entrada
        if porcentaje < minimo_pct:
            return f"sobrevivió solo el {porcentaje:.0f}% de las filas y el mínimo es {minimo_pct}%"


def revisar_historial(tabla, filas_salida, minimo_pct_historial):
    promedio = promedio_historico(tabla)
    if promedio is None or filas_salida == 0:  # el caso de 0 filas ya lo avisa revisar_minimo
        return None
    if filas_salida < promedio * minimo_pct_historial / 100:
        return f"cargó {filas_salida} filas y el promedio histórico es {promedio:.0f}"


def revisar_fecha(fecha_carga):
    if fecha_carga is None:
        return "no hay fecha de carga"
    if fecha_carga.date() != date.today():
        return f"la fecha de carga es {fecha_carga.date()} y hoy es {date.today()}"


def revisar_suma(suma_entrada, suma_salida):
    if suma_entrada is None or suma_salida is None:
        return "faltan las sumas para comparar"
    if abs(suma_entrada - suma_salida) > 0.01:
        return f"la suma de monto cambió: entró {suma_entrada} y salió {suma_salida}"


def validar_conteo(run_id, tabla, filas_entrada, filas_salida, fecha_carga=None,
                   filas_esperadas=None, suma_entrada=None, suma_salida=None):
    """Revisa una capa, guarda la traza y falla si algo no cuadra."""
    regla = cargar_regla(tabla)
    tipo = regla["tipo"]

    problemas = [revisar_minimo(filas_salida, regla.get("minimo_filas", 1))]

    if tipo == "uno_a_uno":
        problemas.append(revisar_igualdad(filas_salida, filas_entrada, regla["tolerancia_pct"]))
    elif tipo == "filtra":
        problemas.append(revisar_filtro(filas_entrada, filas_salida, regla["minimo_pct"]))
    elif tipo == "agrega":
        problemas.append(revisar_igualdad(filas_salida, filas_esperadas, regla["tolerancia_pct"]))

    if "minimo_pct_historial" in regla:
        problemas.append(revisar_historial(tabla, filas_salida, regla["minimo_pct_historial"]))
    if regla.get("revisar_fecha_carga"):
        problemas.append(revisar_fecha(fecha_carga))
    if regla.get("revisar_suma"):
        problemas.append(revisar_suma(suma_entrada, suma_salida))

    problemas = [p for p in problemas if p]
    estado = "FALLIDO" if problemas else "OK"
    motivo = "; ".join(problemas)

    registrar_conteo(run_id, tabla, filas_entrada, filas_salida, fecha_carga, estado, motivo)

    if problemas:
        mensaje = f"[{run_id}] {tabla}: {motivo}"
        enviar_alerta(mensaje, tabla, run_id)
        raise ValidacionFallida(mensaje)

    print(f"[{run_id}] {tabla}: OK ({filas_entrada} entraron, {filas_salida} salieron)")


# ---------- 2. Calidad contra el esquema ----------
# Regla del margen: cada revisión pasa si al menos `margen_minimo_pct` (ej. 90%) de las filas está bien.
# Una columna puede tener su propio límite con `nulos_max_pct`.

def convertir_tipos(datos, esquema):
    """Pasa cada columna al tipo del esquema. Lo que no se pueda convertir queda nulo."""
    datos = datos.copy()
    for nombre, columna in esquema["columnas"].items():
        if nombre not in datos.columns:
            continue
        if columna["tipo"] == "int":
            datos[nombre] = pd.to_numeric(datos[nombre], errors="coerce").astype("Int64")
        elif columna["tipo"] == "double":
            datos[nombre] = pd.to_numeric(datos[nombre], errors="coerce").astype("float64")
        elif columna["tipo"] == "string":
            datos[nombre] = datos[nombre].astype("string")
    return datos


def porcentaje_llave_ok(datos, llave):
    """% de filas con llave completa y no repetida."""
    mala = datos[llave].isnull().any(axis=1) | datos.duplicated(subset=llave, keep="first")
    return 100 * (1 - mala.mean())


def porcentaje_sin_nulos(datos, columna):
    return 100 * datos[columna].notnull().mean()


def validar_calidad(run_id, tabla, datos):
    """Revisa los datos contra el esquema de la tabla, guarda la traza y falla si no se cumple el margen."""
    esquema = obtener_esquema(tabla)
    margen = esquema["margen_minimo_pct"]

    faltan = [c for c in esquema["columnas"] if c not in datos.columns]
    if faltan:
        return terminar_calidad(run_id, tabla, [("columnas", "-", 0, 100)], [f"faltan columnas: {faltan}"])
    if len(datos) == 0:
        return  # con 0 filas no hay porcentajes que calcular; lo avisa validar_conteo

    revisiones = []  # (revision, columna, porcentaje_ok, minimo_pct)
    revisiones.append(("llave_primaria", ",".join(esquema["llave_primaria"]),
                       porcentaje_llave_ok(datos, esquema["llave_primaria"]), margen))
    for nombre, columna in esquema["columnas"].items():
        minimo = 100 - columna["nulos_max_pct"] if "nulos_max_pct" in columna else margen
        revisiones.append(("nulos", nombre, porcentaje_sin_nulos(datos, nombre), minimo))

    problemas = [f"{rev} {col}: {pct:.0f}% ok y el mínimo es {minimo:.0f}%"
                 for rev, col, pct, minimo in revisiones if pct < minimo]
    terminar_calidad(run_id, tabla, revisiones, problemas)


def terminar_calidad(run_id, tabla, revisiones, problemas):
    conexion = abrir_traza()
    for revision, columna, pct, minimo in revisiones:
        estado = "FALLIDO" if pct < minimo else "OK"
        conexion.execute("insert into audit.calidad_por_columna values (?, ?, ?, ?, ?, ?, ?, ?)",
                         [run_id, tabla, revision, columna, float(pct), float(minimo), estado, datetime.now()])
    conexion.close()

    if problemas:
        mensaje = f"[{run_id}] {tabla} calidad: " + "; ".join(problemas)
        enviar_alerta(mensaje, tabla, run_id)
        raise ValidacionFallida(mensaje)
    print(f"[{run_id}] {tabla}: calidad OK")


# ---------- 3. Resultado del test de dbt ----------

def registrar_tests_dbt(run_id, ruta_run_results):
    """Lee el resultado de dbt test, lo guarda en la traza y alerta si algo falló."""
    with open(ruta_run_results) as archivo:
        resultados = json.load(archivo)["results"]

    conexion = abrir_traza()
    fallidos = []
    for resultado in resultados:
        nombre = resultado["unique_id"].split(".")[2]  # test.cuadratura.<nombre>.<hash>
        estado = "OK" if resultado["status"] == "pass" else "FALLIDO"
        filas_fallidas = resultado.get("failures") or 0
        conexion.execute("insert into audit.resultados_tests_dbt values (?, ?, ?, ?, ?)",
                         [run_id, nombre, estado, filas_fallidas, datetime.now()])
        if estado == "FALLIDO":
            fallidos.append(f"{nombre} ({filas_fallidas} filas)")
    conexion.close()

    if fallidos:
        mensaje = f"[{run_id}] dbt test falló: " + ", ".join(fallidos)
        enviar_alerta(mensaje, run_id=run_id)
        raise ValidacionFallida(mensaje)
    print(f"[{run_id}] dbt test: {len(resultados)} tests OK")
