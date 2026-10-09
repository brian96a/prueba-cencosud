-- Silver: deja solo las ventas válidas (monto positivo).
select
    id_venta,
    id_tienda,
    producto,
    monto,
    fecha_venta,
    fecha_carga
from {{ ref('ventas_bronze') }}
where monto is not null
  and monto > 0
