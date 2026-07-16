from typing import Tuple, List, Optional
from django.db import transaction
from apps.comprobantes.models import Comprobante as DjangoComprobante
from apps.comprobantes.models import DetalleComprobante as DjangoDetalle
from apps.comprobantes.models import NotaCredito as DjangoNotaCredito
from apps.empresa.models import SerieComprobante as DjangoSerie
from apps.productos.models import Producto as DjangoProducto

from dominio.comprobantes.entidades import Comprobante, DetalleComprobante, NotaCredito, Producto, Cliente, Empresa
from dominio.comprobantes.puertos import IComprobanteRepository, INumeracionRepository, IProductoRepository
from dominio.comprobantes.excepciones import GeneracionCorrelativoException


class DjangoComprobanteRepository(IComprobanteRepository):
    """Adaptador de persistencia para comprobantes usando Django ORM."""

    @transaction.atomic
    def guardar_comprobante_y_detalles(self, comprobante: Comprobante) -> Comprobante:
        django_comp = DjangoComprobante.objects.create(
            serie=comprobante.serie,
            numero=comprobante.numero,
            tipo=comprobante.tipo,
            cliente_id=comprobante.cliente_id,
            empresa_id=comprobante.empresa_id,
            creado_por_id=comprobante.creado_por_id,
            subtotal=comprobante.subtotal,
            total_inafecto=comprobante.total_inafecto,
            igv=comprobante.igv,
            total=comprobante.total,
            estado=comprobante.estado,
        )
        
        comprobante.id = django_comp.id

        django_detalles = []
        for det in comprobante.detalles:
            django_detalles.append(DjangoDetalle(
                comprobante=django_comp,
                producto_id=det.producto_id,
                cantidad=det.cantidad,
                precio_unitario=det.precio_unitario,
                descuento=det.descuento,
                igv_linea=det.igv_linea,
                subtotal=det.subtotal
            ))
        DjangoDetalle.objects.bulk_create(django_detalles)

        return comprobante

    def actualizar_comprobante(self, comprobante: Comprobante, **kwargs) -> Comprobante:
        if not comprobante.id:
            raise ValueError("El comprobante no tiene ID asignado.")
            
        update_fields = list(kwargs.keys())
        if 'actualizado_en' not in update_fields:
            update_fields.append('actualizado_en')
            
        DjangoComprobante.objects.filter(id=comprobante.id).update(**kwargs)
        
        for k, v in kwargs.items():
            if hasattr(comprobante, k):
                setattr(comprobante, k, v)
                
        return comprobante

    @transaction.atomic
    def guardar_nota_credito(self, nota: NotaCredito, comprobante: Comprobante) -> Tuple[Comprobante, NotaCredito]:
        # Guardar el comprobante primero
        django_comp = DjangoComprobante.objects.create(
            serie=comprobante.serie,
            numero=comprobante.numero,
            tipo=comprobante.tipo,
            cliente_id=comprobante.cliente_id,
            empresa_id=comprobante.empresa_id,
            creado_por_id=comprobante.creado_por_id,
            subtotal=comprobante.subtotal,
            total_inafecto=comprobante.total_inafecto,
            igv=comprobante.igv,
            total=comprobante.total,
            estado=comprobante.estado,
        )
        comprobante.id = django_comp.id
        nota.comprobante_nota_id = django_comp.id

        # Guardar la nota de crédito
        DjangoNotaCredito.objects.create(
            comprobante_nota_id=nota.comprobante_nota_id,
            comprobante_referencia_id=nota.comprobante_referencia_id,
            motivo=nota.motivo,
            tipo_nota=nota.tipo_nota,
            monto_afectado=nota.monto_afectado,
        )

        # Guardar detalles
        django_detalles = []
        for det in comprobante.detalles:
            django_detalles.append(DjangoDetalle(
                comprobante=django_comp,
                producto_id=det.producto_id,
                cantidad=det.cantidad,
                precio_unitario=det.precio_unitario,
                descuento=det.descuento,
                igv_linea=det.igv_linea,
                subtotal=det.subtotal
            ))
        DjangoDetalle.objects.bulk_create(django_detalles)

        return comprobante, nota

    def obtener_comprobante_por_id(self, comprobante_id: int) -> Comprobante:
        django_comp = DjangoComprobante.objects.select_related('cliente', 'empresa').prefetch_related('detalles__producto').get(id=comprobante_id)
        
        detalles = []
        for det in django_comp.detalles.all():
            detalles.append(DetalleComprobante(
                producto_id=det.producto_id,
                cantidad=det.cantidad,
                precio_unitario=det.precio_unitario,
                descuento=det.descuento,
                igv_linea=det.igv_linea,
                subtotal=det.subtotal,
                producto=Producto(
                    id=det.producto.id,
                    codigo=det.producto.codigo,
                    descripcion=det.producto.descripcion,
                    unidad_medida=det.producto.unidad_medida,
                    precio_unitario=det.producto.precio_unitario,
                    afecto_igv=det.producto.afecto_igv
                )
            ))
            
        comp = Comprobante(
            id=django_comp.id,
            serie=django_comp.serie,
            numero=django_comp.numero,
            tipo=django_comp.tipo,
            cliente_id=django_comp.cliente_id,
            empresa_id=django_comp.empresa_id,
            creado_por_id=django_comp.creado_por_id,
            subtotal=django_comp.subtotal,
            total_inafecto=django_comp.total_inafecto,
            igv=django_comp.igv,
            total=django_comp.total,
            estado=django_comp.estado,
            detalles=detalles,
            xml_firmado=django_comp.xml_firmado,
            hash_cpe=django_comp.hash_cpe,
            cliente=Cliente(
                id=django_comp.cliente.id,
                tipo_doc=django_comp.cliente.tipo_doc,
                num_doc=django_comp.cliente.num_doc,
                razon_social=django_comp.cliente.razon_social,
                direccion=django_comp.cliente.direccion,
                email=django_comp.cliente.email
            ) if django_comp.cliente else None,
            empresa=Empresa(
                id=django_comp.empresa.id,
                ruc=django_comp.empresa.ruc,
                razon_social=django_comp.empresa.razon_social,
                nombre_comercial=django_comp.empresa.nombre_comercial,
                direccion=django_comp.empresa.direccion,
                regimen_tributario=django_comp.empresa.regimen_tributario
            ) if django_comp.empresa else None,
            fecha_emision=django_comp.creado_en
        )
        return comp


