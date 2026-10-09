-- Gold debe tener una fila por cada tienda y día distintos que hay en silver.
-- Devuelve una fila (y por lo tanto falla) si los conteos no coinciden.
with llaves_silver as (
    select count(distinct (id_tienda, fecha_venta)) as cantidad from {{ ref('ventas') }}
),
llaves_gold as (
    select count(*) as cantidad from {{ ref('ventas_diarias') }}
)
select llaves_silver.cantidad as llaves_silver, llaves_gold.cantidad as llaves_gold
from llaves_silver, llaves_gold
where llaves_silver.cantidad != llaves_gold.cantidad
