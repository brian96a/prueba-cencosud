"""Rutas del proyecto. En AWS serían buckets S3 y tablas Iceberg."""
from pathlib import Path

CARPETA_PROYECTO = Path(__file__).resolve().parent.parent

ARCHIVO_DUCKDB = CARPETA_PROYECTO / "demo.duckdb"       # aquí vive la tabla de traza
ARCHIVO_ALERTAS = CARPETA_PROYECTO / "alertas.log"       # en AWS: un topic SNS
CARPETA_WAREHOUSE = CARPETA_PROYECTO / "warehouse"       # en AWS: bucket S3 con Iceberg
