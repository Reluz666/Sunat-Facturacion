# Taller de Lenguajes de Programación

*Especificaciones, Arquitectura y Rúbricas*
**Proyectos Integradores — Solución Web Completa — Ciclo 2026-01**

> Este documento reúne las **páginas 1–10** del PDF original (especificaciones generales y requerimientos arquitectónicos, aplicables a los 9 proyectos) y las **páginas 23–25** (ficha completa del **Proyecto 5**).

---

## 9 Proyectos Disponibles

1. Plataforma de Delivery Local
2. Sistema de Punto de Venta (POS)
3. Venta de Pasajes Terrestres Interprovinciales
4. Optimización de Rutas de Distribución
5. **Facturación Electrónica SUNAT-ready**
6. Picking Inteligente para Almacenes
7. Sistema de Gestión Hotelera
8. Gestión para Restaurantes y Food Service
9. Control Nutricional y Tracking de Hábitos

**Naturaleza del entregable:** Solución web completa (backend Django/DRF + frontend web) con requerimientos arquitectónicos escalonados.

### Componentes de Evaluación General

| Componente | Peso | Descripción |
|---|---|---|
| Modelos y Base de Datos | 10% | Diseño correcto de entidades, relaciones e índices |
| API REST | 10% | Endpoints completos, códigos HTTP, validaciones, paginación |
| Lógica de Negocio Específica | 10% | Reglas y flujos críticos del dominio implementados |
| Frontend Web | 15% | Vistas funcionales, conectadas a la API, UX usable |
| Integración API–Frontend + Auth | 10% | Token en headers, errores en UI, vistas protegidas por rol |
| Nivel 1 — Service Layer + Excepciones | 15% | Capa de servicios completa, excepciones de dominio propias |
| Nivel 1 — Soft Delete + Docker | 10% | Modelo base abstracto, soft delete, Docker Compose funcional |
| Nivel 2 — Patrón Arquitectónico elegido | 15% | Uno de: Repository, Strategy, Celery, Redis, Events, WebSockets |
| Testing | 5% | Tests unitarios e integración, cobertura ≥ 60% |
| Documentación y Calidad de Código | 5% | README, Swagger, instrucciones de despliegue, clean code, sin N+1 |

### ⭐ BONUS — Nivel 3: Arquitectura Hexagonal (+10 puntos sobre la nota final)

- El directorio `dominio/` no puede importar nada de Django. Entidades de dominio como dataclasses Python puras.
- Puertos definidos como Protocols (interfaces). Adaptadores en `infraestructura/` implementan los puertos.
- Views de Django solo reciben el request y llaman al dominio. Tests de dominio sin base de datos (mocks).

---

## Requerimientos Arquitectónicos

*Aplican a los 9 proyectos*

### NIVEL 1 — Obligatorio para todos los proyectos (25% de la nota)

- **Service Layer:** una clase `XxxService` por módulo con toda la lógica de negocio. Las Views solo reciben el request, llaman al servicio y devuelven el response.
- **Excepciones de Dominio:** jerarquía propia en `exceptions.py`. Clases específicas como `AsientoNoDisponible`, `CajaNoAbierta`, `CapacidadExcedida`. Nunca lanzar `ValueError` o `Exception` genéricos.
- **Soft Delete + Auditoría:** modelo base abstracto con `creado_en`, `actualizado_en`, `creado_por` (FK a User), `activo`. Método `eliminar()` que hace soft delete. Todo modelo del sistema hereda de él.
- **Docker Compose:** el proyecto debe levantarse con `docker compose up --build`. Incluye Django + PostgreSQL + Redis (si aplica). Archivo `.env.example` con todas las variables requeridas.

#### Ejemplo — Service Layer

