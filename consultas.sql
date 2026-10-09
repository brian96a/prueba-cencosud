-- Consultas para la demo. Se pegan dentro de DuckDB:  .venv/bin/duckdb demo.duckdb
.maxrows 1000
.maxwidth 300

-- Cuántas filas entraron y salieron de cada capa, por ejecución
select run_id, tabla, filas_entrada, filas_salida, estado, motivo
from audit.conteos_por_capa order by registrado_en;

-- Archivos procesados: cuándo, cuántas filas, qué versión de esquema
select run_id, tabla, archivo, filas, estado, version_esquema
from meta.archivos_ejecutados order by iniciado_en;

-- Calidad que falló (llave primaria y nulos)
select run_id, tabla, revision, columna, round(porcentaje_ok) as pct_ok, minimo_pct
from audit.calidad_por_columna where estado = 'FALLIDO' order by registrado_en;

-- Resultado de los tests de dbt
select * from audit.resultados_tests_dbt order by registrado_en;

-- Alertas enviadas
select run_id, tabla, responsable, canal, estado_envio from audit.alertas order by enviado_en;

-- Esquemas y reglas registrados
select tabla, version, esquema from meta.esquemas;

-- Capas de datos
select * from silver.ventas;
select * from gold.ventas_diarias;
