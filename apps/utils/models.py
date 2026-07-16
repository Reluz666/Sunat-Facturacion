"""
Modelo base abstracto con auditoría y soft delete.

Todos los modelos del sistema deben heredar de ModeloBase para garantizar:
  - Campos de auditoría: creado_en, actualizado_en, creado_por
  - Soft delete: campo activo + método eliminar()
  - Manager activos: filtra solo registros activos
"""
from django.db import models
from django.conf import settings
from django.utils import timezone


class ManagerActivos(models.Manager):
    """Manager que filtra solo registros activos (no eliminados)."""

    def get_queryset(self):
        return super().get_queryset().filter(activo=True)


class ModeloBase(models.Model):
    """
    Modelo base abstracto con auditoría y soft delete.

    Campos:
      - creado_en: Fecha de creación (auto)
      - actualizado_en: Fecha de última actualización (auto)
      - creado_por: Usuario que creó el registro (FK a User)
      - activo: Flag de soft delete (True = activo, False = eliminado)

    Managers:
      - objects: Todos los registros (incluye eliminados)
      - activos: Solo registros activos
    """

    creado_en = models.DateTimeField(auto_now_add=True, verbose_name='Creado en')
    actualizado_en = models.DateTimeField(auto_now=True, verbose_name='Actualizado en')
    creado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        related_name='+',
        on_delete=models.SET_NULL,
        verbose_name='Creado por'
    )
    activo = models.BooleanField(default=True, db_index=True, verbose_name='Activo')

    objects = models.Manager()    # todos los registros
    activos = ManagerActivos()    # solo activos

    def eliminar(self, usuario=None):
        """Soft delete: nunca borrar físicamente."""
        self.activo = False
        if usuario:
            self.creado_por = usuario
        self.save(update_fields=['activo', 'actualizado_en'])

    class Meta:
        abstract = True
