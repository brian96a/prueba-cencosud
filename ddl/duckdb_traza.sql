-- Tablas de traza y metadata de la demo local (DuckDB).
-- recon_utils las crea al abrir la conexión si no existen.

create schema if not exists audit;
create table if not exists audit.conteos_por_capa (
    run_id          varchar,
    capa            varchar,
    tabla           varchar,
    filas_entrada   bigint,
    filas_salida    bigint,
    fecha_carga     timestamp,
    estado          varchar,
    motivo          varchar,
    registrado_en   timestamp
);
create table if not exists audit.calidad_por_columna (
    run_id          varchar,
    tabla           varchar,
    revision        varchar,
    columna         varchar,
    porcentaje_ok   double,
    minimo_pct      double,
    estado          varchar,
    registrado_en   timestamp
);
create table if not exists audit.resultados_tests_dbt (
    run_id          varchar,
    test            varchar,
    estado          varchar,
    filas_fallidas  bigint,
    registrado_en   timestamp
);
create table if not exists audit.alertas (
    run_id          varchar,
    tabla           varchar,
    responsable     varchar,
    canal           varchar,
    estado_envio    varchar,
    mensaje         varchar,
    enviado_en      timestamp
);
create schema if not exists meta;
create table if not exists meta.esquemas (
    tabla           varchar primary key,
    version         integer,
    esquema         varchar,
    actualizado_en  timestamp
);
create table if not exists meta.archivos_ejecutados (
    run_id            varchar,
    tabla             varchar,
    archivo           varchar,
    tamano_bytes      bigint,
    filas             bigint,
    columnas_archivo  varchar,
    version_esquema   integer,
    estado            varchar,
    iniciado_en       timestamp,
    terminado_en      timestamp
);
