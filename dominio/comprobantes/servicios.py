from decimal import Decimal, ROUND_HALF_UP
from typing import List, Dict, Any, Tuple, Optional
from .entidades import Comprobante, DetalleComprobante, Cliente, Empresa, Producto, NotaCredito
from .excepciones import ValidacionClienteException, TransicionEstadoException, ComprobanteException
from .puertos import IComprobanteRepository, INumeracionRepository, IProductoRepository, ISunatClient

IGV_RATE = Decimal('0.18')
QUANTIZE_2 = Decimal('0.01')


class TributaryEngine:
    """Motor de cálculos tributarios puro."""

    @staticmethod
    def calcular_linea(cantidad: Decimal, precio_unitario: Decimal, descuento_pct: Decimal, afecto_igv: bool) -> Dict[str, Decimal]:
        cantidad = Decimal(str(cantidad))
        precio_unitario = Decimal(str(precio_unitario))
        descuento_pct = Decimal(str(descuento_pct))

        valor_venta = (cantidad * precio_unitario).quantize(QUANTIZE_2, rounding=ROUND_HALF_UP)
        descuento_monto = (valor_venta * descuento_pct / Decimal('100')).quantize(QUANTIZE_2, rounding=ROUND_HALF_UP)
        subtotal = (valor_venta - descuento_monto).quantize(QUANTIZE_2, rounding=ROUND_HALF_UP)

        if afecto_igv:
            igv_linea = (subtotal * IGV_RATE).quantize(QUANTIZE_2, rounding=ROUND_HALF_UP)
        else:
            igv_linea = Decimal('0.00')

        total_linea = subtotal + igv_linea

        return {
            'valor_venta': valor_venta,
            'descuento_monto': descuento_monto,
            'subtotal': subtotal,
            'igv_linea': igv_linea,
            'total_linea': total_linea,
        }

    @staticmethod
    def calcular_totales(detalles_data: List[Dict[str, Any]], productos_map: Dict[int, Producto]) -> Dict[str, Any]:
        base_imponible = Decimal('0.00')
        total_inafecto = Decimal('0.00')
        total_igv = Decimal('0.00')
        lineas_calculadas = []

        for detalle in detalles_data:
            producto = productos_map[detalle['producto_id']]
            calculos = TributaryEngine.calcular_linea(
                cantidad=detalle['cantidad'],
                precio_unitario=detalle['precio_unitario'],
                descuento_pct=detalle.get('descuento', Decimal('0')),
                afecto_igv=producto.afecto_igv,
            )

            if producto.afecto_igv:
                base_imponible += calculos['subtotal']
            else:
                total_inafecto += calculos['subtotal']

            total_igv += calculos['igv_linea']

            lineas_calculadas.append({
                'producto_id': detalle['producto_id'],
                'cantidad': Decimal(str(detalle['cantidad'])),
                'precio_unitario': Decimal(str(detalle['precio_unitario'])),
                'descuento': Decimal(str(detalle.get('descuento', '0'))),
                'igv_linea': calculos['igv_linea'],
                'subtotal': calculos['subtotal'],
            })

        total = base_imponible + total_igv + total_inafecto

        return {
            'subtotal': base_imponible.quantize(QUANTIZE_2),
            'total_inafecto': total_inafecto.quantize(QUANTIZE_2),
            'igv': total_igv.quantize(QUANTIZE_2),
            'total': total.quantize(QUANTIZE_2),
            'lineas': lineas_calculadas,
        }


class NumeracionService:
    @staticmethod
    def generar_correlativo(
        empresa_id: int, 
        tipo_comprobante: str, 
        comprobante_ref: Optional[Comprobante], 
        num_repo: INumeracionRepository
    ) -> Tuple[str, int]:
        
        tipo_map = {
            'FACTURA': 'FACTURA',
            'BOLETA': 'BOLETA',
        }
        
        if tipo_comprobante == 'NOTA_CREDITO':
            if comprobante_ref and comprobante_ref.tipo == 'BOLETA':
                serie_tipo = 'NOTA_CREDITO_BOLETA'
            else:
                serie_tipo = 'NOTA_CREDITO'
        else:
            serie_tipo = tipo_map[tipo_comprobante]

        return num_repo.generar_correlativo(empresa_id, serie_tipo)