class DjangoNumeracionRepository(INumeracionRepository):
    @transaction.atomic
    def generar_correlativo(self, empresa_id: int, tipo_serie: str) -> Tuple[str, int]:
        db_tipo_map = {
            'FACTURA': 'F',
            'BOLETA': 'B',
            'NOTA_CREDITO': 'FC',
            'NOTA_CREDITO_BOLETA': 'BC',
        }
        db_tipo = db_tipo_map.get(tipo_serie, tipo_serie)
        
        serie = (
            DjangoSerie.objects
            .select_for_update()
            .filter(empresa_id=empresa_id, tipo=db_tipo)
            .first()
        )
        if not serie:
            raise GeneracionCorrelativoException(
                f'No existe una serie configurada para {tipo_serie} en la empresa {empresa_id}.'
            )
        numero = serie.siguiente_correlativo()
        return serie.serie, numero


class DjangoProductoRepository(IProductoRepository):
    def obtener_productos_por_ids(self, producto_ids: List[int]) -> List[Producto]:
        django_productos = DjangoProducto.objects.filter(id__in=producto_ids)
        productos = []
        for dp in django_productos:
            productos.append(Producto(
                id=dp.id,
                codigo=dp.codigo,
                descripcion=dp.descripcion,
                unidad_medida=dp.unidad_medida,
                precio_unitario=dp.precio_unitario,
                afecto_igv=dp.afecto_igv
            ))
        return productos
