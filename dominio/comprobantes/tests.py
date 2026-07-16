import unittest
from decimal import Decimal
from typing import Tuple, List, Optional
from datetime import datetime

from dominio.comprobantes.entidades import (
    Comprobante, DetalleComprobante, Cliente, Empresa, Producto, NotaCredito
)
from dominio.comprobantes.servicios import FacturaService, BoletaService, NotaCreditoService
from dominio.comprobantes.excepciones import (
    ValidacionClienteException, ComprobanteException
)
from dominio.comprobantes.puertos import (
    IComprobanteRepository, INumeracionRepository, IProductoRepository, ISunatClient
)

class MockComprobanteRepository(IComprobanteRepository):
    def __init__(self):
        self.comprobantes = {}
        
    def guardar_comprobante_y_detalles(self, comprobante: Comprobante) -> Comprobante:
        comprobante.id = len(self.comprobantes) + 1
        self.comprobantes[comprobante.id] = comprobante
        return comprobante

    def guardar_nota_credito(self, nota: NotaCredito, comprobante: Comprobante) -> Tuple[Comprobante, NotaCredito]:
        comprobante.id = len(self.comprobantes) + 1
        self.comprobantes[comprobante.id] = comprobante
        nota.id = len(self.comprobantes) + 1
        return comprobante, nota

    def actualizar_comprobante(self, comprobante: Comprobante, **kwargs) -> Comprobante:
        self.comprobantes[comprobante.id] = comprobante
        return comprobante

    def obtener_comprobante_por_id(self, comprobante_id: int) -> Comprobante:
        return self.comprobantes.get(comprobante_id)

class MockNumeracionRepository(INumeracionRepository):
    def generar_correlativo(self, empresa_id: int, tipo_serie: str) -> Tuple[str, int]:
        series = {
            'FACTURA': 'F001',
            'BOLETA': 'B001',
            'NOTA_CREDITO': 'FC01',
            'NOTA_CREDITO_BOLETA': 'BC01',
        }
        return series.get(tipo_serie, 'X001'), 1

class MockProductoRepository(IProductoRepository):
    def obtener_productos_por_ids(self, producto_ids: List[int]) -> List[Producto]:
        return [
            Producto(id=pid, codigo=f'P{pid}', descripcion='Prod', precio_unitario=Decimal('100.00'), afecto_igv=True)
            for pid in producto_ids
        ]

class MockSunatClient(ISunatClient):
    def generar_xml(self, comprobante: Comprobante) -> Tuple[bytes, str]:
        return b'<xml></xml>', 'hash123'

    def enviar_comprobante(self, comprobante: Comprobante) -> None:
        pass


class TestDomainServices(unittest.TestCase):
    def setUp(self):
        self.empresa = Empresa(id=1, ruc='20123456789', razon_social='Test SAC', nombre_comercial='Test', direccion='Lima', regimen_tributario='GENERAL')
        self.cliente = Cliente(id=1, tipo_doc='RUC', num_doc='20987654321', razon_social='Cliente Test', direccion='Lima', email='test@test.com')
        self.cliente_dni = Cliente(id=2, tipo_doc='DNI', num_doc='12345678', razon_social='Juan', direccion='Lima', email='juan@test.com')
        
        self.comp_repo = MockComprobanteRepository()
        self.num_repo = MockNumeracionRepository()
        self.prod_repo = MockProductoRepository()
        self.sunat_client = MockSunatClient()

    def test_emitir_factura_exito(self):
        detalles_data = [{'producto_id': 1, 'cantidad': Decimal('5'), 'precio_unitario': Decimal('100.00'), 'descuento': Decimal('0')}]
        comprobante = FacturaService.emitir(
            empresa=self.empresa, cliente=self.cliente, detalles_data=detalles_data, usuario_id=1,
            comp_repo=self.comp_repo, num_repo=self.num_repo, prod_repo=self.prod_repo, sunat_client=self.sunat_client
        )
        self.assertEqual(comprobante.tipo, 'FACTURA')
        self.assertEqual(comprobante.serie, 'F001')
        self.assertEqual(comprobante.numero, 1)
        self.assertEqual(comprobante.subtotal, Decimal('500.00'))
        self.assertEqual(comprobante.igv, Decimal('90.00'))
        self.assertEqual(comprobante.total, Decimal('590.00'))

    def test_emitir_factura_con_dni_falla(self):
        detalles_data = [{'producto_id': 1, 'cantidad': Decimal('5'), 'precio_unitario': Decimal('100.00'), 'descuento': Decimal('0')}]
        with self.assertRaises(ValidacionClienteException):
            FacturaService.emitir(
                empresa=self.empresa, cliente=self.cliente_dni, detalles_data=detalles_data, usuario_id=1,
                comp_repo=self.comp_repo, num_repo=self.num_repo, prod_repo=self.prod_repo, sunat_client=self.sunat_client
            )

    def test_emitir_boleta_exito(self):
        detalles_data = [{'producto_id': 1, 'cantidad': Decimal('2'), 'precio_unitario': Decimal('100.00'), 'descuento': Decimal('0')}]
        comprobante = BoletaService.emitir(
            empresa=self.empresa, cliente=self.cliente_dni, detalles_data=detalles_data, usuario_id=1,
            comp_repo=self.comp_repo, num_repo=self.num_repo, prod_repo=self.prod_repo, sunat_client=self.sunat_client
        )
        self.assertEqual(comprobante.tipo, 'BOLETA')
        self.assertEqual(comprobante.serie, 'B001')
        self.assertEqual(comprobante.total, Decimal('236.00'))
