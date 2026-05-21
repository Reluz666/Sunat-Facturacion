"""Web views para Reportes."""
from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.db.models import Sum, Count, Q
from django.utils import timezone
from decimal import Decimal
import openpyxl
from openpyxl.styles import Font, Alignment, PatternFill
from openpyxl.utils import get_column_letter
from apps.comprobantes.models import Comprobante


@login_required
def libro_ventas_view(request):
    """Libro de Ventas con filtros por mes/año y exportación."""
    hoy = timezone.now()
    mes = request.GET.get('mes', str(hoy.month))
    anio = request.GET.get('anio', str(hoy.year))

    qs = Comprobante.objects.select_related('cliente').exclude(tipo='NOTA_CREDITO')
    if request.user.empresa:
        qs = qs.filter(empresa=request.user.empresa)
    if request.user.is_emisor:
        qs = qs.filter(created_by=request.user)

    qs = qs.filter(fecha_emision__month=int(mes), fecha_emision__year=int(anio))
    comprobantes = qs.order_by('fecha_emision', 'serie', 'numero')

    totales = qs.aggregate(
        total_base=Sum('subtotal'), total_igv=Sum('igv'), total_general=Sum('total'),
        cantidad=Count('id'),
        aceptados=Count('id', filter=Q(estado='ACEPTADO')),
        rechazados=Count('id', filter=Q(estado='RECHAZADO')),
    )

    # Stats por tipo para gráficos
    import json
    tipo_map = dict(Comprobante.TipoComprobante.choices)
    estado_map = dict(Comprobante.EstadoComprobante.choices)

    stats_tipo_clean = [
        {
            'tipo': tipo_map.get(item['tipo'], item['tipo']),
            'count': item['count'],
            'total': float(item['total'] or 0)
        }
        for item in qs.values('tipo').annotate(count=Count('id'), total=Sum('total'))
    ]
    stats_estado_clean = [
        {
            'estado': estado_map.get(item['estado'], item['estado']),
            'count': item['count']
        }
        for item in qs.values('estado').annotate(count=Count('id'))
    ]

    return render(request, 'reportes/libro_ventas.html', {
        'comprobantes': comprobantes,
        'totales': totales,
        'stats_tipo_json': json.dumps(stats_tipo_clean),
        'stats_estado_json': json.dumps(stats_estado_clean),
        'mes': mes,
        'anio': anio,
        'meses': list(range(1, 13)),
        'anios': list(range(2024, hoy.year + 2)),
    })


@login_required
def exportar_excel_view(request):
    """Exportar libro de ventas a Excel con formato."""
    mes = request.GET.get('mes')
    anio = request.GET.get('anio')

    qs = Comprobante.objects.select_related('cliente').exclude(tipo='NOTA_CREDITO')
    if request.user.empresa:
        qs = qs.filter(empresa=request.user.empresa)
    if request.user.is_emisor:
        qs = qs.filter(created_by=request.user)
    if mes and anio:
        qs = qs.filter(fecha_emision__month=int(mes), fecha_emision__year=int(anio))

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = f"Ventas {anio}-{mes}"

    # Estilos
    header_font = Font(bold=True, color="FFFFFF")
    header_fill = PatternFill("solid", fgColor="1A237E") # Azul oscuro
    alignment = Alignment(horizontal="center", vertical="center")
    
    headers = ['Fecha', 'Serie-Número', 'Tipo', 'Cliente', 'RUC/DNI',
               'Base Imponible', 'IGV', 'Total', 'Estado SUNAT']
    
    ws.append(headers)
    for col_num in range(1, len(headers) + 1):
        cell = ws.cell(row=1, column=col_num)
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = alignment

    for c in qs.order_by('fecha_emision'):
        ws.append([
            c.fecha_emision.strftime('%Y-%m-%d'), 
            c.serie_numero, 
            c.get_tipo_display(),
            c.cliente.razon_social, 
            c.cliente.num_doc,
            float(c.subtotal), 
            float(c.igv), 
            float(c.total), 
            c.estado,
        ])
        
    # Formato de números y anchos de columna
    for row in ws.iter_rows(min_row=2, max_row=ws.max_row, min_col=6, max_col=8):
        for cell in row:
            cell.number_format = '#,##0.00'

    column_widths = [12, 15, 12, 40, 15, 15, 12, 15, 15]
    for i, width in enumerate(column_widths, 1):
        ws.column_dimensions[get_column_letter(i)].width = width

    response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    response['Content-Disposition'] = f'attachment; filename="libro_ventas_{anio}_{mes}.xlsx"'
    wb.save(response)

    return response