```python
# ❌ MAL — Lógica en la View
class PedidoViewSet(viewsets.ModelViewSet):
    def create(self, request):
        producto = Producto.objects.get(pk=request.data["producto_id"])
        if producto.stock == 0:
            return Response({"error": "Sin stock"}, status=400)
        pedido = Pedido.objects.create(...)
        producto.stock -= 1
        producto.save()
        return Response(PedidoSerializer(pedido).data, status=201)


# ✅ BIEN — View delgada, Service con la lógica
class PedidoViewSet(viewsets.ModelViewSet):
    def create(self, request):
        try:
            pedido = PedidoService.crear(request.data, usuario=request.user)
            return Response(PedidoSerializer(pedido).data, status=201)
        except ProductoSinStock as e:
            return Response({"error": str(e)}, status=400)
        except NegocioCerrado as e:
            return Response({"error": str(e)}, status=422)


# services.py
class PedidoService:
    @staticmethod
    @transaction.atomic
    def crear(data: dict, usuario) -> Pedido:
        producto = Producto.objects.select_for_update().get(pk=data["producto_id"])
        if producto.stock == 0:
            raise ProductoSinStock(f"{producto.nombre} no tiene stock disponible")
        if not NegocioService.esta_abierto(data["negocio_id"]):
            raise NegocioCerrado("El negocio está cerrado en este momento")
        pedido = Pedido.objects.create(**data, cliente=usuario)
        producto.stock -= 1
        producto.save(update_fields=["stock", "actualizado_en"])
        return pedido
```

#### Ejemplo — Excepciones de Dominio

```python
# exceptions.py
class AppError(Exception):
    """Base de todas las excepciones de la aplicación."""


class ReglaNegocioViolada(AppError): pass
class RecursoNoEncontrado(AppError): pass
class AccesoNoAutorizado(AppError): pass


# Específicas del dominio
class ProductoSinStock(ReglaNegocioViolada): pass
class NegocioCerrado(ReglaNegocioViolada): pass
class TransicionEstadoInvalida(ReglaNegocioViolada): pass
class CajaNoAbierta(ReglaNegocioViolada): pass
class AsientoNoDisponible(ReglaNegocioViolada): pass
```

#### Ejemplo — Modelo Base + Soft Delete

```python
# utils/models.py
class ManagerActivos(models.Manager):
    def get_queryset(self):
        return super().get_queryset().filter(activo=True)


class ModeloBase(models.Model):
    creado_en = models.DateTimeField(auto_now_add=True)
    actualizado_en = models.DateTimeField(auto_now=True)
    creado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True,
        related_name="+", on_delete=models.SET_NULL
    )
    activo = models.BooleanField(default=True, db_index=True)

    objects = models.Manager()   # todos los registros
    activos = ManagerActivos()   # solo activos

    def eliminar(self, usuario=None):
        """Soft delete: nunca borrar físicamente."""
        self.activo = False
        if usuario:
            self.creado_por = usuario
        self.save(update_fields=["activo", "actualizado_en"])

    class Meta:
        abstract = True
```

### NIVEL 2 — Elegir 1 patrón según el proyecto (15% de la nota)

- Cada proyecto tiene un patrón recomendado en su ficha, pero el grupo puede elegir cualquiera de los 6.
- **Repository Pattern:** abstrae el acceso a datos. El Service usa una interfaz, no el ORM directamente.
- **Strategy Pattern:** reglas de negocio intercambiables (ej: políticas de descuento, políticas de cancelación).
- **Celery + tareas asíncronas:** procesos no bloqueantes (TTL de reservas, envío de emails, reportes async).
- **Caché con Redis:** reducir queries repetidas en buscadores y listados de alta frecuencia.
- **Eventos de Dominio:** desacoplamiento entre módulos mediante publicación/suscripción de eventos.
- **WebSockets con Django Channels:** actualizaciones en tiempo real (KDS de cocina, tracking, plano de hotel).

#### Ejemplo — Repository Pattern

```python
# dominio/puertos/repositorios.py
from typing import Protocol


class IEncomiendaRepository(Protocol):
    def obtener_por_codigo(self, codigo: str) -> "Encomienda": ...
    def listar_activas(self) -> list["Encomienda"]: ...
    def guardar(self, encomienda: "Encomienda") -> None: ...


# infraestructura/persistencia/encomienda_repo.py
class EncomiendaRepositoryDjango:
    def obtener_por_codigo(self, codigo: str):
        try:
            return EncomiendaModel.objects.select_related(
                "remitente", "agencia_origen"
            ).get(codigo=codigo, activo=True)
        except EncomiendaModel.DoesNotExist:
            raise RecursoNoEncontrado(f"Encomienda {codigo} no existe")

    def guardar(self, encomienda):
        encomienda.save()


# services.py — Service usa el puerto, no el ORM directamente
class EncomiendaService:
    def __init__(self, repo: IEncomiendaRepository):
        self.repo = repo

    def cambiar_estado(self, codigo: str, nuevo_estado: str) -> None:
        enc = self.repo.obtener_por_codigo(codigo)
        enc.cambiar_estado(nuevo_estado)   # lógica en la entidad
        self.repo.guardar(enc)
```

