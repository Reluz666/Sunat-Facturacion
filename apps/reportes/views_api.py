"""API View para reportes: Libro de Ventas por período."""
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.db.models import Sum, Count, Q
from apps.comprobantes.models import Comprobante
from apps.accounts.permissions import IsEmisorOrContador


class LibroVentasAPIView(APIView):
    """GET /api/reportes/ventas-por-periodo/?mes=&anio="""
    permission_classes = [IsAuthenticated, IsEmisorOrContador]

    def get(self, request):
        mes = request.query_params.get('mes')
        anio = request.query_params.get('anio')

        qs = Comprobante.objects.select_related('cliente').exclude(
            tipo=Comprobante.TipoComprobante.NOTA_CREDITO
        )

        if request.user.empresa:
            qs = qs.filter(empresa=request.user.empresa)
        if request.user.is_emisor:
            qs = qs.filter(creado_por=request.user)

        if mes and anio:
            qs = qs.filter(fecha_emision__month=int(mes), fecha_emision__year=int(anio))
        elif anio:
            qs = qs.filter(fecha_emision__year=int(anio))

        comprobantes = qs.order_by('fecha_emision', 'serie', 'numero')

        # Totales
        totales = qs.aggregate(
            total_base=Sum('subtotal'),
            total_igv=Sum('igv'),
            total_general=Sum('total'),
            cantidad=Count('id'),
            aceptados=Count('id', filter=Q(estado='ACEPTADO')),
            rechazados=Count('id', filter=Q(estado='RECHAZADO')),
            enviados=Count('id', filter=Q(estado='ENVIADO')),
        )

        data = {
            'comprobantes': [
                {
                    'id': c.id,
                    'fecha': str(c.fecha_emision),
                    'serie_numero': c.serie_numero,
                    'tipo': c.get_tipo_display(),
                    'cliente': c.cliente.razon_social,
                    'cliente_doc': c.cliente.num_doc,
                    'base_imponible': str(c.subtotal),
                    'igv': str(c.igv),
                    'total': str(c.total),
                    'estado': c.estado,
                }
                for c in comprobantes
            ],
            'totales': {
                'base_imponible': str(totales['total_base'] or 0),
                'igv': str(totales['total_igv'] or 0),
                'total': str(totales['total_general'] or 0),
                'cantidad': totales['cantidad'],
                'aceptados': totales['aceptados'],
                'rechazados': totales['rechazados'],
                'enviados': totales['enviados'],
            }
        }
        return Response(data)
