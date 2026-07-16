"""
Tests de la API REST de comprobantes.
"""
import pytest
from decimal import Decimal
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework import status

from apps.accounts.models import CustomUser
from apps.empresa.models import Empresa, SerieComprobante
from apps.clientes.models import Cliente
from apps.productos.models import Producto
from apps.comprobantes.models import Comprobante


@pytest.mark.django_db
class TestComprobanteAPI(TestCase):
    """Tests de los endpoints API de comprobantes."""

    def setUp(self):
        self.empresa = Empresa.objects.create(
            ruc='20123456789', razon_social='API Test SAC', direccion='Lima'
        )
        SerieComprobante.objects.create(empresa=self.empresa, tipo='F', serie='F001', correlativo_actual=0)
        SerieComprobante.objects.create(empresa=self.empresa, tipo='B', serie='B001', correlativo_actual=0)
        SerieComprobante.objects.create(empresa=self.empresa, tipo='FC', serie='FC01', correlativo_actual=0)

        self.user = CustomUser.objects.create_user(
            username='emisor', password='test123', rol='EMISOR', empresa=self.empresa
        )
        self.cliente_ruc = Cliente.objects.create(
            tipo_doc='RUC', num_doc='20987654321', razon_social='Cliente API SAC'
        )
        self.cliente_dni = Cliente.objects.create(
            tipo_doc='DNI', num_doc='12345678', razon_social='Juan Test'
        )
        self.producto = Producto.objects.create(
            codigo='PROD001', descripcion='Producto Test',
            precio_unitario=Decimal('100.00'), afecto_igv=True
        )

        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

    def test_emitir_factura(self):
        """POST /api/facturas/ — Emisión exitosa de factura."""
        data = {
            'cliente_id': self.cliente_ruc.id,
            'detalles': [{'producto_id': self.producto.id, 'cantidad': 5, 'precio_unitario': 100, 'descuento': 0}],
        }
        response = self.client.post('/api/facturas/', data, format='json')
        if response.status_code != status.HTTP_201_CREATED:
            print(response.json())
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['serie'], 'F001')
        self.assertEqual(Decimal(response.data['subtotal']), Decimal('500.00'))
        self.assertEqual(Decimal(response.data['igv']), Decimal('90.00'))

    def test_emitir_factura_requiere_ruc(self):
        """POST /api/facturas/ — Falla si cliente tiene DNI."""
        data = {
            'cliente_id': self.cliente_dni.id,
            'detalles': [{'producto_id': self.producto.id, 'cantidad': 1, 'precio_unitario': 100}],
        }
        response = self.client.post('/api/facturas/', data, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_emitir_boleta(self):
        """POST /api/boletas/ — Emisión exitosa de boleta con DNI."""
        data = {
            'cliente_id': self.cliente_dni.id,
            'detalles': [{'producto_id': self.producto.id, 'cantidad': 2, 'precio_unitario': 50}],
        }
        response = self.client.post('/api/boletas/', data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_listar_comprobantes(self):
        """GET /api/comprobantes/ — Lista con filtros."""
        response = self.client.get('/api/comprobantes/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_acceso_no_autenticado(self):
        """Endpoints requieren autenticación."""
        client = APIClient()
        response = client.get('/api/comprobantes/')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


@pytest.mark.django_db
class TestPermisosAPI(TestCase):
    """Tests de permisos por rol."""

    def setUp(self):
        self.empresa = Empresa.objects.create(
            ruc='20123456789', razon_social='Perm Test SAC', direccion='Lima'
        )
        self.user_emisor = CustomUser.objects.create_user(
            username='emisor_perm', password='test123', rol='EMISOR', empresa=self.empresa
        )
        self.user_contador = CustomUser.objects.create_user(
            username='contador_perm', password='test123', rol='CONTADOR', empresa=self.empresa
        )

    def test_emisor_puede_listar(self):
        client = APIClient()
        client.force_authenticate(user=self.user_emisor)
        response = client.get('/api/comprobantes/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_contador_puede_listar(self):
        client = APIClient()
        client.force_authenticate(user=self.user_contador)
        response = client.get('/api/comprobantes/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
