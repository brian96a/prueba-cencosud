"""Orquestador local (simula Step Functions).

Corre los pasos en orden. Si un paso termina con error, la ejecución completa queda FAILED
y los pasos siguientes no se ejecutan.

Uso:  python jobs/run_demo.py bueno | malo | vacio | duplicado | nulos
"""
import json
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path

from jobs.bronze_ventas import abrir_catalogo
from recon_utils import guardar_esquema
from recon_utils.config import CARPETA_PROYECTO, ARCHIVO_DUCKDB

CASOS = {"bueno": "ventas_bueno.csv", "malo": "ventas_malo.csv", "vacio": "ventas_vacio.csv",
         "duplicado": "ventas_duplicado.csv", "nulos": "ventas_nulos.csv"}
PYTHON = sys.executable
DBT = str(Path(PYTHON).parent / "dbt")


def registrar_esquemas():
    """Registra los esquemas de esquemas/*.json en el catálogo (en AWS: put_item a DynamoDB)."""
    for archivo in sorted((CARPETA_PROYECTO / "esquemas").glob("*.json")):
        esquema = json.loads(archivo.read_text())
        guardar_esquema(esquema)
        print(f"Esquema registrado: {esquema['tabla']} (versión {esquema['version']})")


def correr(nombre_paso, comando, ignorar_error=False):
    print(f"\n--- {nombre_paso} ---")
    resultado = subprocess.run(comando, cwd=CARPETA_PROYECTO,
                               env={**os.environ, "PYTHONPATH": str(CARPETA_PROYECTO),
                                    "RUTA_DUCKDB": str(ARCHIVO_DUCKDB),
                                    "PYTHONUNBUFFERED": "1"})
    if resultado.returncode != 0 and not ignorar_error:
        print(f"\n>>> EJECUCIÓN FAILED en el paso: {nombre_paso}")
        sys.exit(1)


def comando_dbt(capa):
    ruta_bronze = abrir_catalogo().load_table("bronze.ventas").metadata_location.replace("file://", "")
    modelos = "ventas_bronze ventas" if capa == "silver" else "ventas_diarias"
    return [DBT, "run", "--project-dir", "dbt_project",
            "--profiles-dir", "dbt_project", "--select", *modelos.split(),
            "--vars", f"{{ruta_bronze: {ruta_bronze}}}"]


def comando_dbt_test():
    ruta_bronze = abrir_catalogo().load_table("bronze.ventas").metadata_location.replace("file://", "")
    # Único test de dbt: compara las llaves de silver con las filas de gold.
    # La llave primaria y los nulos los valida recon_utils con el esquema del catálogo.
    return [DBT, "test", "--project-dir", "dbt_project", "--profiles-dir", "dbt_project",
            "--vars", f"{{ruta_bronze: {ruta_bronze}}}"]


def main(caso):
    run_id = f"{datetime.now():%Y%m%d_%H%M%S}_{caso}"
    print(f"Ejecución {run_id}")

    print("\n--- 0. Registrar esquemas ---")
    registrar_esquemas()
    correr("1. Bronze (job PySpark simulado)",
           [PYTHON, "jobs/bronze_ventas.py", "--archivo", f"data/{CASOS[caso]}", "--run_id", run_id])

    correr("2. Silver (dbt run)", comando_dbt("silver"))
    correr("3. Validar silver (calidad y conteos)", [PYTHON, "jobs/validar_dbt.py", "--capa", "silver", "--run_id", run_id])

    correr("4. Gold (dbt run)", comando_dbt("gold"))
    correr("5. Test de dbt: llaves silver vs gold", comando_dbt_test(), ignorar_error=True)
    correr("5b. Registrar resultado del test", [PYTHON, "jobs/validar_dbt.py", "--capa", "tests", "--run_id", run_id])
    correr("6. Validar gold (calidad y conteos)", [PYTHON, "jobs/validar_dbt.py", "--capa", "gold", "--run_id", run_id])

    print(f"\n>>> EJECUCIÓN {run_id} TERMINÓ OK")


if __name__ == "__main__":
    if len(sys.argv) != 2 or sys.argv[1] not in CASOS:
        sys.exit("Uso: python jobs/run_demo.py bueno | malo | vacio | duplicado | nulos")
    main(sys.argv[1])
