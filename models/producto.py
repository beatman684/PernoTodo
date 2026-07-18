"""
Modelo Producto — PERNO TODO
Referencia directa a la tabla 'productos' de la base de datos.
"""

class Producto:
    """Representa un producto del inventario."""

    def __init__(self, id_producto=None, codigo_producto=None, nombre_producto=None,
                 descripcion=None, material=None, tipo_rosca=None, medida=None,
                 unidad_medida='unidad', precio_compra=0.0, precio_venta=0.0,
                 stock_actual=0, stock_minimo=10, id_proveedor=None,
                 id_categoria=None, fecha_creacion=None, fecha_actualizacion=None,
                 nombre_proveedor=None, nombre_categoria=None):
        self.id_producto         = id_producto
        self.codigo_producto     = codigo_producto
        self.nombre_producto     = nombre_producto
        self.descripcion         = descripcion
        self.material            = material
        self.tipo_rosca          = tipo_rosca
        self.medida              = medida
        self.unidad_medida       = unidad_medida
        self.precio_compra       = precio_compra
        self.precio_venta        = precio_venta
        self.stock_actual        = stock_actual
        self.stock_minimo        = stock_minimo
        self.id_proveedor        = id_proveedor
        self.id_categoria        = id_categoria
        self.fecha_creacion      = fecha_creacion
        self.fecha_actualizacion = fecha_actualizacion
        # Campos de JOIN (opcionales)
        self.nombre_proveedor    = nombre_proveedor
        self.nombre_categoria    = nombre_categoria

    @property
    def bajo_stock(self):
        return self.stock_actual < self.stock_minimo

    @property
    def margen(self):
        if self.precio_compra and self.precio_compra > 0:
            return round((self.precio_venta - self.precio_compra) / self.precio_compra * 100, 2)
        return 0.0

    def __repr__(self):
        return f"<Producto {self.codigo_producto} — {self.nombre_producto}>"