#### Ejemplo — Strategy Pattern

```python
# strategies/reembolso.py
from typing import Protocol
from decimal import Decimal


class PoliticaReembolso(Protocol):
    def calcular(self, monto: Decimal, horas_anticipacion: int) -> Decimal: ...


class ReembolsoTotal:
    def calcular(self, monto, horas_anticipacion):
        return monto


class ReembolsoParcial:
    def calcular(self, monto, horas_anticipacion):
        return monto * Decimal("0.80") if horas_anticipacion >= 24 else Decimal("0")


class SinReembolso:
    def calcular(self, monto, horas_anticipacion):
        return Decimal("0")


# service usa la estrategia — no sabe cuál es
class CancelacionService:
    def __init__(self, politica: PoliticaReembolso):
        self.politica = politica

    def cancelar(self, boleto) -> Decimal:
        horas = calcular_horas(boleto.viaje.fecha_salida)
        return self.politica.calcular(boleto.precio_final, horas)
```

#### Ejemplo — Celery (TTL de reservas)

```python
# tasks.py
from celery import shared_task


@shared_task
def liberar_reserva_expirada(reserva_id: int):
    from .models import Reserva
    try:
        r = Reserva.objects.get(pk=reserva_id, estado="PENDIENTE")
        r.asiento.estado = "DISPONIBLE"
        r.asiento.save(update_fields=["estado"])
        r.estado = "EXPIRADA"
        r.save(update_fields=["estado", "actualizado_en"])
    except Reserva.DoesNotExist:
        pass   # ya fue procesada (comprada o cancelada)


# services.py — lanza la tarea al crear la reserva
class ReservaService:
    @staticmethod
    @transaction.atomic
    def crear(viaje_id, asiento_id, pasajero) -> Reserva:
        # ... validaciones ...
        reserva = Reserva.objects.create(...)
        # Liberar en 15 minutos si no se confirma
        liberar_reserva_expirada.apply_async(
            args=[reserva.id], countdown=900
        )
        return reserva
```

#### Ejemplo — Eventos de Dominio

```python
# events.py
from dataclasses import dataclass
from datetime import datetime


@dataclass
class PedidoEntregado:
    pedido_id: int
    cliente_email: str
    repartidor_id: int
    fecha: datetime


# event_bus.py
handlers = {}


def subscribe(event_class, handler): ...

def publish(event):
    for h in handlers.get(type(event), []):
        h(event)


# handlers/notificaciones.py — reacciona al evento
def al_entregar_pedido(event: PedidoEntregado):
    EmailService.enviar_confirmacion(event.cliente_email)
    EstadisticaService.registrar_entrega(event.repartidor_id)


# service — emite, no sabe quién escucha
class PedidoService:
    def entregar(self, pedido_id: int) -> None:
        pedido = self.repo.obtener(pedido_id)
        pedido.marcar_entregado()
        self.repo.guardar(pedido)
        publish(PedidoEntregado(
            pedido_id=pedido.id,
            cliente_email=pedido.cliente.email,
            repartidor_id=pedido.repartidor_id,
            fecha=datetime.now()
        ))
```

### NIVEL 3 — Arquitectura Hexagonal (+10 puntos BONUS)

- El directorio `dominio/` no puede tener ningún import de Django (ni models, ni settings, ni nada).
- Entidades de dominio como dataclasses o clases Python puras con toda la lógica de negocio.
- Puertos definidos como `typing.Protocol`. Adaptadores en `infraestructura/` implementan los puertos.
- Views de Django solo reciben el request y delegan al dominio. Son adaptadores de entrada.
- Tests del dominio no usan base de datos — usan repositorios mock.
- Estructura de carpetas: `dominio/` — `infraestructura/` — `interfaces/`

#### Estructura de carpetas — Arquitectura Hexagonal

```
proyecto/
├── dominio/                     ← Python puro. CERO Django.
│   ├── entidades/                ← Clases de dominio con lógica de negocio
│   │   └── pedido.py              ← dataclass + métodos de dominio
│   ├── servicios/                 ← Casos de uso
│   │   └── pedido_service.py
│   ├── puertos/                   ← Interfaces (Protocol)
│   │   ├── repositorios.py        ← IPedidoRepository, IClienteRepository
│   │   └── notificaciones.py      ← IEmailService, ISMSService
│   └── excepciones.py
│
├── infraestructura/               ← Implementaciones concretas
│   ├── persistencia/               ← Adaptadores Django ORM
│   │   └── pedido_repo.py
│   ├── email/                      ← Adaptador SMTP / SendGrid
│   └── cache/                      ← Adaptador Redis
│
└── interfaces/                    ← Adaptadores de entrada
    ├── api/
    │   ├── views.py                ← Solo recibe request, llama al dominio
    │   └── serializers.py
    └── admin.py
```

