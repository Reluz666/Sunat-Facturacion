"""Serializers y API views para Clientes."""
from rest_framework import serializers, viewsets, filters
from django_filters.rest_framework import DjangoFilterBackend
from .models import Cliente


class ClienteSerializer(serializers.ModelSerializer):
    class Meta:
        model = Cliente
        fields = ['id', 'tipo_doc', 'num_doc', 'razon_social', 'direccion', 'email']


class ClienteViewSet(viewsets.ModelViewSet):
    queryset = Cliente.activos.all()
    serializer_class = ClienteSerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ['tipo_doc']
    search_fields = ['num_doc', 'razon_social', 'email']
