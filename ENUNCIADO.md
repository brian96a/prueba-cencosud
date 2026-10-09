# Ejercicio técnico — Pieza Data Reconciliation & Validation

> CONFIDENCIAL – CENCOSUD S.A. Documento entregado exclusivamente para fines del proceso de selección.

## Contexto

Se solicita evaluar la incorporación de una tarea de **cuadratura** dentro de los flujos de datos, idealmente al finalizar el flujo, que permita validar automáticamente la carga y consistencia de datos entre las capas/tablas involucradas.

Actualmente existen procesos que finalizan en **Success**, pero posteriormente se detecta que **no hubo carga de datos**. La idea es que esta validación permita detectar estos casos y, según el resultado, generar una alerta o marcar la ejecución como fallida.

Se espera que la implementación permita:

- Detectar procesos que finalizan en verde, pero no cargan información.
- Validar la cantidad y consistencia de registros entre capas.
- Validar la fecha de carga de los datos.
- Generar alertas ante diferencias o ausencia de información.
- Mejorar el monitoreo y reducir el riesgo de que datos incompletos lleguen a capas posteriores sin ser detectados.

### Detalle técnico a considerar

- Tablas **Iceberg**.
- Extracciones (capa **bronze**) con scripts **PySpark**, sobre **Glue jobs** o **EMR Serverless**.
- Transformaciones (capa **silver-gold**) con **DBT**, mediante conector de Glue.

## El problema a resolver

Proponer cómo validar la cantidad de registros que carga cada capa (bronze → silver → gold, o las que correspondan en nuestro modelo) de forma que:

1. Quede una **traza clara** de cuántos registros entraron y salieron de cada capa en cada ejecución.
2. Un proceso que cargó **0 registros** (o muchos menos de los esperados) **no pueda terminar en verde** sin que alguien se entere.

## Qué se debe entregar

Una **propuesta escrita**, más una **demo** que muestre el flujo funcionando en lo esencial (puede ser con datos de prueba).

La propuesta debe cubrir al menos:

1. **Qué se compara y cómo**: ¿solo conteo de registros, o también consistencia de contenido? ¿Cómo se define qué es un conteo "aceptable" entre capas si no son 1:1 (por ejemplo, si gold agrega o filtra respecto a silver)?
2. **Dónde vive la lógica de validación**: diseñarla como una capacidad **reutilizable**, no como código pegado dentro de cada pipeline. ¿Librería que cada tarea importa? ¿Servicio al que cada pipeline llama? Justificar la elección.
3. **Cómo se integra en cada tramo del pipeline**: bronze corre con scripts PySpark, silver-gold corre con DBT. Mostrar cómo la validación se invoca en ambos tramos **sin duplicar la lógica** — por ejemplo, ¿DBT la dispara como un test propio, o como un paso externo posterior al `dbt run`?
4. **Qué pasa cuando falla**: ¿la ejecución se marca FAILED, se dispara una alerta, o ambas? ¿Quién la recibe y por qué canal?
5. **Dónde queda la traza**: cuántos registros entraron/salieron de cada capa, en cada ejecución, tiene que quedar **consultable después** — no solo en el log de la corrida que ya pasó.
