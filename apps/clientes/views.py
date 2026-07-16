"""Web views para CRUD de Clientes."""
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
import urllib.request
import urllib.error
import json
from .models import Cliente
from .forms import ClienteForm


@login_required
def lista_clientes_view(request):
    q = request.GET.get('q', '')
    clientes = Cliente.activos.all()
    if q:
        from django.db.models import Q
        clientes = clientes.filter(Q(num_doc__icontains=q) | Q(razon_social__icontains=q))
    return render(request, 'clientes/lista.html', {'clientes': clientes, 'q': q})


@login_required
def crear_cliente_view(request):
    if request.user.rol not in ['EMISOR', 'ADMIN']:
        messages.error(request, 'No tiene permisos para crear clientes.')
        return redirect('cliente-lista')
        
    if request.method == 'POST':
        form = ClienteForm(request.POST)
        if form.is_valid():
            try:
                form.save()
                messages.success(request, 'Cliente creado correctamente.')
                return redirect('cliente-lista')
            except Exception as e:
                messages.error(request, str(e))
    else:
        form = ClienteForm()
    return render(request, 'clientes/form.html', {'form': form, 'titulo': 'Nuevo Cliente'})


@login_required
def editar_cliente_view(request, pk):
    if request.user.rol not in ['EMISOR', 'ADMIN']:
        messages.error(request, 'No tiene permisos para editar clientes.')
        return redirect('cliente-lista')
        
    cliente = get_object_or_404(Cliente, pk=pk)
    if request.method == 'POST':
        form = ClienteForm(request.POST, instance=cliente)
        if form.is_valid():
            try:
                form.save()
                messages.success(request, 'Cliente actualizado correctamente.')
                return redirect('cliente-lista')
            except Exception as e:
                messages.error(request, str(e))
    else:
        form = ClienteForm(instance=cliente)
    return render(request, 'clientes/form.html', {'form': form, 'titulo': 'Editar Cliente', 'cliente': cliente})


@login_required
def detalle_cliente_view(request, pk):
    cliente = get_object_or_404(Cliente, pk=pk)
    comprobantes = cliente.comprobantes.order_by('-fecha_emision')[:20]
    return render(request, 'clientes/detalle.html', {'cliente': cliente, 'comprobantes': comprobantes})


@login_required
def eliminar_cliente_view(request, pk):
    if request.user.rol != 'ADMIN':
        messages.error(request, 'Solo el administrador puede eliminar clientes.')
        return redirect('cliente-lista')
        
    cliente = get_object_or_404(Cliente, pk=pk)
    if request.method == 'POST':
        try:
            cliente.eliminar(usuario=request.user)
            messages.success(request, 'Cliente desactivado.')
        except Exception as e:
            messages.error(request, f'No se puede eliminar: {e}')
    return redirect('cliente-lista')


@login_required
def consultar_documento_api(request):
    """Proxy API interna para consultar DNI/RUC en apisperu.com de forma segura."""
    tipo = request.GET.get('tipo', '').upper()
    numero = request.GET.get('numero', '').strip()
    
    if not numero:
        return JsonResponse({'success': False, 'message': 'Número de documento requerido.'})
        
    token = "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJlbWFpbCI6InNjYXJsb3NtYXJ0aW5lemQwNUBnbWFpbC5jb20ifQ.IRZi3t6He66NK_K5BIlGAk38gM8j-0sua2-M_TuMWzE"
    
    if tipo == 'DNI' or (len(numero) == 8 and tipo != 'RUC'):
        url = f"https://dniruc.apisperu.com/api/v1/dni/{numero}?token={token}"
    elif tipo == 'RUC' or len(numero) == 11:
        url = f"https://dniruc.apisperu.com/api/v1/ruc/{numero}?token={token}"
    else:
        return JsonResponse({'success': False, 'message': 'Tipo o longitud de documento inválido.'})
        
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=10) as response:
            data = json.loads(response.read().decode('utf-8'))
            return JsonResponse({'success': True, 'data': data})
    except urllib.error.HTTPError as e:
        try:
            err_data = json.loads(e.read().decode('utf-8'))
            msg = err_data.get('message', 'Documento no encontrado o inválido.')
        except Exception:
            msg = f"Error al consultar el servicio ({e.code})."
        return JsonResponse({'success': False, 'message': msg})
    except Exception as e:
        return JsonResponse({'success': False, 'message': f"Error de conexión: {str(e)}"})
