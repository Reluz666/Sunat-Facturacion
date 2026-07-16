class AppError(Exception):
    """Base de todas las excepciones de la aplicación."""
    def __init__(self, mensaje, codigo='ERR_GENERAL'):
        self.mensaje = mensaje
        self.codigo_error = codigo
        super().__init__(self.mensaje)


class ReglaNegocioViolada(AppError):
    pass


class RecursoNoEncontrado(AppError):
    pass


class AccesoNoAutorizado(AppError):
    pass


# Específicas del dominio Comprobantes
class ComprobanteException(ReglaNegocioViolada):
    """Excepción general para lógica de comprobantes."""
    pass


class ValidacionClienteException(ComprobanteException):
    """Excepción lanzada cuando el cliente no cumple los requisitos del comprobante."""
    def __init__(self, mensaje):
        super().__init__(mensaje, codigo='ERR_RUC_REQUERIDO')


class TransicionEstadoException(ComprobanteException):
    """Excepción lanzada cuando se intenta un cambio de estado inválido."""
    def __init__(self, mensaje):
        super().__init__(mensaje, codigo='ERR_ESTADO_INVALIDO')


class GeneracionCorrelativoException(ComprobanteException):
    """Excepción lanzada al fallar la obtención de un correlativo."""
    def __init__(self, mensaje):
        super().__init__(mensaje, codigo='ERR_CORRELATIVO')
