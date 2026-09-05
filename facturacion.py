# -*- coding: utf-8 -*-
"""
Cálculo de totales de venta para PERNO TODO.

Se aísla esta lógica del resto de app.py (que maneja la base de datos y las
rutas de Flask) para poder probarla de forma automatizada, sin necesidad de
levantar el servidor ni la base de datos.
"""


def calcular_totales(total_bruto, descuento_pct, iva_pct=15.0):
    """Calcula el desglose de una venta a partir del total bruto del carrito.

    Los precios de venta en PERNO TODO YA INCLUYEN IVA, por lo que el
    subtotal (base imponible) se obtiene dividiendo el total final entre
    (1 + iva_pct/100), y el IVA es la diferencia entre el total y esa base.

    Args:
        total_bruto: suma de (precio_venta * cantidad) de todos los items,
            antes de aplicar descuento.
        descuento_pct: porcentaje de descuento a aplicar (se limita a
            un rango de 0 a 100).
        iva_pct: porcentaje de IVA vigente (por defecto 15, IVA Ecuador).

    Returns:
        dict con 'descuento', 'total', 'subtotal' e 'iva', todos
        redondeados a 2 decimales.
    """
    descuento_pct = min(max(descuento_pct, 0.0), 100.0)
    desc_monto = round(total_bruto * (descuento_pct / 100.0), 2)
    total_final = round(total_bruto - desc_monto, 2)
    subtotal_base = round(total_final / (1 + iva_pct / 100.0), 2)
    iva_monto = round(total_final - subtotal_base, 2)

    return {
        'descuento': desc_monto,
        'total': total_final,
        'subtotal': subtotal_base,
        'iva': iva_monto,
    }
