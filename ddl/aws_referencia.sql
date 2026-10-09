-- Referencia para AWS. La demo local NO ejecuta este archivo (no probado contra Athena).
-- En la demo, la tabla Iceberg bronze.ventas la crea jobs/bronze_ventas.py a partir de esquemas/bronze_ventas.json.

-- Iceberg no exige llave primaria ni partición, y no hace cumplir llaves primarias.
-- Por eso la llave la declaramos en el esquema registrado (DynamoDB) y la valida recon_utils.
-- La partición es opcional, pero conviene en tablas grandes: Iceberg usa partición oculta
-- (funciones como day, month, bucket), no hace falta una columna extra.

-- Athena: tabla Iceberg de bronze
CREATE TABLE bronze.ventas (
    id_venta     bigint,
    id_tienda    string,
    producto     string,
    monto        double,
    fecha_venta  string,
    fecha_carga  timestamp
)
PARTITIONED BY (day(fecha_carga))
LOCATION 's3://<bucket>/bronze/ventas/'
TBLPROPERTIES ('table_type' = 'ICEBERG');

-- Athena: traza de conteos (tabla Iceberg)
CREATE TABLE audit.conteos_por_capa (
    run_id          string,
    capa            string,
    tabla           string,
    filas_entrada   bigint,
    filas_salida    bigint,
    fecha_carga     timestamp,
    estado          string,
    motivo          string,
    registrado_en   timestamp
)
PARTITIONED BY (day(registrado_en))
LOCATION 's3://<bucket>/audit/conteos_por_capa/'
TBLPROPERTIES ('table_type' = 'ICEBERG');

-- audit.calidad_por_columna, audit.resultados_tests_dbt y audit.alertas siguen el mismo patrón
-- (ver ddl/duckdb_traza.sql para sus columnas).

-- DynamoDB (solo claves; el resto de atributos son libres)
--   esquemas             clave de partición: tabla (string)
--   archivos_ejecutados  clave de partición: run_id (string), clave de orden: tabla (string)
