-- Gold: una fila por tienda y día.
select
    id_tienda,
    fecha_venta,
    count(*)            as cantidad_ventas,
    sum(monto)          as monto_total,
    cast(now() as timestamp) as fecha_carga
from {{ ref('ventas') }}
group by id_tienda, fecha_venta
