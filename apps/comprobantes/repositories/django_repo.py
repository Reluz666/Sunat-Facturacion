from django.db import transaction
from apps.comprobantes.models import Comprobante, DetalleComprobante, NotaCredito
from apps.comprobantes.repositories.base import IComprobanteRepository

class DjangoComprobanteRepository(IComprobanteRepository):
    """
    Implementación del repositorio de comprobantes usando Django ORM.
    """

    @transaction.atomic
    def guardar_comprobante_y_detalles(self, comprobante_data, detalles_data):
        comprobante = Comprobante.objects.create(**comprobante_data)

        detalles = []
        for linea in detalles_data:
            detalles.append(DetalleComprobante(
                comprobante=comprobante,
                **linea
            ))
        DetalleComprobante.objects.bulk_create(detalles)
        return comprobante

    def actualizar_comprobante(self, comprobante, **kwargs):
        for key, value in kwargs.items():
            setattr(comprobante, key, value)
        update_fields = list(kwargs.keys())
        if 'actualizado_en' not in update_fields:
            update_fields.append('actualizado_en')
        comprobante.save(update_fields=update_fields)
        return comprobante

    @transaction.atomic
    def guardar_nota_credito(self, nota_credito_data, comprobante_data, detalles_data):
        comprobante_nc = Comprobante.objects.create(**comprobante_data)

        nota_credito = NotaCredito.objects.create(
            comprobante_nota=comprobante_nc,
            **nota_credito_data
        )

        detalles = []
        for linea in detalles_data:
            detalles.append(DetalleComprobante(
                comprobante=comprobante_nc,
                **linea
            ))
        DetalleComprobante.objects.bulk_create(detalles)
        
        return comprobante_nc, nota_credito