#### Entidad de dominio — Python puro

```python
# dominio/entidades/pedido.py — SIN imports de Django
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from ..excepciones import TransicionEstadoInvalida


@dataclass
class Pedido:
    id: int | None
    cliente_id: int
    estado: str = "RECIBIDO"
    total: Decimal = Decimal("0")
    items: list = field(default_factory=list)

    TRANSICIONES = {
        "RECIBIDO": ["CONFIRMADO", "CANCELADO"],
        "CONFIRMADO": ["EN_PREPARACION", "CANCELADO"],
        "EN_PREPARACION": ["LISTO_PARA_RECOJO"],
        "LISTO_PARA_RECOJO": ["EN_CAMINO"],
        "EN_CAMINO": ["ENTREGADO"],
    }

    def cambiar_estado(self, nuevo: str) -> None:
        if nuevo not in self.TRANSICIONES.get(self.estado, []):
            raise TransicionEstadoInvalida(
                f"No se puede ir de {self.estado} a {nuevo}"
            )
        self.estado = nuevo
```

---

## PROYECTO 5 — Facturación Electrónica SUNAT-ready

### Descripción del Sistema

Sistema para emitir comprobantes electrónicos (facturas, boletas, notas de crédito) siguiendo normativa SUNAT. Gestiona el ciclo completo: emisión, envío al OSE (mock) y respuesta.

### Modelos de Datos Requeridos

**Entidades:**

- **Empresa:** ruc, razon_social, nombre_comercial, direccion, regimen_tributario — hereda `ModeloBase`
- **SerieComprobante:** tipo(F/B/FC), serie, correlativo_actual, empresa — unique(tipo, serie, empresa)
- **ClienteCE:** tipo_doc(RUC/DNI/CE), num_doc, razon_social, direccion, email — hereda `ModeloBase`
- **ProductoCE:** codigo, descripcion, unidad_medida, precio_unitario, afecto_igv (bool)
- **Comprobante:** serie, numero, fecha, cliente, tipo, subtotal, igv, total, estado, xml_firmado — unique(serie, numero)
- **DetalleComprobante:** comprobante, producto, cantidad, precio_unitario, igv_linea, subtotal
- **LogEnvioSUNAT:** comprobante, fecha_envio, estado_respuesta, codigo_respuesta, descripcion
- **NotaCredito:** comprobante_referencia, motivo, tipo_nota, monto_afectado

### Endpoints Mínimos

- `POST /api/facturas/` — FacturaService.emitir: genera XML, calcula IGV, numeración correlativa
- `POST /api/boletas/` — BoletaService.emitir: valida DNI
- `POST /api/notas-credito/` — NotaCreditoService.emitir: referencia al original, valida montos
- `GET /api/comprobantes/?tipo=&fecha_desde=&ruc_cliente=` — Listado paginado con filtros
- `POST /api/comprobantes/{id}/reenviar/` — Reenviar si RECHAZADO
- `GET /api/comprobantes/{id}/pdf/` — Vista imprimible (HTML o PDF)
- `GET /api/reportes/ventas-por-periodo/?mes=&anio=` — Libro de ventas simplificado

### Vistas Web Requeridas

*Vistas / Pantallas Web Requeridas (Django Templates + Bootstrap 5 | React/Vue)*

- **Dashboard:** resumen del mes — facturas, boletas, total facturado, alertas de RECHAZADOS
- **Emitir Comprobante:** selector de tipo, búsqueda de cliente por RUC/DNI con autocompletado, tabla de líneas con cálculo de IGV en tiempo real, total automático
- **Lista de Comprobantes:** tabla paginada con badges de estado SUNAT, filtros y descarga
- **Vista Previa del Comprobante:** formato voucher con logo, datos, líneas, subtotal, IGV y total. Botón imprimir
- **Emitir Nota de Crédito:** buscar comprobante original por serie/número, seleccionar motivo y monto
- **Mantenimiento de Clientes y Productos:** CRUD con validación de RUC/DNI en tiempo real
- **Libro de Ventas:** tabla mensual con exportación a CSV

