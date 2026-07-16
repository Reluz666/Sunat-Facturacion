from typing import Protocol, List, Tuple, Optional
from decimal import Decimal
from .entidades import Comprobante, DetalleComprobante, NotaCredito, Cliente, Empresa, Producto

class IComprobanteRepository(Protocol):
    def guardar_comprobante_y_detalles(self, comprobante: Comprobante) -> Comprobante:
        """Guarda el comprobante y sus detalles asociados en la base de datos."""
        ...

    def actualizar_comprobante(self, comprobante: Comprobante, **kwargs) -> Comprobante:
        """Actualiza campos específicos del comprobante."""
        ...

    def guardar_nota_credito(self, nota: NotaCredito, comprobante: Comprobante) -> Tuple[Comprobante, NotaCredito]:
        """Guarda la nota de crédito y su comprobante asociado."""
        ...

    def obtener_comprobante_por_id(self, comprobante_id: int) -> Comprobante:
        """Recupera un comprobante por su ID."""
        ...


class INumeracionRepository(Protocol):
    def generar_correlativo(self, empresa_id: int, tipo_serie: str) -> Tuple[str, int]:
        """Genera y retorna de forma atómica (serie, numero) para el tipo especificado."""
        ...


class IProductoRepository(Protocol):
    def obtener_productos_por_ids(self, producto_ids: List[int]) -> List[Producto]:
        """Retorna una lista de productos dado sus IDs."""
        ...


class ISunatClient(Protocol):
    def enviar_comprobante(self, comprobante: Comprobante) -> None:
        """Envía el comprobante a SUNAT/OSE."""
        ...
        
    def generar_xml(self, comprobante: Comprobante) -> Tuple[bytes, str]:
        """Genera el XML firmado y su hash CPE. Retorna (xml_firmado, hash_cpe)."""
        ...
