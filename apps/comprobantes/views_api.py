"""API Views para comprobantes electrónicos."""
from rest_framework import generics, status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.http import HttpResponse
from django.shortcuts import get_object_or_404

from .models import Comprobante
from .serializers import (
    ComprobanteListSerializer, ComprobanteDetailSerializer,
    EmitirComprobanteSerializer, NotaCreditoInputSerializer,
)
from dominio.comprobantes.excepciones import ComprobanteException
from .filters import ComprobanteFilter
from dominio.comprobantes.servicios import FacturaService, BoletaService, NotaCreditoService
from dominio.comprobantes.entidades import Cliente as DominioCliente, Empresa as DominioEmpresa
from infraestructura.persistencia.comprobante_repo import (
    DjangoComprobanteRepository, DjangoNumeracionRepository, DjangoProductoRepository
)
from infraestructura.sunat.cliente_ose import DjangoSunatClient
from .pdf_generator import generar_pdf_comprobante
from apps.clientes.models import Cliente
from apps.accounts.permissions import IsEmisor, IsEmisorOrContador


class FacturaCreateView(APIView):
    """POST /api/facturas/ — Emitir factura con cálculo de IGV y XML mock."""
    permission_classes = [IsAuthenticated, IsEmisor]

    def post(self, request):
        serializer = EmitirComprobanteSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        try:
            cliente_django = Cliente.objects.get(id=serializer.validated_data['cliente_id'])
            cliente_domain = DominioCliente(
                id=cliente_django.id, tipo_doc=cliente_django.tipo_doc,
                num_doc=cliente_django.num_doc, razon_social=cliente_django.razon_social,
                direccion=cliente_django.direccion, email=cliente_django.email
            )
            empresa_django = request.user.empresa
            empresa_domain = DominioEmpresa(
                id=empresa_django.id, ruc=empresa_django.ruc,
                razon_social=empresa_django.razon_social, nombre_comercial=empresa_django.nombre_comercial,
                direccion=empresa_django.direccion, regimen_tributario=empresa_django.regimen_tributario
            )
            
            comp_repo = DjangoComprobanteRepository()
            num_repo = DjangoNumeracionRepository()
            prod_repo = DjangoProductoRepository()
            sunat_client = DjangoSunatClient(comp_repo)

            comprobante = FacturaService.emitir(
                empresa=empresa_domain,
                cliente=cliente_domain,
                detalles_data=serializer.validated_data['detalles'],
                usuario_id=request.user.id,
                comp_repo=comp_repo, num_repo=num_repo,
                prod_repo=prod_repo, sunat_client=sunat_client
            )
            
            comp_django = Comprobante.objects.get(id=comprobante.id)
            return Response(
                ComprobanteDetailSerializer(comp_django).data,
                status=status.HTTP_201_CREATED
            )
        except ComprobanteException as e:
            return Response(
                {'error': str(e), 'codigo': getattr(e, 'codigo_error', 'ERR_DESCONOCIDO')},
                status=status.HTTP_400_BAD_REQUEST
            )
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class BoletaCreateView(APIView):
    """POST /api/boletas/ — Emitir boleta de venta."""
    permission_classes = [IsAuthenticated, IsEmisor]

    def post(self, request):
        serializer = EmitirComprobanteSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        try:
            cliente_django = Cliente.objects.get(id=serializer.validated_data['cliente_id'])
            cliente_domain = DominioCliente(
                id=cliente_django.id, tipo_doc=cliente_django.tipo_doc,
                num_doc=cliente_django.num_doc, razon_social=cliente_django.razon_social,
                direccion=cliente_django.direccion, email=cliente_django.email
            )
            empresa_django = request.user.empresa
            empresa_domain = DominioEmpresa(
                id=empresa_django.id, ruc=empresa_django.ruc,
                razon_social=empresa_django.razon_social, nombre_comercial=empresa_django.nombre_comercial,
                direccion=empresa_django.direccion, regimen_tributario=empresa_django.regimen_tributario
            )
            
            comp_repo = DjangoComprobanteRepository()
            num_repo = DjangoNumeracionRepository()
            prod_repo = DjangoProductoRepository()
            sunat_client = DjangoSunatClient(comp_repo)

            comprobante = BoletaService.emitir(
                empresa=empresa_domain,
                cliente=cliente_domain,
                detalles_data=serializer.validated_data['detalles'],
                usuario_id=request.user.id,
                comp_repo=comp_repo, num_repo=num_repo,
                prod_repo=prod_repo, sunat_client=sunat_client
            )
            
            comp_django = Comprobante.objects.get(id=comprobante.id)
            return Response(
                ComprobanteDetailSerializer(comp_django).data,
                status=status.HTTP_201_CREATED
            )
        except ComprobanteException as e:
            return Response(
                {'error': str(e), 'codigo': getattr(e, 'codigo_error', 'ERR_DESCONOCIDO')},
                status=status.HTTP_400_BAD_REQUEST
            )
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class NotaCreditoCreateView(APIView):
    """POST /api/notas-credito/ — Emitir nota de crédito."""
    permission_classes = [IsAuthenticated, IsEmisor]

    def post(self, request):
        serializer = NotaCreditoInputSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        try:
            empresa_django = request.user.empresa
            empresa_domain = DominioEmpresa(
                id=empresa_django.id, ruc=empresa_django.ruc,
                razon_social=empresa_django.razon_social, nombre_comercial=empresa_django.nombre_comercial,
                direccion=empresa_django.direccion, regimen_tributario=empresa_django.regimen_tributario
            )
            
            comp_repo = DjangoComprobanteRepository()
            num_repo = DjangoNumeracionRepository()
            sunat_client = DjangoSunatClient(comp_repo)
            
            comp_ref_domain = comp_repo.obtener_comprobante_por_id(serializer.validated_data['comprobante_referencia_id'])

            comprobante_nc, nota = NotaCreditoService.emitir(
                empresa=empresa_domain,
                comprobante_ref=comp_ref_domain,
                motivo=serializer.validated_data['motivo'],
                tipo_nota=serializer.validated_data['tipo_nota'],
                monto_afectado=serializer.validated_data['monto_afectado'],
                usuario_id=request.user.id,
                comp_repo=comp_repo, num_repo=num_repo,
                sunat_client=sunat_client
            )
            
            comp_django = Comprobante.objects.get(id=comprobante_nc.id)
            return Response(
                ComprobanteDetailSerializer(comp_django).data,
                status=status.HTTP_201_CREATED
            )
        except ComprobanteException as e:
            return Response(
                {'error': str(e), 'codigo': getattr(e, 'codigo_error', 'ERR_DESCONOCIDO')},
                status=status.HTTP_400_BAD_REQUEST
            )
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class ComprobanteListView(generics.ListAPIView):
    """GET /api/comprobantes/ — Listado con filtros."""
    serializer_class = ComprobanteListSerializer
    permission_classes = [IsAuthenticated, IsEmisorOrContador]
    filterset_class = ComprobanteFilter

    def get_queryset(self):
        qs = Comprobante.objects.select_related('cliente', 'empresa')
        if self.request.user.empresa:
            qs = qs.filter(empresa=self.request.user.empresa)
        if self.request.user.is_emisor:
            qs = qs.filter(creado_por=self.request.user)
        return qs


