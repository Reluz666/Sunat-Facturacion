import random
from typing import Tuple
from decouple import config

from dominio.comprobantes.entidades import Comprobante
from dominio.comprobantes.puertos import ISunatClient, IComprobanteRepository
from dominio.comprobantes.excepciones import TransicionEstadoException
from apps.comprobantes.models import LogEnvioSUNAT
from apps.comprobantes.sunat_soap import SunatSoapClient
from .xml_generator import generar_xml_comprobante


class DjangoSunatClient(ISunatClient):
    """Adaptador de infraestructura para interactuar con la OSE/SUNAT."""

    def __init__(self, comp_repo: IComprobanteRepository):
        self.comp_repo = comp_repo

    def generar_xml(self, comprobante: Comprobante) -> Tuple[bytes, str]:
        return generar_xml_comprobante(comprobante)
        
    def enviar_comprobante(self, comprobante: Comprobante) -> None:
        if comprobante.estado not in ['EMITIDO', 'RECHAZADO']:
            raise TransicionEstadoException('Solo comprobantes EMITIDOS o RECHAZADOS pueden enviarse.')
            
        comprobante.estado = 'ENVIADO'
        self.comp_repo.actualizar_comprobante(comprobante, estado='ENVIADO')

        if config('SUNAT_BETA_MODE', default=True, cast=bool):
            soap_client = SunatSoapClient()
            resultado = soap_client.send_bill(comprobante, comprobante.xml_firmado)
            
            if resultado['success']:
                LogEnvioSUNAT.objects.create(
                    comprobante_id=comprobante.id,
                    estado_respuesta='ACEPTADO',
                    codigo_respuesta=resultado['code'],
                    descripcion=resultado['description']
                )
                comprobante.estado = 'ACEPTADO'
            else:
                estado_res = 'RECHAZADO'
                if resultado.get('code') == 'ERROR_CONEXION':
                    estado_res = 'EXCEPCION'
                    
                LogEnvioSUNAT.objects.create(
                    comprobante_id=comprobante.id,
                    estado_respuesta=estado_res,
                    codigo_respuesta=resultado.get('code', 'ERR'),
                    descripcion=resultado.get('error') or resultado.get('description')
                )
                if estado_res == 'RECHAZADO':
                    comprobante.estado = 'RECHAZADO'
        else:
            aceptado = random.random() < 0.9
            if aceptado:
                LogEnvioSUNAT.objects.create(
                    comprobante_id=comprobante.id,
                    estado_respuesta='ACEPTADO',
                    codigo_respuesta='0',
                    descripcion='(Simulación) La factura electrónica fue aceptada por SUNAT.'
                )
                comprobante.estado = 'ACEPTADO'
            else:
                LogEnvioSUNAT.objects.create(
                    comprobante_id=comprobante.id,
                    estado_respuesta='RECHAZADO',
                    codigo_respuesta='2800',
                    descripcion='(Simulación) Error en la estructura del comprobante.'
                )
                comprobante.estado = 'RECHAZADO'
        
        self.comp_repo.actualizar_comprobante(comprobante, estado=comprobante.estado)
