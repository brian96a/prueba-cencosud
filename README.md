# Demo de cuadratura entre capas

Ver el enunciado en [ENUNCIADO.md](ENUNCIADO.md) y los diagramas en [diagramas.html](diagramas.html).

## Instalar
```
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```
(la primera corrida de dbt descarga la extensión `iceberg` de DuckDB, requiere internet)

## Correr
```
.venv/bin/python -m jobs.run_demo bueno    # todo cuadra, termina OK
.venv/bin/python -m jobs.run_demo vacio    # bronze carga 0 filas: FAILED + alerta
.venv/bin/python -m jobs.run_demo malo     # silver pierde el 70% de las filas: FAILED + alerta
.venv/bin/python -m jobs.run_demo duplicado # 4 id_venta repetidos (17% de llaves duplicadas): falla la calidad de bronze
.venv/bin/python -m jobs.run_demo nulos     # 30% de nulos en producto: falla la calidad de bronze
.venv/bin/duckdb demo.duckdb               # luego pega las consultas de consultas.sql
```
Para repetir la demo desde cero: `rm -rf demo.duckdb warehouse alertas.log`

## Piezas
| Carpeta | Qué es | En AWS |
|---|---|---|
| `recon_utils/` | Librería de validación (reglas, traza, alertas) | .whl versionado |
| `jobs/bronze_ventas.py` | Job de bronze | Glue Job / EMR Serverless |
| `jobs/validar_dbt.py` | Validación después del dbt run | Tarea de Step Functions |
| `jobs/run_demo.py` | Orquestador | Step Functions |
| `dbt_project/` | Silver y gold | dbt con conector de Glue |
| `esquemas/*.json` | Esquema y reglas de conteo por tabla | Tabla DynamoDB |

## Test de dbt
dbt tiene un solo test propio: `dbt_project/tests/gold_llaves_vs_silver.sql`, que compara las llaves distintas de silver
(tienda y día) con las filas de gold. La llave primaria y los nulos los valida `recon_utils` con el esquema del catálogo,
para tener una sola regla por tabla.

## Esquemas y calidad
Los esquemas no están en el código: viven en `esquemas/*.json` y `jobs/run_demo.py` los registra al empezar en `meta.esquemas`
(en AWS sería una tabla DynamoDB). Cada esquema define tipos, llave primaria, `nulos_max_pct` por columna y
`margen_minimo_pct` (90): cada revisión pasa si al menos el 90% de las filas está bien.
Cada archivo procesado queda en `meta.archivos_ejecutados` (cuándo, cuántas filas, qué columnas traía, qué versión de esquema).
El resultado del test de dbt queda en `audit.resultados_tests_dbt`.

## Alertas
`recon_utils/alertas.yml` define, por tabla, quién es el responsable y por qué canales se avisa (log y correo vía SNS).
El correo (SNS) se envía de verdad solo si existe `SNS_TOPIC_ARN`; si no, quedan como SIMULADO.
Cada alerta y su canal quedan en `audit.alertas`.

## Create table
- `ddl/duckdb_traza.sql`: tablas de traza y metadata de la demo (las usa `recon_utils`).
- `ddl/aws_referencia.sql`: equivalentes en Athena (Iceberg) y claves de DynamoDB. Es solo referencia, no se ejecuta en la demo.
- La tabla Iceberg `bronze.ventas` la crea el job de bronze desde `esquemas/bronze_ventas.json`; silver y gold las crea dbt.

## Reglas de conteo
Están en la sección `reglas_conteo` de cada `esquemas/*.json`:
- `tipo`: `uno_a_uno` (salida = entrada), `filtra` (salida menor, pero no menos de `minimo_pct`) o `agrega` (salida = grupos distintos de la capa anterior).
- `minimo_filas`, `tolerancia_pct`, `minimo_pct`, `minimo_pct_historial` (contra el promedio de las últimas 5 corridas buenas).
- `revisar_fecha_carga` y `revisar_suma` (la suma de monto debe coincidir entre capas).
