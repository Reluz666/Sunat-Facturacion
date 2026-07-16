"""Web views para CRUD de Productos."""
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from .models import Producto
from .forms import ProductoForm


@login_required
def lista_productos_view(request):
    q = request.GET.get('q', '')
    productos = Producto.activos.all()
    if q:
        from django.db.models import Q
        productos = productos.filter(Q(codigo__icontains=q) | Q(descripcion__icontains=q))
    return render(request, 'productos/lista.html', {'productos': productos, 'q': q})


@login_required
def crear_producto_view(request):
    if request.user.rol != 'ADMIN':
        messages.error(request, 'Solo el administrador puede crear productos.')
        return redirect('producto-lista')
        
    if request.method == 'POST':
        form = ProductoForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Producto creado correctamente.')
            return redirect('producto-lista')
    else:
        form = ProductoForm()
    return render(request, 'productos/form.html', {'form': form, 'titulo': 'Nuevo Producto'})


@login_required
def editar_producto_view(request, pk):
    if request.user.rol != 'ADMIN':
        messages.error(request, 'Solo el administrador puede editar productos.')
        return redirect('producto-lista')
        
    producto = get_object_or_404(Producto, pk=pk)
    if request.method == 'POST':
        form = ProductoForm(request.POST, instance=producto)
        if form.is_valid():
            form.save()
            messages.success(request, 'Producto actualizado correctamente.')
            return redirect('producto-lista')
    else:
        form = ProductoForm(instance=producto)
    return render(request, 'productos/form.html', {'form': form, 'titulo': 'Editar Producto', 'producto': producto})


@login_required
def eliminar_producto_view(request, pk):
    if request.user.rol != 'ADMIN':
        messages.error(request, 'Solo el administrador puede desactivar productos.')
        return redirect('producto-lista')
        
    producto = get_object_or_404(Producto, pk=pk)
    if request.method == 'POST':
        try:
            producto.eliminar(usuario=request.user)
            messages.success(request, 'Producto desactivado.')
        except Exception as e:
            messages.error(request, str(e))
    return redirect('producto-lista')


@login_required
def importar_productos_excel_view(request):
    if request.user.rol != 'ADMIN':
        messages.error(request, 'Solo el administrador puede importar productos.')
        return redirect('producto-lista')
        
    if request.method == 'POST':
        if 'excel_file' not in request.FILES:
            messages.error(request, "Por favor seleccione un archivo Excel.")
            return redirect('producto-lista')

        excel_file = request.FILES['excel_file']
        if not excel_file.name.endswith(('.xlsx', '.xls')):
            messages.error(request, "El archivo debe ser una hoja de cálculo de Excel (.xlsx o .xls).")
            return redirect('producto-lista')

        try:
            import openpyxl
            from decimal import Decimal
            
            wb = openpyxl.load_workbook(excel_file, data_only=True)
            sheet = wb.active

            # Identificar las columnas requeridas en la primera fila
            headers = {}
            for col_idx, cell in enumerate(sheet[1]):
                if cell.value is not None:
                    val = str(cell.value).strip().lower()
                    # Mapeo flexible de nombres de columnas
                    if 'codigo' in val or 'código' in val:
                        headers['codigo'] = col_idx
                    elif 'descrip' in val:
                        headers['descripcion'] = col_idx
                    elif 'unidad' in val or 'medida' in val:
                        headers['unidad_medida'] = col_idx
                    elif 'precio' in val:
                        headers['precio_unitario'] = col_idx
                    elif 'afecto' in val or 'igv' in val:
                        headers['afecto_igv'] = col_idx

            # Verificar que estén las 5 columnas requeridas por el usuario
            expected_columns = ['codigo', 'descripcion', 'unidad_medida', 'precio_unitario', 'afecto_igv']
            missing = [col for col in expected_columns if col not in headers]
            if missing:
                messages.error(
                    request, 
                    f"El archivo Excel no tiene el formato correcto. Faltan identificar las columnas: {', '.join(missing)}"
                )
                return redirect('producto-lista')

            productos_creados = 0
            productos_actualizados = 0
            errores = []

            # Mapeo robusto de unidades de medida
            unidad_map = {
                'unidad': 'NIU', 'niu': 'NIU',
                'kilogramo': 'KGM', 'kgm': 'KGM', 'kg': 'KGM',
                'litro': 'LTR', 'ltr': 'LTR', 'l': 'LTR',
                'metro': 'MTR', 'mtr': 'MTR', 'm': 'MTR',
                'servicio': 'ZZ', 'zz': 'ZZ',
                'paquete': 'PK', 'pk': 'PK',
            }

            for row_idx, row in enumerate(sheet.iter_rows(min_row=2, values_only=True), start=2):
                # Omitir filas completamente vacías
                if all(cell is None or str(cell).strip() == '' for cell in row):
                    continue

                try:
                    codigo_val = row[headers['codigo']]
                    desc_val = row[headers['descripcion']]
                    uni_val = row[headers['unidad_medida']]
                    precio_val = row[headers['precio_unitario']]
                    afecto_val = row[headers['afecto_igv']]

                    if not codigo_val or not desc_val or precio_val is None:
                        errores.append(f"Fila {row_idx}: Faltan datos obligatorios.")
                        continue

                    codigo = str(codigo_val).strip()
                    descripcion = str(desc_val).strip()

                    # Procesar unidad de medida
                    unidad_medida = 'NIU'
                    if uni_val is not None:
                        u_clean = str(uni_val).strip().lower()
                        unidad_medida = unidad_map.get(u_clean, 'NIU')
                        for choice_code, _ in Producto.UnidadMedida.choices:
                            if u_clean.upper() == choice_code:
                                unidad_medida = choice_code
                                break

                    # Procesar precio unitario
                    try:
                        precio_unitario = Decimal(str(precio_val).strip())
                        if precio_unitario < Decimal('0.01'):
                            errores.append(f"Fila {row_idx}: El precio unitario debe ser mayor a 0.")
                            continue
                    except Exception:
                        errores.append(f"Fila {row_idx}: Precio unitario inválido.")
                        continue

                    # Procesar afecto_igv
                    afecto_igv = True
                    if afecto_val is not None:
                        a_clean = str(afecto_val).strip().lower()
                        if a_clean in ['no', 'false', '0', 'f', 'inafecto']:
                            afecto_igv = False
                        else:
                            afecto_igv = True

                    # Actualizar o crear producto
                    producto, created = Producto.objects.update_or_create(
                        codigo=codigo,
                        defaults={
                            'descripcion': descripcion,
                            'unidad_medida': unidad_medida,
                            'precio_unitario': precio_unitario,
                            'afecto_igv': afecto_igv,
                            'activo': True
                        }
                    )
                    if created:
                        productos_creados += 1
                    else:
                        productos_actualizados += 1

                except Exception as e:
                    errores.append(f"Fila {row_idx}: Error al procesar ({str(e)}).")

            if productos_creados or productos_actualizados:
                msg = f"Se importaron con éxito: {productos_creados} productos nuevos y {productos_actualizados} actualizados."
                if errores:
                    msg += f" Hubo observaciones en {len(errores)} filas."
                messages.success(request, msg)
            else:
                if errores:
                    messages.error(request, f"No se pudo importar. Primer error: {errores[0]}")
                else:
                    messages.warning(request, "El archivo Excel no contenía filas válidas para procesar.")

        except Exception as e:
            messages.error(request, f"Error al procesar el archivo Excel: {str(e)}")

    return redirect('producto-lista')
