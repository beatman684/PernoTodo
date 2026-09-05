# -*- coding: utf-8 -*-
"""
Pruebas automatizadas del cálculo de totales de venta (facturación) de
PERNO TODO. Cubre el caso normal, el descuento, y los límites del
porcentaje de descuento (regresión frente a valores fuera de rango).
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from facturacion import calcular_totales


def test_totales_sin_descuento():
    r = calcular_totales(total_bruto=115.0, descuento_pct=0)
    assert r['total'] == 115.0
    assert r['subtotal'] == 100.0
    assert r['iva'] == 15.0
    assert r['descuento'] == 0.0


def test_totales_con_descuento():
    r = calcular_totales(total_bruto=100.0, descuento_pct=10)
    assert r['descuento'] == 10.0
    assert r['total'] == 90.0


def test_descuento_mayor_a_100_se_limita():
    r = calcular_totales(total_bruto=100.0, descuento_pct=150)
    assert r['descuento'] == 100.0
    assert r['total'] == 0.0


def test_descuento_negativo_se_limita_a_cero():
    r = calcular_totales(total_bruto=100.0, descuento_pct=-20)
    assert r['descuento'] == 0.0
    assert r['total'] == 100.0


def test_iva_personalizado():
    r = calcular_totales(total_bruto=112.0, descuento_pct=0, iva_pct=12.0)
    assert r['subtotal'] == 100.0
    assert r['iva'] == 12.0
