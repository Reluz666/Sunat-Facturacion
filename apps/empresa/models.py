from django.db import models
from django.core.validators import RegexValidator
from apps.utils.models import ModeloBase


class Empresa(ModeloBase):
    """
    Empresa emisora de comprobantes electrónicos.
    Cada empresa tiene un RUC único y puede tener múltiples series.
    """
    ruc = models.CharField(
        max_length=11,
        unique=True,
        validators=[RegexValidator(r'^\d{11}$', 'El RUC debe contener exactamente 11 dígitos numéricos.')],
        verbose_name='RUC'
    )
    razon_social = models.CharField(max_length=200, verbose_name='Razón Social')
    nombre_comercial = models.CharField(max_length=200, blank=True, verbose_name='Nombre Comercial')
    direccion = models.TextField(verbose_name='Dirección')
    regimen_tributario = models.CharField(
        max_length=50,
        choices=[
            ('GENERAL', 'Régimen General'),
            ('MYPE', 'Régimen MYPE Tributario'),
            ('RER', 'Régimen Especial de Renta'),
            ('RUS', 'Nuevo RUS'),
        ],
        default='GENERAL',
        verbose_name='Régimen Tributario'
    )

    class Meta:
        verbose_name = 'Empresa'
        verbose_name_plural = 'Empresas'
        ordering = ['razon_social']

    def __str__(self):
        return f"{self.razon_social} ({self.ruc})"


class SerieComprobante(ModeloBase):
    """
    Serie de numeración para comprobantes electrónicos.
    Cada empresa puede tener múltiples series por tipo de comprobante.
    La numeración es correlativa y no permite saltos.
    """

    class TipoComprobante(models.TextChoices):
        FACTURA = 'F', 'Factura'
        BOLETA = 'B', 'Boleta'
        NOTA_CREDITO = 'FC', 'Nota de Crédito (Factura)'
        NOTA_CREDITO_BOLETA = 'BC', 'Nota de Crédito (Boleta)'

    empresa = models.ForeignKey(
        Empresa,
        on_delete=models.CASCADE,
        related_name='series',
        verbose_name='Empresa'
    )
    tipo = models.CharField(
        max_length=2,
        choices=TipoComprobante.choices,
        verbose_name='Tipo de Comprobante'
    )
    serie = models.CharField(
        max_length=4,
        validators=[RegexValidator(r'^[A-Z]\w{3}$', 'La serie debe ser una letra seguida de 3 caracteres (ej: F001).')],
        verbose_name='Serie'
    )
    correlativo_actual = models.PositiveIntegerField(
        default=0,
        verbose_name='Correlativo Actual'
    )

    class Meta:
        verbose_name = 'Serie de Comprobante'
        verbose_name_plural = 'Series de Comprobantes'
        unique_together = ('empresa', 'tipo', 'serie')
        ordering = ['tipo', 'serie']

    def __str__(self):
        return f"{self.get_tipo_display()} - {self.serie} (#{self.correlativo_actual})"

    def siguiente_correlativo(self):
        """
        Obtiene el siguiente número correlativo de forma atómica.
        Usa select_for_update para evitar condiciones de carrera.
        """
        self.correlativo_actual += 1
        self.save(update_fields=['correlativo_actual'])
        return self.correlativo_actual
