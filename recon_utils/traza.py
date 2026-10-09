"""Todo lo que se guarda en DuckDB: la traza de conteos, los esquemas de las tablas y el log de archivos.

En AWS la traza serían tablas Iceberg (Athena) y los esquemas y el log serían tablas DynamoDB.
"""
import json
import duckdb
from datetime import datetime

from recon_utils.config import ARCHIVO_DUCKDB, CARPETA_PROYECTO

ARCHIVO_DDL = CARPETA_PROYECTO / "ddl" / "duckdb_traza.sql"  # aquí están los create table


def abrir_traza():
    conexion = duckdb.connect(str(ARCHIVO_DUCKDB))
    conexion.execute(ARCHIVO_DDL.read_text())
    return conexion


def registrar_conteo(run_id, tabla, filas_entrada, filas_salida, fecha_carga, estado, motivo):
    capa = tabla.split(".")[0]
    conexion = abrir_traza()
    conexion.execute(
        "insert into audit.conteos_por_capa values (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        [run_id, capa, tabla, filas_entrada, filas_salida, fecha_carga, estado, motivo, datetime.now()],
    )
    conexion.close()


def filas_salida_de(run_id, tabla):
    """Filas que dejó una tabla en esta corrida (sirve como entrada de la capa siguiente)."""
    conexion = abrir_traza()
    resultado = conexion.execute(
        "select filas_salida from audit.conteos_por_capa where run_id = ? and tabla = ?",
        [run_id, tabla],
    ).fetchone()
    conexion.close()
    return resultado[0] if resultado else None


def promedio_historico(tabla, ultimas=5):
    """Promedio de filas de las últimas corridas buenas. None si no hay historia."""
    conexion = abrir_traza()
    resultado = conexion.execute(
        """select avg(filas_salida) from (
               select filas_salida from audit.conteos_por_capa
               where tabla = ? and estado = 'OK'
               order by registrado_en desc limit ?)""",
        [tabla, ultimas],
    ).fetchone()
    conexion.close()
    return resultado[0]


# --- Esquemas de las tablas (en AWS: DynamoDB, tabla `esquemas`, clave: tabla) ---

def guardar_esquema(esquema):
    conexion = abrir_traza()
    conexion.execute("delete from meta.esquemas where tabla = ?", [esquema["tabla"]])
    conexion.execute("insert into meta.esquemas values (?, ?, ?, ?)",
                     [esquema["tabla"], esquema["version"], json.dumps(esquema), datetime.now()])
    conexion.close()


def obtener_esquema(tabla):
    conexion = abrir_traza()
    fila = conexion.execute("select esquema from meta.esquemas where tabla = ?", [tabla]).fetchone()
    conexion.close()
    if fila is None:
        raise ValueError(f"No hay esquema registrado para {tabla}")
    return json.loads(fila[0])


# --- Log de cada archivo procesado (en AWS: DynamoDB, tabla `archivos_ejecutados`, clave: run_id + tabla) ---

def registrar_archivo(run_id, tabla, archivo, tamano_bytes, filas, columnas_archivo, version_esquema):
    conexion = abrir_traza()
    conexion.execute(
        "insert into meta.archivos_ejecutados values (?, ?, ?, ?, ?, ?, ?, 'EN_PROCESO', ?, null)",
        [run_id, tabla, archivo, tamano_bytes, filas, json.dumps(columnas_archivo), version_esquema, datetime.now()])
    conexion.close()


def marcar_archivo(run_id, tabla, estado):
    conexion = abrir_traza()
    conexion.execute(
        "update meta.archivos_ejecutados set estado = ?, terminado_en = ? where run_id = ? and tabla = ?",
        [estado, datetime.now(), run_id, tabla])
    conexion.close()