class ComprobanteDetailView(generics.RetrieveAPIView):
    """GET /api/comprobantes/{id}/ — Detalle del comprobante."""
    serializer_class = ComprobanteDetailSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Comprobante.objects.select_related('cliente', 'empresa').prefetch_related('detalles', 'logs_envio')


class ReenviarView(APIView):
    """POST /api/comprobantes/{id}/reenviar/ — Reenviar comprobante rechazado."""
    permission_classes = [IsAuthenticated, IsEmisor]

    def post(self, request, pk):
        comprobante = get_object_or_404(Comprobante, pk=pk)
        try:
            comp_repo = DjangoComprobanteRepository()
            sunat_client = DjangoSunatClient(comp_repo)
            comp_domain = comp_repo.obtener_comprobante_por_id(comprobante.id)
            sunat_client.enviar_comprobante(comp_domain)
            comprobante.refresh_from_db()
            return Response(ComprobanteDetailSerializer(comprobante).data)
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)


class ComprobantePDFView(APIView):
    """GET /api/comprobantes/{id}/pdf/ — Descargar PDF del comprobante."""
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        comprobante = get_object_or_404(
            Comprobante.objects.select_related('cliente', 'empresa').prefetch_related('detalles__producto'),
            pk=pk
        )
        pdf_buffer = generar_pdf_comprobante(comprobante)
        response = HttpResponse(pdf_buffer.getvalue(), content_type='application/pdf')
        response['Content-Disposition'] = f'inline; filename="{comprobante.serie_numero}.pdf"'
        return response
