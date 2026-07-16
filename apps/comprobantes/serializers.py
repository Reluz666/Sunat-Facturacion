"""Serializers para la API REST de comprobantes electrónicos."""
from rest_framework import serializers
from decimal import Decimal
from .models import Comprobante, DetalleComprobante, NotaCredito, LogEnvioSUNAT
from apps.clientes.models import Cliente
from apps.productos.models import Producto


class DetalleComprobanteSerializer(serializers.ModelSerializer):
    producto_descripcion = serializers.CharField(source='producto.descripcion', read_only=True)

    class Meta:
        model = DetalleComprobante
        fields = ['id', 'producto', 'producto_descripcion', 'cantidad',
                  'precio_unitario', 'descuento', 'igv_linea', 'subtotal']
        read_only_fields = ['igv_linea', 'subtotal']


class LogEnvioSerializer(serializers.ModelSerializer):
    class Meta:
        model = LogEnvioSUNAT
        fields = ['id', 'fecha_envio', 'estado_respuesta', 'codigo_respuesta', 'descripcion']


class ComprobanteListSerializer(serializers.ModelSerializer):
    cliente_nombre = serializers.CharField(source='cliente.razon_social', read_only=True)
    cliente_doc = serializers.CharField(source='cliente.num_doc', read_only=True)
    serie_numero = serializers.CharField(read_only=True)
    tipo_display = serializers.CharField(source='get_tipo_display', read_only=True)
    estado_display = serializers.CharField(source='get_estado_display', read_only=True)

    class Meta:
        model = Comprobante
        fields = ['id', 'serie', 'numero', 'serie_numero', 'tipo', 'tipo_display',
                  'fecha_emision', 'cliente', 'cliente_nombre', 'cliente_doc',
                  'subtotal', 'igv', 'total', 'estado', 'estado_display']


class ComprobanteDetailSerializer(serializers.ModelSerializer):
    detalles = DetalleComprobanteSerializer(many=True, read_only=True)
    logs_envio = LogEnvioSerializer(many=True, read_only=True)
    cliente_nombre = serializers.CharField(source='cliente.razon_social', read_only=True)
    serie_numero = serializers.CharField(read_only=True)

    class Meta:
        model = Comprobante
        fields = ['id', 'serie', 'numero', 'serie_numero', 'tipo', 'fecha_emision',
                  'cliente', 'cliente_nombre', 'empresa', 'subtotal', 'total_inafecto',
                  'igv', 'total', 'estado', 'xml_firmado', 'hash_cpe',
                  'detalles', 'logs_envio', 'creado_en']


class DetalleInputSerializer(serializers.Serializer):
    producto_id = serializers.IntegerField()
    cantidad = serializers.DecimalField(max_digits=10, decimal_places=2, min_value=Decimal('0.01'))
    precio_unitario = serializers.DecimalField(max_digits=12, decimal_places=2, min_value=Decimal('0.01'))
    descuento = serializers.DecimalField(max_digits=5, decimal_places=2, default=Decimal('0.00'), required=False)


class EmitirComprobanteSerializer(serializers.Serializer):
    """Serializer para emitir una factura o boleta."""
    cliente_id = serializers.IntegerField()
    detalles = DetalleInputSerializer(many=True, min_length=1)

    def validate_cliente_id(self, value):
        if not Cliente.objects.filter(id=value).exists():
            raise serializers.ValidationError('El cliente no existe.')
        return value

    def validate_detalles(self, value):
        producto_ids = [d['producto_id'] for d in value]
        existing = set(Producto.objects.filter(id__in=producto_ids).values_list('id', flat=True))
        for pid in producto_ids:
            if pid not in existing:
                raise serializers.ValidationError(f'El producto con ID {pid} no existe.')
        return value


class NotaCreditoInputSerializer(serializers.Serializer):
    """Serializer para emitir una nota de crédito."""
    comprobante_referencia_id = serializers.IntegerField()
    motivo = serializers.CharField(max_length=500)
    tipo_nota = serializers.ChoiceField(choices=NotaCredito.TipoNota.choices)
    monto_afectado = serializers.DecimalField(max_digits=12, decimal_places=2, min_value=Decimal('0.01'))

    def validate_comprobante_referencia_id(self, value):
        if not Comprobante.objects.filter(id=value).exists():
            raise serializers.ValidationError('El comprobante de referencia no existe.')
        return value
