"""Web views para CRUD de Empresa."""
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from .models import Empresa
from .forms import EmpresaForm


@login_required
def lista_empresas_view(request):
    """Listado de empresas del sistema."""
    empresas = Empresa.activos.all()
    return render(request, 'empresa/lista.html', {'empresas': empresas})


@login_required
def crear_empresa_view(request):
    """Registro de nueva empresa emisora (Solo ADMIN)."""
    if request.user.rol != 'ADMIN':
        messages.error(request, 'Solo el Administrador puede registrar empresas.')
        return redirect('empresa-lista')

    if request.method == 'POST':
        form = EmpresaForm(request.POST)
        if form.is_valid():
            try:
                empresa = form.save()
                # Si el usuario actual no tiene empresa asignada, le asignamos esta por defecto
                if not request.user.empresa:
                    request.user.empresa = empresa
                    request.user.save(update_fields=['empresa'])
                messages.success(request, 'Empresa registrada correctamente.')
                return redirect('empresa-lista')
            except Exception as e:
                messages.error(request, str(e))
    else:
        form = EmpresaForm()
    return render(request, 'empresa/form.html', {'form': form, 'titulo': 'Registrar Empresa'})


@login_required
def editar_empresa_view(request, pk):
    """Modificación de los datos de la empresa (Solo ADMIN)."""
    if request.user.rol != 'ADMIN':
        messages.error(request, 'Solo el Administrador puede modificar los datos de la empresa.')
        return redirect('empresa-lista')

    empresa = get_object_or_404(Empresa, pk=pk)
    if request.method == 'POST':
        form = EmpresaForm(request.POST, instance=empresa)
        if form.is_valid():
            try:
                form.save()
                messages.success(request, 'Datos de la empresa actualizados correctamente.')
                return redirect('empresa-lista')
            except Exception as e:
                messages.error(request, str(e))
    else:
        form = EmpresaForm(instance=empresa)
    return render(request, 'empresa/form.html', {'form': form, 'titulo': 'Editar Empresa', 'empresa': empresa})


@login_required
def detalle_empresa_view(request, pk):
    """Ver detalle fiscal y series configuradas de la empresa."""
    empresa = get_object_or_404(Empresa.objects.prefetch_related('series'), pk=pk)
    return render(request, 'empresa/detalle.html', {'empresa': empresa})