class ComprobanteBaseService:
    @staticmethod
    def _crear_comprobante_y_detalles(
        empresa: Empresa, 
        cliente: Cliente, 
        tipo: str, 
        detalles_data: List[Dict[str, Any]], 
        usuario_id: int, 
        auto_enviar: bool,
        comp_repo: IComprobanteRepository,
        num_repo: INumeracionRepository,
        prod_repo: IProductoRepository,
        sunat_client: ISunatClient
    ) -> Comprobante:
        
        # 1. Generar número
        serie, numero = NumeracionService.generar_correlativo(empresa.id, tipo, None, num_repo)

        # 2. Obtener productos y calcular totales
        producto_ids = [d['producto_id'] for d in detalles_data]
        productos = prod_repo.obtener_productos_por_ids(producto_ids)
        productos_map = {p.id: p for p in productos}

        if len(productos_map) != len(producto_ids):
            raise ComprobanteException('Uno o más productos no existen.')

        totales = TributaryEngine.calcular_totales(detalles_data, productos_map)

        # 3. Crear entidad Comprobante
        detalles_obj = [
            DetalleComprobante(
                producto_id=l['producto_id'],
                cantidad=l['cantidad'],
                precio_unitario=l['precio_unitario'],
                descuento=l['descuento'],
                igv_linea=l['igv_linea'],
                subtotal=l['subtotal'],
                producto=productos_map[l['producto_id']]
            ) for l in totales['lineas']
        ]

        comprobante = Comprobante(
            serie=serie,
            numero=numero,
            tipo=tipo,
            cliente_id=cliente.id,
            empresa_id=empresa.id,
            creado_por_id=usuario_id,
            subtotal=totales['subtotal'],
            total_inafecto=totales['total_inafecto'],
            igv=totales['igv'],
            total=totales['total'],
            estado='BORRADOR',
            detalles=detalles_obj,
            cliente=cliente,
            empresa=empresa
        )

        # 4. Guardar en repositorio
        comprobante = comp_repo.guardar_comprobante_y_detalles(comprobante)

        # 5. Generar XML y hash
        xml_content, hash_cpe = sunat_client.generar_xml(comprobante)
        
        comprobante.xml_firmado = xml_content
        comprobante.hash_cpe = hash_cpe
        comprobante.estado = 'EMITIDO'
        
        comprobante = comp_repo.actualizar_comprobante(
            comprobante, 
            xml_firmado=xml_content, 
            hash_cpe=hash_cpe, 
            estado='EMITIDO'
        )

        # 6. Enviar a SUNAT
        if auto_enviar:
            sunat_client.enviar_comprobante(comprobante)

        return comprobante


class FacturaService:
    @staticmethod
    def validar_cliente(cliente: Cliente):
        if cliente.tipo_doc != 'RUC':
            raise ValidacionClienteException(
                'Para emitir una Factura, el cliente debe tener RUC (11 dígitos).'
            )

    @staticmethod
    def emitir(
        empresa: Empresa, 
        cliente: Cliente, 
        detalles_data: List[Dict[str, Any]], 
        usuario_id: int, 
        comp_repo: IComprobanteRepository,
        num_repo: INumeracionRepository,
        prod_repo: IProductoRepository,
        sunat_client: ISunatClient,
        auto_enviar: bool = True
    ) -> Comprobante:
        FacturaService.validar_cliente(cliente)
        return ComprobanteBaseService._crear_comprobante_y_detalles(
            empresa, cliente, 'FACTURA', detalles_data, usuario_id, auto_enviar,
            comp_repo, num_repo, prod_repo, sunat_client
        )


class BoletaService:
    @staticmethod
    def validar_cliente(cliente: Cliente):
        if cliente.tipo_doc not in ['DNI', 'CE', 'RUC']:
            raise ValidacionClienteException(
                'Para emitir una Boleta, el cliente debe tener DNI, CE o RUC.'
            )

    @staticmethod
    def emitir(
        empresa: Empresa, 
        cliente: Cliente, 
        detalles_data: List[Dict[str, Any]], 
        usuario_id: int, 
        comp_repo: IComprobanteRepository,
        num_repo: INumeracionRepository,
        prod_repo: IProductoRepository,
        sunat_client: ISunatClient,
        auto_enviar: bool = True
    ) -> Comprobante:
        BoletaService.validar_cliente(cliente)
        return ComprobanteBaseService._crear_comprobante_y_detalles(
            empresa, cliente, 'BOLETA', detalles_data, usuario_id, auto_enviar,
            comp_repo, num_repo, prod_repo, sunat_client
        )


