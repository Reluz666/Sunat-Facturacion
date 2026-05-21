"""Web views para comprobantes (Django Templates)."""
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse, HttpResponse
from django.db.models import Sum, Count, Q
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt, ensure_csrf_cookie
from decimal import Decimal
import json

from .models import Comprobante, DetalleComprobante
from .services import emitir_comprobante, emitir_nota_credito
from .sunat_client import reenviar_comprobante
from .pdf_generator import generar_pdf_comprobante
from apps.clientes.models import Cliente
from apps.productos.models import Producto
from apps.empresa.models import SerieComprobante


@login_required
def dashboard_view(request):
    """Dashboard principal con resumen del mes."""
    hoy = timezone.now()
    qs = Comprobante.objects.filter(empresa=request.user.empresa) if request.user.empresa else Comprobante.objects.none()
    if request.user.is_emisor:
        qs = qs.filter(created_by=request.user)
    mes_qs = qs.filter(fecha_emision__month=hoy.month, fecha_emision__year=hoy.year)

    stats = {
        'total_facturas': mes_qs.filter(tipo='FACTURA').count(),
        'total_boletas': mes_qs.filter(tipo='BOLETA').count(),
        'monto_total': mes_qs.aggregate(t=Sum('total'))['t'] or Decimal('0.00'),
        'rechazados': mes_qs.filter(estado='RECHAZADO').count(),
        'aceptados': mes_qs.filter(estado='ACEPTADO').count(),
        'pendientes': mes_qs.filter(estado__in=['BORRADOR', 'EMITIDO', 'ENVIADO']).count(),
    }
    rechazados_list = qs.filter(estado='RECHAZADO').order_by('-fecha_emision')[:5]

    return render(request, 'dashboard/index.html', {
        'stats': stats,
        'rechazados_list': rechazados_list,
        'mes_actual': hoy.strftime('%B %Y'),
    })


@csrf_exempt
@login_required
def emitir_comprobante_view(request):
    """Formulario para emitir factura o boleta."""
    if request.user.rol not in ['EMISOR', 'ADMIN']:
        if request.method == 'POST':
            return JsonResponse({'success': False, 'error': 'No tiene permisos para emitir comprobantes.'}, status=403)
        messages.error(request, 'No tiene permisos para acceder a esta página.')
        return redirect('dashboard')

    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            tipo = data.get('tipo', 'FACTURA')
            cliente_id = data.get('cliente_id')
            detalles = data.get('detalles', [])

            cliente = Cliente.objects.get(id=cliente_id)
            comprobante = emitir_comprobante(
                empresa=request.user.empresa,
                cliente=cliente,
                tipo=tipo,
                detalles_data=detalles,
                usuario=request.user,
            )
            return JsonResponse({
                'success': True,
                'message': f'Comprobante {comprobante.serie_numero} emitido correctamente.',
                'comprobante_id': comprobante.id,
                'serie_numero': comprobante.serie_numero,
                'estado': comprobante.estado,
            })
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)}, status=400)

    productos = Producto.objects.filter(activo=True)
    return render(request, 'comprobantes/emitir.html', {'productos': productos})


@login_required
def lista_comprobantes_view(request):
    """Lista de comprobantes con filtros."""
    qs = Comprobante.objects.select_related('cliente', 'empresa')
    if request.user.empresa:
        qs = qs.filter(empresa=request.user.empresa)
    if request.user.is_emisor:
        qs = qs.filter(created_by=request.user)

    # Filtros
    tipo = request.GET.get('tipo')
    estado = request.GET.get('estado')
    fecha_desde = request.GET.get('fecha_desde')
    fecha_hasta = request.GET.get('fecha_hasta')
    buscar = request.GET.get('buscar')

    if tipo:
        qs = qs.filter(tipo=tipo)
    if estado:
        qs = qs.filter(estado=estado)
    if fecha_desde:
        qs = qs.filter(fecha_emision__gte=fecha_desde)
    if fecha_hasta:
        qs = qs.filter(fecha_emision__lte=fecha_hasta)
    if buscar:
        qs = qs.filter(
            Q(cliente__razon_social__icontains=buscar) |
            Q(cliente__num_doc__icontains=buscar) |
            Q(serie__icontains=buscar)
        )

    comprobantes = qs.order_by('-fecha_emision', '-numero')[:100]

    return render(request, 'comprobantes/lista.html', {
        'comprobantes': comprobantes,
        'filtros': {'tipo': tipo, 'estado': estado, 'fecha_desde': fecha_desde,
                    'fecha_hasta': fecha_hasta, 'buscar': buscar},
    })


