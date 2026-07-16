from django.db import models
from django.conf import settings
from django.core.validators import MinValueValidator
from django.core.exceptions import ValidationError
from decimal import Decimal
from apps.utils.models import ModeloBase


class Comprobante(ModeloBase):
    """
    Comprobante electrónico (Factura, Boleta o Nota de Crédito).

    Flujo de estados:
      BORRADOR → EMITIDO → ENVIADO → ACEPTADO / RECHAZADO

    Modelo Matemático:
      Base Imponible = Σ (cantidad_i × precio_unitario_i × (1 - descuento_i))  [productos afectos]
      IGV = Base Imponible × 0.18
      Total = Base Imponible + IGV + Σ (productos inafectos)

    Reglas de negocio:
      - Numeración correlativa y única por serie, sin saltos.
      - Factura requiere RUC (11 dígitos).
      - Boleta acepta DNI.
      - Comprobante ACEPTADO no se puede eliminar, solo anular vía nota de crédito.
    """

    class TipoComprobante(models.TextChoices):
        FACTURA = 'FACTURA', 'Factura'
        BOLETA = 'BOLETA', 'Boleta'
        NOTA_CREDITO = 'NOTA_CREDITO', 'Nota de Crédito'

    class EstadoComprobante(models.TextChoices):
        BORRADOR = 'BORRADOR', 'Borrador'
        EMITIDO = 'EMITIDO', 'Emitido'
        ENVIADO = 'ENVIADO', 'Enviado'
        ACEPTADO = 'ACEPTADO', 'Aceptado'
        RECHAZADO = 'RECHAZADO', 'Rechazado'

    # ── Identificación del comprobante ────────────────────────────
    serie = models.CharField(max_length=4, verbose_name='Serie')
    numero = models.PositiveIntegerField(verbose_name='Número')
    tipo = models.CharField(
        max_length=15,
        choices=TipoComprobante.choices,
        verbose_name='Tipo de Comprobante'
    )
    fecha_emision = models.DateField(auto_now_add=True, verbose_name='Fecha de Emisión')

    # ── Relaciones ────────────────────────────────────────────────
    cliente = models.ForeignKey(
        'clientes.Cliente',
        on_delete=models.PROTECT,
        related_name='comprobantes',
        verbose_name='Cliente'
    )
    empresa = models.ForeignKey(
        'empresa.Empresa',
        on_delete=models.PROTECT,
        related_name='comprobantes',
        verbose_name='Empresa'
    )

    # ── Montos calculados ─────────────────────────────────────────
    subtotal = models.DecimalField(
        max_digits=12, decimal_places=2, default=Decimal('0.00'),
        verbose_name='Subtotal (Base Imponible)'
    )
    total_inafecto = models.DecimalField(
        max_digits=12, decimal_places=2, default=Decimal('0.00'),
        verbose_name='Total Inafecto'
    )
    igv = models.DecimalField(
        max_digits=12, decimal_places=2, default=Decimal('0.00'),
        verbose_name='IGV (18%)'
    )
    total = models.DecimalField(
        max_digits=12, decimal_places=2, default=Decimal('0.00'),
        verbose_name='Total'
    )

    # ── Estado y SUNAT ────────────────────────────────────────────
    estado = models.CharField(
        max_length=10,
        choices=EstadoComprobante.choices,
        default=EstadoComprobante.BORRADOR,
        verbose_name='Estado'
    )
    xml_firmado = models.TextField(blank=True, verbose_name='XML Firmado')
    hash_cpe = models.CharField(max_length=64, blank=True, verbose_name='Hash CPE')

    class Meta:
        verbose_name = 'Comprobante'
        verbose_name_plural = 'Comprobantes'
        unique_together = ('serie', 'numero')
        ordering = ['-fecha_emision', '-numero']
        indexes = [
            models.Index(fields=['tipo', 'estado']),
            models.Index(fields=['fecha_emision']),
            models.Index(fields=['serie', 'numero']),
        ]

    def __str__(self):
        return f"{self.serie}-{self.numero:05d} ({self.get_tipo_display()}) - {self.get_estado_display()}"

    @property
    def serie_numero(self):
        return f"{self.serie}-{self.numero:05d}"


    @property
    def tipo_sunat(self):
        mapa = {
            self.TipoComprobante.FACTURA: '01',
            self.TipoComprobante.BOLETA: '03',
            self.TipoComprobante.NOTA_CREDITO: '07',
        }
        return mapa.get(self.tipo, '01')

    def eliminar(self, usuario=None):
        """Comprobante ACEPTADO no se puede eliminar (soft delete)."""
        if self.estado == self.EstadoComprobante.ACEPTADO:
            raise ValidationError(
                'No se puede eliminar un comprobante ACEPTADO. Use una Nota de Crédito para anularlo.'
            )
        super().eliminar(usuario=usuario)