### Reglas de Negocio Críticas

- FacturaService lanza `TipoDocumentoInvalido` si se emite factura con DNI (necesita RUC)
- NumeracionService garantiza correlativo sin saltos usando `select_for_update()`
- IGV = 18% sobre la suma de líneas con `afecto_igv = True`
- NotaCreditoService lanza `MontoExcedidoError` si el monto supera al comprobante original
- Comprobante ACEPTADO no se puede eliminar — solo anular vía nota de crédito
- Estado: BORRADOR → EMITIDO → ENVIADO → ACEPTADO / RECHAZADO

### Requerimientos Arquitectónicos Específicos

- **Nivel 1 (obligatorio):** Service Layer, Excepciones de dominio, Soft Delete + auditoría, Docker Compose.
- **Nivel 2 recomendado:** Repository Pattern o Celery — Repository para abstraer el acceso al comprobante y al log de SUNAT (facilita mock en tests). Celery para enviar al OSE/SUNAT de forma asíncrona sin bloquear el response al usuario.
- **Nivel 3 (bonus +10 pts):** Arquitectura Hexagonal — `dominio/` sin imports de Django.

### Rúbrica de Evaluación

| Área | Peso | Logrado 100% | En Progreso 70% | Básico 40% | Insuficiente 0% |
|---|---|---|---|---|---|
| **Modelos y DB** | 10% | Todas las entidades con unique en serie+número, ModeloBase, log de envíos SUNAT | Sin unique en serie+número (permite duplicados de comprobantes) | Modelos básicos sin log de envíos | Modelos incompletos |
| **API REST** | 10% | Emisión de los 3 tipos con validaciones tributarias, ciclo de estados y reenvío | Factura y boleta correctas, nota de crédito parcial | Solo facturas sin validaciones tributarias | < 50% de endpoints |
| **Lógica — Lógica Tributaria** | 10% | IGV correcto, numeración correlativa con select_for_update, ciclo SUNAT completo en services | IGV correcto pero numeración sin lock o sin ciclo SUNAT | Cálculo básico en View sin Service | Sin lógica tributaria |
| **Frontend Web** | 15% | Formulario con autocompletado y cálculo dinámico de IGV, lista con badges de estado, vista previa en formato voucher | Formulario funcional sin cálculo dinámico ni vista previa | Formularios básicos sin feedback tributario | Sin frontend o desconectado |
| **Integración + Auth** | 10% | JWT con roles (emisor, contador, admin), comprobantes filtrados por empresa | JWT con roles parciales | Auth básica | Sin auth |
| **Nivel 1 — Service Layer + Excepciones** | 15% | Service por módulo con toda la lógica de negocio. Excepciones de dominio propias capturadas en Views con handlers específicos. Views sin lógica de negocio | Service implementado pero Views aún contienen lógica. Excepciones parciales o usando ValueError genérico | Función de servicio sin clase, lógica mezclada con serializers o views | Sin capa de servicios. Toda la lógica en Views o Serializers |
| **Nivel 1 — Soft Delete + Docker** | 10% | Modelo base abstracto con creado_en, actualizado_en, creado_por, activo. Soft delete implementado. Docker Compose funcional: levantar con un comando | Modelo base presente pero sin creado_por o sin soft delete. Docker Compose parcial (falta PostgreSQL o variables de entorno) | Campos de auditoría en algunos modelos pero sin modelo base abstracto. Solo Dockerfile sin Compose | Sin auditoría ni soft delete. Sin Docker |
| **Nivel 2 — Repository (abstrae SUNAT) o Celery (envío asíncrono)** | 15% | Patrón implementado correctamente, integrado al flujo principal, con tests que demuestran el beneficio del desacoplamiento | Patrón implementado pero sin tests que lo validen o integración incompleta | Intento de implementar el patrón pero con errores de diseño (dependencias circulares, acoplamiento) | Patrón no implementado o implementado de forma que no aporta desacoplamiento |
| **Testing** | 5% | Tests de flujo principal, lógica crítica y permisos. Cobertura ≥ 60% | Tests principales, cobertura 40-60% | Tests básicos, cobertura < 40% | Sin tests |
| **Docs y Calidad** | 5% | Swagger completo, README con setup frontend+backend, sin N+1 en queries | Swagger generado y README básico | Solo README | Sin documentación |
