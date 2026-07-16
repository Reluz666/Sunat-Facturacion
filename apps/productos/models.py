from django.db import models
from django.core.validators import MinValueValidator
from decimal import Decimal
from apps.utils.models import ModeloBase


class Producto(ModeloBase):
    """
    Producto o servicio que puede incluirse en un comprobante.
    El flag afecto_igv determina si se aplica el IGV (18%) al producto.

    Modelo Matemático:
      Si afecto_igv = True:
        IGV_linea = cantidad × precio_unitario × (1 - descuento%) × 0.18
      Si afecto_igv = False:
        IGV_linea = 0
    """

    class UnidadMedida(models.TextChoices):
        UNIDAD = 'NIU', 'Unidad'
        KILOGRAMO = 'KGM', 'Kilogramo'
        LITRO = 'LTR', 'Litro'
        METRO = 'MTR', 'Metro'
        SERVICIO = 'ZZ', 'Servicio'
        PAQUETE = 'PK', 'Paquete'

    codigo = models.CharField(max_length=20, unique=True, verbose_name='Código')
    descripcion = models.CharField(max_length=250, verbose_name='Descripción')
    unidad_medida = models.CharField(
        max_length=3,
        choices=UnidadMedida.choices,
        default=UnidadMedida.UNIDAD,
        verbose_name='Unidad de Medida'
    )
    precio_unitario = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))],
        verbose_name='Precio Unitario (S/.)'
    )
    afecto_igv = models.BooleanField(
        default=True,
        verbose_name='Afecto a IGV',
        help_text='Si está marcado, se calcula IGV (18%) sobre este producto.'
    )

    class Meta:
        verbose_name = 'Producto'
        verbose_name_plural = 'Productos'
        ordering = ['descripcion']

    def __str__(self):
        igv_tag = '(+IGV)' if self.afecto_igv else '(Inafecto)'
        return f"{self.codigo} - {self.descripcion} S/.{self.precio_unitario} {igv_tag}"