class NotaCreditoService:
    @staticmethod
    def emitir(
        empresa: Empresa, 
        comprobante_ref: Comprobante, 
        motivo: str, 
        tipo_nota: str, 
        monto_afectado: Decimal, 
        usuario_id: int, 
        comp_repo: IComprobanteRepository,
        num_repo: INumeracionRepository,
        sunat_client: ISunatClient
    ) -> Tuple[Comprobante, NotaCredito]:
        
        monto_afectado = Decimal(str(monto_afectado))

        if monto_afectado > comprobante_ref.total:
            raise ComprobanteException(
                f'El monto afectado (S/.{monto_afectado}) no puede superar '
                f'el total del comprobante original (S/.{comprobante_ref.total}).'
            )

        if comprobante_ref.estado not in ['ACEPTADO', 'EMITIDO']:
            raise TransicionEstadoException(
                'Solo se pueden emitir notas de crédito para comprobantes ACEPTADOS o EMITIDOS.'
            )

        serie, numero = NumeracionService.generar_correlativo(
            empresa.id, 
            'NOTA_CREDITO', 
            comprobante_ref=comprobante_ref,
            num_repo=num_repo
        )

        if comprobante_ref.subtotal > 0:
            proporcion = monto_afectado / (comprobante_ref.subtotal + comprobante_ref.total_inafecto + comprobante_ref.igv)
        else:
            proporcion = Decimal('1.00')

        igv_nc = (comprobante_ref.igv * proporcion).quantize(QUANTIZE_2, rounding=ROUND_HALF_UP)
        subtotal_nc = (monto_afectado - igv_nc).quantize(QUANTIZE_2, rounding=ROUND_HALF_UP)

        detalles_nuevos = []
        for det_ref in comprobante_ref.detalles:
            nueva_cantidad = det_ref.cantidad * proporcion
            nuevo_igv_linea = (det_ref.igv_linea * proporcion).quantize(QUANTIZE_2, rounding=ROUND_HALF_UP)
            nuevo_subtotal = (det_ref.subtotal * proporcion).quantize(QUANTIZE_2, rounding=ROUND_HALF_UP)
            
            detalles_nuevos.append(
                DetalleComprobante(
                    producto_id=det_ref.producto_id,
                    cantidad=nueva_cantidad.quantize(Decimal('.01'), rounding=ROUND_HALF_UP),
                    precio_unitario=det_ref.precio_unitario,
                    descuento=det_ref.descuento,
                    igv_linea=nuevo_igv_linea,
                    subtotal=nuevo_subtotal,
                    producto=det_ref.producto
                )
            )

        comprobante_nc = Comprobante(
            serie=serie,
            numero=numero,
            tipo='NOTA_CREDITO',
            cliente_id=comprobante_ref.cliente_id,
            empresa_id=empresa.id,
            creado_por_id=usuario_id,
            subtotal=subtotal_nc,
            igv=igv_nc,
            total=monto_afectado,
            estado='EMITIDO',
            detalles=detalles_nuevos,
            cliente=comprobante_ref.cliente,
            empresa=empresa
        )

        nota_credito = NotaCredito(
            comprobante_nota_id=0, # Asignado tras guardar
            comprobante_referencia_id=comprobante_ref.id,
            motivo=motivo,
            tipo_nota=tipo_nota,
            monto_afectado=monto_afectado,
        )

        comprobante_nc, nota_credito = comp_repo.guardar_nota_credito(nota_credito, comprobante_nc)

        xml_content, hash_cpe = sunat_client.generar_xml(comprobante_nc)
        comprobante_nc = comp_repo.actualizar_comprobante(
            comprobante_nc,
            xml_firmado=xml_content,
            hash_cpe=hash_cpe
        )

        sunat_client.enviar_comprobante(comprobante_nc)

        return comprobante_nc, nota_credito
