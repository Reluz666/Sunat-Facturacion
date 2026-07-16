from abc import ABC, abstractmethod

class IComprobanteRepository(ABC):
    """
    Interfaz para el repositorio de Comprobantes.
    Define los métodos de persistencia sin acoplar a un ORM específico.
    """

    @abstractmethod
    def guardar_comprobante_y_detalles(self, comprobante_data, detalles_data):
        """
        Guarda el comprobante y sus detalles de manera transaccional.
        Retorna el comprobante creado (como entidad o modelo).
        """
        pass

    @abstractmethod
    def actualizar_comprobante(self, comprobante, **kwargs):
        """
        Actualiza un comprobante existente con los kwargs dados.
        """
        pass

    @abstractmethod
    def guardar_nota_credito(self, nota_credito_data, comprobante_data, detalles_data):
        """
        Guarda la nota de crédito, su comprobante y detalles.
        """
        pass