class DetalleComprobante(ModeloBase):
    """
    Línea de detalle de un comprobante.

    Modelo Matemático por línea:
      valor_venta = cantidad × precio_unitario
      descuento_monto = valor_venta × (descuento / 100)
      subtotal = valor_venta - descuento_monto
      igv_linea = subtotal × 0.18  (si producto es afecto)
      total_linea = subtotal + igv_linea
    """

    comprobante = models.ForeignKey(
        Comprobante,
        on_delete=models.CASCADE,
        related_name='detalles',
        verbose_name='Comprobante'
    )
    producto = models.ForeignKey(
        'productos.Producto',
        on_delete=models.PROTECT,
        related_name='detalles_comprobante',
        verbose_name='Producto'
    )
    cantidad = models.DecimalField(
        max_digits=10, decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))],
        verbose_name='Cantidad'
    )
    precio_unitario = models.DecimalField(
        max_digits=12, decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))],
        verbose_name='Precio Unitario'
    )
    descuento = models.DecimalField(
        max_digits=5, decimal_places=2, default=Decimal('0.00'),
        validators=[MinValueValidator(Decimal('0.00'))],
        verbose_name='Descuento (%)',
        help_text='Porcentaje de descuento aplicado a esta línea.'
    )
    igv_linea = models.DecimalField(
        max_digits=12, decimal_places=2, default=Decimal('0.00'),
        verbose_name='IGV Línea'
    )
    subtotal = models.DecimalField(
        max_digits=12, decimal_places=2, default=Decimal('0.00'),
        verbose_name='Subtotal Línea'
    )

    class Meta:
        verbose_name = 'Detalle de Comprobante'
        verbose_name_plural = 'Detalles de Comprobante'
        ordering = ['id']

    def __str__(self):
        return f"{self.producto.descripcion} x{self.cantidad} = S/.{self.subtotal}"


class NotaCredito(ModeloBase):
    """
    Nota de crédito que referencia un comprobante original.

    Reglas:
      - El monto_afectado no puede superar el total del comprobante original.
      - Genera un nuevo comprobante de tipo NOTA_CREDITO.
    """

    class TipoNota(models.TextChoices):
        ANULACION = '01', 'Anulación de la operación'
        ANULACION_ERROR = '02', 'Anulación por error en el RUC'
        CORRECCION_DESCRIPCION = '03', 'Corrección por error en la descripción'
        DESCUENTO_GLOBAL = '04', 'Descuento global'
        DESCUENTO_ITEM = '05', 'Descuento por ítem'
        DEVOLUCION_TOTAL = '06', 'Devolución total'
        DEVOLUCION_ITEM = '07', 'Devolución por ítem'

    comprobante_nota = models.OneToOneField(
        Comprobante,
        on_delete=models.CASCADE,
        related_name='nota_credito_info',
        verbose_name='Comprobante (Nota de Crédito)'
    )
    comprobante_referencia = models.ForeignKey(
        Comprobante,
        on_delete=models.PROTECT,
        related_name='notas_credito',
        verbose_name='Comprobante de Referencia'
    )
    motivo = models.TextField(verbose_name='Motivo')
    tipo_nota = models.CharField(
        max_length=2,
        choices=TipoNota.choices,
        default=TipoNota.ANULACION,
        verbose_name='Tipo de Nota'
    )
    monto_afectado = models.DecimalField(
        max_digits=12, decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))],
        verbose_name='Monto Afectado (S/.)'
    )

    class Meta:
        verbose_name = 'Nota de Crédito'
        verbose_name_plural = 'Notas de Crédito'

    def __str__(self):
        return f"NC {self.comprobante_nota.serie_numero} → {self.comprobante_referencia.serie_numero}"

    def clean(self):
        super().clean()
        if self.monto_afectado and self.comprobante_referencia_id:
            if self.monto_afectado > self.comprobante_referencia.total:
                raise ValidationError({
                    'monto_afectado': (
                        f'El monto afectado (S/.{self.monto_afectado}) no puede superar '
                        f'el total del comprobante original (S/.{self.comprobante_referencia.total}).'
                    )
                })


class LogEnvioSUNAT(ModeloBase):
    """
    Registro de cada intento de envío al OSE (Operador de Servicios Electrónicos).
    Permite trazabilidad completa del ciclo de vida del comprobante ante SUNAT.
    """

    class EstadoRespuesta(models.TextChoices):
        PENDIENTE = 'PENDIENTE', 'Pendiente'
        ACEPTADO = 'ACEPTADO', 'Aceptado'
        RECHAZADO = 'RECHAZADO', 'Rechazado'
        EXCEPCION = 'EXCEPCION', 'Excepción'

    comprobante = models.ForeignKey(
        Comprobante,
        on_delete=models.CASCADE,
        related_name='logs_envio',
        verbose_name='Comprobante'
    )
    fecha_envio = models.DateTimeField(auto_now_add=True, verbose_name='Fecha de Envío')
    estado_respuesta = models.CharField(
        max_length=20,
        choices=EstadoRespuesta.choices,
        default=EstadoRespuesta.PENDIENTE,
        verbose_name='Estado de Respuesta'
    )
    codigo_respuesta = models.CharField(
        max_length=20, blank=True, verbose_name='Código de Respuesta'
    )
    descripcion = models.TextField(blank=True, verbose_name='Descripción de Respuesta')

    class Meta:
        verbose_name = 'Log de Envío SUNAT'
        verbose_name_plural = 'Logs de Envío SUNAT'
        ordering = ['-fecha_envio']

    def __str__(self):
        return f"Envío {self.comprobante.serie_numero} - {self.get_estado_respuesta_display()}"
