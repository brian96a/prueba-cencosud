-- Lee la tabla Iceberg que dejó el job de bronze.
-- En AWS esta capa sería una fuente de Glue (source) apuntando a bronze.ventas.
select * from iceberg_scan('{{ var("ruta_bronze") }}')
