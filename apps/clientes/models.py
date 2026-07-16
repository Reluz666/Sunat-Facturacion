from django.db import models
from django.core.validators import RegexValidator, MinLengthValidator
from django.core.exceptions import ValidationError
from apps.utils.models import ModeloBase


class Cliente(ModeloBase):
    """
    Cliente receptor de comprobantes electrónicos.
    Validación según tipo de documento:
      - RUC: 11 dígitos (requerido para facturas)
      - DNI: 8 dígitos (válido para boletas)
      - CE: Carné de extranjería
    """

    class TipoDocumento(models.TextChoices):
        RUC = 'RUC', 'RUC'
        DNI = 'DNI', 'DNI'
        CE = 'CE', 'Carné de Extranjería'

    tipo_doc = models.CharField(
        max_length=3,
        choices=TipoDocumento.choices,
        verbose_name='Tipo de Documento'
    )
    num_doc = models.CharField(
        max_length=15,
        verbose_name='Número de Documento'
    )
    razon_social = models.CharField(max_length=200, verbose_name='Razón Social / Nombre')
    direccion = models.TextField(blank=True, verbose_name='Dirección')
    email = models.EmailField(blank=True, verbose_name='Correo Electrónico')

    class Meta:
        verbose_name = 'Cliente'
        verbose_name_plural = 'Clientes'
        unique_together = ('tipo_doc', 'num_doc')
        ordering = ['razon_social']

    def __str__(self):
        return f"{self.razon_social} ({self.tipo_doc}: {self.num_doc})"

    def clean(self):
        """Validación de número de documento según tipo."""
        super().clean()
        if self.tipo_doc == self.TipoDocumento.RUC:
            if not self.num_doc.isdigit() or len(self.num_doc) != 11:
                raise ValidationError({
                    'num_doc': 'El RUC debe contener exactamente 11 dígitos numéricos.'
                })
        elif self.tipo_doc == self.TipoDocumento.DNI:
            if not self.num_doc.isdigit() or len(self.num_doc) != 8:
                raise ValidationError({
                    'num_doc': 'El DNI debe contener exactamente 8 dígitos numéricos.'
                })

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)