@login_required
def detalle_comprobante_view(request, pk):
    qs = Comprobante.objects.select_related('cliente', 'empresa').prefetch_related('detalles__producto', 'logs_envio')
    if request.user.empresa:
        qs = qs.filter(empresa=request.user.empresa)
    if request.user.is_emisor:
        qs = qs.filter(created_by=request.user)
    
    comprobante = get_object_or_404(qs, pk=pk)
    return render(request, 'comprobantes/detalle.html', {'comprobante': comprobante})


@login_required
def pdf_comprobante_view(request, pk):
    qs = Comprobante.objects.select_related('cliente', 'empresa').prefetch_related('detalles__producto')
    if request.user.empresa:
        qs = qs.filter(empresa=request.user.empresa)
    if request.user.is_emisor:
        qs = qs.filter(created_by=request.user)
    
    comprobante = get_object_or_404(qs, pk=pk)
    pdf_buffer = generar_pdf_comprobante(comprobante)
    response = HttpResponse(pdf_buffer.getvalue(), content_type='application/pdf')
    response['Content-Disposition'] = f'inline; filename="{comprobante.serie_numero}.pdf"'
    return response


@csrf_exempt
@login_required
def nota_credito_view(request):
    """Formulario para emitir nota de crédito."""
    if request.user.rol not in ['EMISOR', 'ADMIN']:
        if request.method == 'POST':
            return JsonResponse({'success': False, 'error': 'No tiene permisos para emitir notas de crédito.'}, status=403)
        messages.error(request, 'No tiene permisos para acceder a esta página.')
        return redirect('dashboard')

    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            comp_ref = Comprobante.objects.get(id=data['comprobante_referencia_id'])
            comprobante_nc, nota = emitir_nota_credito(
                empresa=request.user.empresa,
                comprobante_ref=comp_ref,
                motivo=data['motivo'],
                tipo_nota=data['tipo_nota'],
                monto_afectado=data['monto_afectado'],
                usuario=request.user,
            )
            return JsonResponse({
                'success': True,
                'message': f'Nota de Crédito {comprobante_nc.serie_numero} emitida correctamente.',
                'comprobante_id': comprobante_nc.id,
            })
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)}, status=400)

    return render(request, 'comprobantes/nota_credito.html', {
        'tipos_nota': list(dict(item) for item in [
            {'value': c[0], 'label': c[1]} for c in __import__('apps.comprobantes.models', fromlist=['NotaCredito']).NotaCredito.TipoNota.choices
        ]),
    })


@login_required
def reenviar_comprobante_view(request, pk):
    """Reenviar un comprobante rechazado."""
    if request.user.rol not in ['EMISOR', 'ADMIN']:
        messages.error(request, 'No tiene permisos para reenviar comprobantes.')
        return redirect('dashboard')
        
    qs = Comprobante.objects.all()
    if request.user.empresa:
        qs = qs.filter(empresa=request.user.empresa)
    if request.user.is_emisor:
        qs = qs.filter(created_by=request.user)
        
    comprobante = get_object_or_404(qs, pk=pk)
    try:
        reenviar_comprobante(comprobante)
        messages.success(request, f'Comprobante {comprobante.serie_numero} reenviado. Nuevo estado: {comprobante.estado}')
    except Exception as e:
        messages.error(request, str(e))
    return redirect('comprobante-detalle', pk=pk)


@login_required
def buscar_cliente_api(request):
    """API interna para autocompletado de clientes."""
    q = request.GET.get('q', '')
    if len(q) < 2:
        return JsonResponse([], safe=False)
    clientes = Cliente.objects.filter(
        Q(num_doc__icontains=q) | Q(razon_social__icontains=q)
    )[:10]
    data = [{'id': c.id, 'num_doc': c.num_doc, 'tipo_doc': c.tipo_doc,
             'razon_social': c.razon_social, 'direccion': c.direccion} for c in clientes]
    return JsonResponse(data, safe=False)


@login_required
def buscar_comprobante_api(request):
    """API interna para buscar comprobante por serie-número."""
    serie_numero = request.GET.get('q', '')
    if '-' not in serie_numero:
        return JsonResponse({'found': False})
    parts = serie_numero.split('-')
    try:
        serie = parts[0]
        numero = int(parts[1])
        qs = Comprobante.objects.select_related('cliente')
        if request.user.empresa:
            qs = qs.filter(empresa=request.user.empresa)
        if request.user.is_emisor:
            qs = qs.filter(created_by=request.user)
            
        comp = qs.get(serie=serie, numero=numero)
        return JsonResponse({
            'found': True,
            'id': comp.id,
            'serie_numero': comp.serie_numero,
            'tipo': comp.get_tipo_display(),
            'cliente': comp.cliente.razon_social,
            'total': str(comp.total),
            'estado': comp.estado,
        })
    except (Comprobante.DoesNotExist, ValueError, IndexError):
        return JsonResponse({'found': False})
