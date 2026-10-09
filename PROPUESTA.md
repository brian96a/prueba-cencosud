# Propuesta: Data Reconciliation & Validation

## Resumen

Se propone una librería Python, `recon_utils`, que cada pipeline invoca al terminar un tramo. La librería compara lo que entró y lo que salió de cada capa, revisa la calidad de los datos contra un esquema registrado y deja una traza consultable. Si algo no cuadra, la ejecución queda FAILED y se avisa por correo al responsable de la tabla. Así un proceso que carga 0 filas, o muy pocas, no puede terminar en verde sin que alguien se entere.

La misma librería se usa en bronze (script PySpark) y en silver-gold (dbt). Los diagramas de la arquitectura real y de la demo están en [diagramas.html](diagramas.html), y el modelo de datos en [modelo_datos.html](modelo_datos.html).

## 1. Qué se compara y cómo

Se compara conteo, calidad y contenido. El conteo solo detecta el caso de 0 filas, no que los datos vengan rotos.

| Revisión | Qué detecta |
|---|---|
| Mínimo de filas | Cargas de 0 filas o muy por debajo de lo esperado |
| Conteo entre capas, según el tipo de regla | Pérdida o multiplicación de filas |
| Promedio histórico | Cargas muy distintas a las últimas 5 corridas buenas |
| Fecha de carga | Datos que no se actualizaron hoy |
| Llave primaria | Filas duplicadas o sin llave |
| Nulos por columna | Campos que dejaron de venir poblados |
| Suma de `monto` entre silver y gold | Contenido alterado aunque el conteo coincida |

**Qué es un conteo aceptable cuando las capas no son 1:1.** Cada tabla declara su tipo de regla en la sección `reglas_conteo` de su esquema registrado:

- `uno_a_uno` (bronze contra el origen): la salida debe ser igual a la entrada, con una tolerancia en %.
- `filtra` (silver respecto a bronze): la salida puede ser menor, pero no debajo de un porcentaje mínimo. Además, nunca puede ser mayor que la entrada.
- `agrega` (gold respecto a silver): no se compara contra las filas de entrada. Se compara contra las **llaves distintas** de silver (por ejemplo, tienda y día), que es lo que gold debería tener.

**Esquema y margen del 90%.** Cada tabla tiene un esquema registrado con tipos, llave primaria y tolerancia de nulos por columna. Cada revisión de calidad pasa si al menos el 90% de las filas está bien, y una columna puede declarar un límite propio. Los valores que no se pueden convertir al tipo declarado cuentan como nulos.

## 2. Dónde vive la lógica

Es una **librería** versionada (`recon_utils`) que cada tarea importa. Los umbrales y esquemas son datos, no código: viven juntos en el esquema registrado de cada tabla en el catálogo (DynamoDB): tipos, llave primaria, nulos y reglas de conteo.

Se eligió librería y no servicio por estas razones:

- Glue, EMR Serverless y dbt ya ejecutan Python. Un servicio agrega infraestructura, un punto de falla y una llamada de red a cada tarea.
- Un servicio central de validación tendría que acceder a los datos de cada capa, o recibir los datos ya calculados por el pipeline. Con la librería, cada pipeline calcula lo suyo y la librería decide.
- El beneficio de un servicio, que es versionar la lógica en un solo lugar, se logra publicando la librería como paquete versionado (`.whl` en S3 o CodeArtifact). Cada pipeline fija la versión que usa.

## 3. Cómo se integra en cada tramo

| Tramo | Cómo invoca la validación |
|---|---|
| Bronze (PySpark en Glue o EMR Serverless) | El script llama a `validar_calidad` antes de cargar y a `validar_conteo` al terminar la carga |
| Silver-gold (dbt) | Un paso externo de la state machine, posterior al `dbt run`, ejecuta `validar_dbt.py`, que llama a las mismas funciones |

El orden de ejecución es: bronze, silver, validar silver, gold, test de dbt y validar gold. Si un paso falla, los siguientes no corren, así que los datos incompletos no llegan a capas posteriores.

Se eligió un paso externo y no un test de dbt por una razón práctica: la validación debe escribir la traza y enviar la alerta, y eso no se hace bien desde dentro de dbt. dbt conserva un único test propio, `gold_llaves_vs_silver`, que compara las llaves de silver con las filas de gold. La llave primaria y los nulos los valida solo `recon_utils`, para que cada regla exista en un único lugar.

## 4. Qué pasa cuando falla

Ocurren las dos cosas a la vez:

- **La ejecución queda FAILED.** El paso termina con error, así que la state machine no puede terminar en verde.
- **Se avisa por correo.** La alerta se publica en un topic de SNS y llega por correo a los suscritos. El destinatario se define por tabla en `alertas.yml` (por ejemplo, el equipo de ingesta para bronze y el de analytics para silver y gold). Cada alerta y su canal quedan registrados en la tabla `audit.alertas`.

Una alerta que no se pueda enviar no tapa la falla original: el error se registra y la ejecución igual queda FAILED.

## 5. Dónde queda la traza

Todo queda en tablas consultables, no solo en el log de la corrida:

| Tabla | Contenido |
|---|---|
| `audit.conteos_por_capa` | Filas de entrada y salida de cada capa por ejecución, fecha de carga, estado y motivo |
| `audit.calidad_por_columna` | Porcentaje de llaves únicas y no nulos por columna, contra el mínimo exigido |
| `audit.resultados_tests_dbt` | Resultado del test de dbt por ejecución |
| `audit.alertas` | Cada alerta enviada, a quién y por qué canal |
| `meta.esquemas` | Esquema registrado de cada tabla, con su versión |
| `meta.archivos_ejecutados` | Cada archivo procesado: cuándo, tamaño, filas, columnas que traía y versión de esquema |

En AWS, las tablas `audit.*` serían tablas Iceberg consultables desde Athena. Las tablas `meta.*` vivirían en DynamoDB, que es donde se controlan los logs y la metadata de las tablas.

## Demo local

La demo simula la arquitectura con piezas locales: pandas y PyIceberg para bronze, dbt-duckdb para silver y gold, y DuckDB para las tablas de traza y metadata. Instrucciones en [README.md](README.md).

| Caso | Qué muestra | Resultado |
|---|---|---|
| `bueno` | Todo cuadra | Termina OK |
| `vacio` | El job carga 0 filas y "termina bien" | FAILED en bronze y alerta |
| `duplicado` | 17% de llaves duplicadas | FAILED en bronze y alerta |
| `nulos` | 30% de nulos en `producto` | FAILED en bronze y alerta |
| `malo` | Silver conserva solo el 30% de las filas | FAILED en silver y alerta; gold no corre |

## Limitaciones de la demo

- Bronze usa pandas y PyIceberg en lugar de PySpark. En el código están comentados los equivalentes en Spark.
- Silver y gold son tablas de DuckDB, no Iceberg, y dbt corre sobre DuckDB, no sobre el conector de Glue.
- DynamoDB está simulado con tablas de DuckDB. El envío por SNS no se ejecutó contra AWS: sin la variable `SNS_TOPIC_ARN` la alerta queda registrada como SIMULADO.
- No se probó en Glue, EMR Serverless ni Step Functions. El diseño para AWS es la propuesta; la demo valida la lógica y el flujo.
