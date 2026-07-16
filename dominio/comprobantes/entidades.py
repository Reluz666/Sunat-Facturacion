from dataclasses import dataclass, field
from decimal import Decimal
from typing import List, Optional
from datetime import datetime

@dataclass
class Empresa:
    id: Optional[int]
    ruc: str
    razon_social: str
    nombre_comercial: str = ""
    direccion: str = ""
    regimen_tributario: str = "GENERAL"


@dataclass
class Cliente:
    id: Optional[int]
    tipo_doc: str
    num_doc: str
    razon_social: str
    direccion: str = ""
    email: str = ""


@dataclass
class Producto:
    id: Optional[int]
    codigo: str
    descripcion: str
    unidad_medida: str = 'NIU'
    precio_unitario: Decimal = field(default_factory=lambda: Decimal('0.00'))
    afecto_igv: bool = True


@dataclass
class DetalleComprobante:
    producto_id: int
    cantidad: Decimal
    precio_unitario: Decimal
    descuento: Decimal = Decimal('0.00')
    igv_linea: Decimal = Decimal('0.00')
    subtotal: Decimal = Decimal('0.00')
    producto: Optional[Producto] = None


@dataclass
class Comprobante:
    id: Optional[int] = None
    serie: str = ""
    numero: int = 0
    tipo: str = "FACTURA"
    cliente_id: Optional[int] = None
    empresa_id: Optional[int] = None
    creado_por_id: Optional[int] = None
    subtotal: Decimal = Decimal('0.00')
    total_inafecto: Decimal = Decimal('0.00')
    igv: Decimal = Decimal('0.00')
    total: Decimal = Decimal('0.00')
    estado: str = "BORRADOR"
    detalles: List[DetalleComprobante] = field(default_factory=list)
    xml_firmado: Optional[bytes] = None
    hash_cpe: str = ""
    cliente: Optional[Cliente] = None
    empresa: Optional[Empresa] = None
    fecha_emision: datetime = field(default_factory=datetime.now)
    
    @property
    def serie_numero(self) -> str:
        return f"{self.serie}-{self.numero:08d}"


@dataclass
class NotaCredito:
    comprobante_nota_id: int
    comprobante_referencia_id: int
    motivo: str
    tipo_nota: str
    monto_afectado: Decimal
