"""Job de bronze (simula un Glue Job con PySpark).

Lee un CSV, lo revisa contra el esquema registrado, lo carga en la tabla Iceberg bronze.ventas
y al final cuadra los conteos.
En AWS: pandas sería spark.read.csv(...) y PyIceberg sería df.writeTo("bronze.ventas").
"""
import argparse
import os
import sys
from datetime import datetime

import pandas as pd
import pyarrow as pa
from pyiceberg.catalog.sql import SqlCatalog

from recon_utils.config import CARPETA_WAREHOUSE
from recon_utils import (validar_conteo, validar_calidad, convertir_tipos, obtener_esquema,
                         registrar_archivo, marcar_archivo, ValidacionFallida)

TABLA = "bronze.ventas"
TIPOS_ARROW = {"int": pa.int64(), "double": pa.float64(), "string": pa.string(), "timestamp": pa.timestamp("us")}


def abrir_catalogo():
    """Abre el catálogo Iceberg local. En AWS sería el Glue Data Catalog."""
    CARPETA_WAREHOUSE.mkdir(exist_ok=True)
    catalogo = SqlCatalog("local", uri=f"sqlite:///{CARPETA_WAREHOUSE}/catalogo.db",
                          warehouse=f"file://{CARPETA_WAREHOUSE}")
    catalogo.create_namespace_if_not_exists("bronze")
    return catalogo


def esquema_arrow(esquema):
    """Arma el esquema de la tabla Iceberg a partir del esquema registrado."""
    return pa.schema([(nombre, TIPOS_ARROW[columna["tipo"]]) for nombre, columna in esquema["columnas"].items()])


def leer_origen(archivo_csv):
    datos = pd.read_csv(archivo_csv, dtype=str)  # todo como texto, los tipos los pone el esquema
    datos["fecha_carga"] = datetime.now()
    return datos


def cargar_en_iceberg(datos, esquema):
    catalogo = abrir_catalogo()
    tabla = catalogo.create_table_if_not_exists(TABLA, schema=esquema_arrow(esquema))
    datos_arrow = pa.Table.from_pandas(datos, schema=esquema_arrow(esquema), preserve_index=False)
    tabla.overwrite(datos_arrow)  # reemplaza todo el contenido en cada corrida (carga completa)

    # --- Carga incremental (para producción) ---
    # Con append, cada corrida agrega filas sin borrar las anteriores:
    #     tabla.append(datos_arrow)
    # Con merge por llave primaria (en Spark o Athena):
    #     MERGE INTO bronze.ventas t USING nuevos s ON t.id_venta = s.id_venta
    #     WHEN MATCHED THEN UPDATE SET * WHEN NOT MATCHED THEN INSERT *
    # Ojo: en modo incremental la tabla ya no tiene solo las filas del archivo.
    # Para validar habría que contar las filas escritas en esta corrida, no las totales.
    # Iceberg las informa en el resumen del snapshot: tabla.current_snapshot().summary["added-records"]
    return catalogo.load_table(TABLA)


def main(archivo_csv, run_id):
    esquema = obtener_esquema(TABLA)

    datos = leer_origen(archivo_csv)
    filas_leidas = len(datos)
    print(f"Leí {filas_leidas} filas de {archivo_csv}")
    registrar_archivo(run_id, TABLA, archivo_csv, os.path.getsize(archivo_csv), filas_leidas,
                      [c for c in datos.columns if c != "fecha_carga"], esquema["version"])

    datos = convertir_tipos(datos, esquema)
    validar_calidad(run_id, TABLA, datos)  # llave primaria y nulos contra el esquema

    tabla = cargar_en_iceberg(datos, esquema)
    datos_cargados = tabla.scan().to_arrow().to_pandas()
    filas_cargadas = len(datos_cargados)
    print(f"Cargué {filas_cargadas} filas en {TABLA}")

    # Sin esta línea el job terminaría en verde aunque no haya cargado nada.
    fecha_carga = datos_cargados["fecha_carga"].max().to_pydatetime() if filas_cargadas else None
    validar_conteo(run_id, TABLA, filas_entrada=filas_leidas, filas_salida=filas_cargadas,
                   fecha_carga=fecha_carga)


if __name__ == "__main__":
    lector = argparse.ArgumentParser()
    lector.add_argument("--archivo", required=True)
    lector.add_argument("--run_id", required=True)
    argumentos = lector.parse_args()
    try:
        main(argumentos.archivo, argumentos.run_id)
        marcar_archivo(argumentos.run_id, TABLA, "OK")
    except ValidacionFallida:
        marcar_archivo(argumentos.run_id, TABLA, "FALLIDO")
        sys.exit(1)  # el job termina en FAILED
