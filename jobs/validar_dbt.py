"""Pasos posteriores a dbt, con la misma librería que bronze.

  --capa silver | gold : cuadra los conteos y la calidad de esa capa
  --capa tests         : guarda el resultado de dbt test y alerta si algo falló
"""
import argparse
import sys

import duckdb

from recon_utils import validar_conteo, validar_calidad, registrar_tests_dbt, ValidacionFallida, filas_salida_de
from recon_utils.config import ARCHIVO_DUCKDB, CARPETA_PROYECTO


def validar_silver(run_id, conexion):
    filas_salida, fecha_carga, suma = conexion.execute(
        "select count(*), max(fecha_carga), sum(monto) from silver.ventas").fetchone()
    validar_calidad(run_id, "silver.ventas", conexion.execute("select * from silver.ventas").df())
    filas_entrada = filas_salida_de(run_id, "bronze.ventas")
    validar_conteo(run_id, "silver.ventas", filas_entrada, filas_salida, fecha_carga)


def validar_gold(run_id, conexion):
    filas_salida, fecha_carga, suma_gold = conexion.execute(
        "select count(*), max(fecha_carga), sum(monto_total) from gold.ventas_diarias").fetchone()
    validar_calidad(run_id, "gold.ventas_diarias", conexion.execute("select * from gold.ventas_diarias").df())
    filas_entrada, suma_silver, grupos = conexion.execute(
        "select count(*), sum(monto), count(distinct (id_tienda, fecha_venta)) from silver.ventas").fetchone()
    validar_conteo(run_id, "gold.ventas_diarias", filas_entrada, filas_salida, fecha_carga,
                   filas_esperadas=grupos, suma_entrada=suma_silver, suma_salida=suma_gold)


if __name__ == "__main__":
    lector = argparse.ArgumentParser()
    lector.add_argument("--capa", required=True, choices=["silver", "gold", "tests"])
    lector.add_argument("--run_id", required=True)
    argumentos = lector.parse_args()

    conexion = duckdb.connect(str(ARCHIVO_DUCKDB))
    try:
        if argumentos.capa == "silver":
            validar_silver(argumentos.run_id, conexion)
        elif argumentos.capa == "gold":
            validar_gold(argumentos.run_id, conexion)
        else:
            registrar_tests_dbt(argumentos.run_id, CARPETA_PROYECTO / "dbt_project" / "target" / "run_results.json")
    except ValidacionFallida:
        sys.exit(1)
    finally:
        conexion.close()
