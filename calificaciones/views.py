import csv
import io
from decimal import Decimal
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from .models import CalificacionTributaria, FactorTributario, AuditoriaLog
from .services import calcular_factores_desde_montos


def puede_editar(user):
    if user.is_superuser or user.is_staff:
        return True
    es_admin = user.groups.filter(name='Administrador').exists()
    es_analista = user.groups.filter(name='Analista Tributario').exists()
    return es_admin or es_analista

def inicio(request):
    return render(request, 'calificaciones/index.html')

@login_required
def mantenedor_calificaciones(request):
    query = CalificacionTributaria.objects.select_related('factores').all()

    mercado = request.GET.get('mercado')
    origen = request.GET.get('origen')
    ejercicio = request.GET.get('ejercicio')

    if mercado:
        query = query.filter(mercado=mercado)
    if origen:
        query = query.filter(origen=origen)
    if ejercicio:
        query = query.filter(ejercicio=ejercicio)

    auditorias = AuditoriaLog.objects.all()[:25]

    context = {
        'calificaciones': query,
        'auditorias': auditorias,
        'mercado_sel': mercado or '',
        'origen_sel': origen or '',
        'ejercicio_sel': ejercicio or '',
        'es_editor': puede_editar(request.user),
    }
    return render(request, 'calificaciones/mantenedor.html', context)


@login_required
def guardar_calificacion(request):
    if not puede_editar(request.user):
        messages.error(request, "No tiene permisos para crear o modificar registros.")
        return redirect('mantenedor')

    if request.method == 'POST':
        calificacion_id = request.POST.get('calificacion_id')
        try:
            ejercicio = int(request.POST['ejercicio'])
            mercado = request.POST['mercado']
            instrumento = request.POST['instrumento'].strip().upper()
            secuencia_evento = int(request.POST['secuencia_evento'])
            fecha_pago = request.POST['fecha_pago']
            descripcion = request.POST['descripcion']
            acogido_isfut = request.POST.get('acogido_isfut') == 'on'
            tipo_sociedad = request.POST.get('tipo_sociedad', 'A')

            if secuencia_evento <= 10000:
                messages.error(request, "La secuencia de evento debe ser superior a 10.000.")
                return redirect('mantenedor')

            montos = {}
            tiene_montos_nuevos = False
            for i in range(8, 38):
                val_str = request.POST.get(f'monto_{i:02d}', '0') or '0'
                montos[f'monto_{i:02d}'] = val_str
                if Decimal(str(val_str)) > 0:
                    tiene_montos_nuevos = True

            datos_anteriores = {}

            if calificacion_id:
                calif = get_object_or_404(CalificacionTributaria, id=calificacion_id)
                accion = 'MODIFICACION'
                if hasattr(calif, 'factores'):
                    for i in range(8, 38):
                        col = f'factor_{i:02d}'
                        val_actual = getattr(calif.factores, col)
                        if val_actual > 0:
                            datos_anteriores[col] = str(val_actual)

                # Si edita cabecera sin ingresar montos nuevos, conserva sus factores actuales
                if tiene_montos_nuevos or not hasattr(calif, 'factores'):
                    factores = calcular_factores_desde_montos(montos)
                else:
                    factores = {f'factor_{i:02d}': getattr(calif.factores, f'factor_{i:02d}') for i in range(8, 38)}
            else:
                calif = CalificacionTributaria()
                accion = 'CREACION'
                factores = calcular_factores_desde_montos(montos)

            calif.ejercicio = ejercicio
            calif.mercado = mercado
            calif.instrumento = instrumento
            calif.secuencia_evento = secuencia_evento
            calif.fecha_pago = fecha_pago
            calif.descripcion = descripcion
            calif.acogido_isfut = acogido_isfut
            calif.tipo_sociedad = tipo_sociedad
            calif.origen = 'CORREDOR'
            calif.save()

            factor_obj, _ = FactorTributario.objects.get_or_create(calificacion=calif)
            for k, v in factores.items():
                setattr(factor_obj, k, v)
            factor_obj.save()

            datos_nuevos = {k: str(v) for k, v in factores.items() if v > 0}

            AuditoriaLog.objects.create(
                calificacion=calif,
                instrumento=calif.instrumento,
                usuario=request.user.username,
                accion=accion,
                origen='MANUAL',
                detalles={
                    'secuencia': secuencia_evento,
                    'anterior': datos_anteriores,
                    'nuevo': datos_nuevos,
                }
            )

            messages.success(request, f"Calificación de {instrumento} guardada correctamente.")
        except ValueError as err:
            messages.error(request, str(err))
        except Exception:
            messages.error(request, "No se pudo guardar el registro. Verifique que los datos ingresados sean válidos.")

    return redirect('mantenedor')


@login_required
def eliminar_calificacion(request, calificacion_id):
    if request.method != 'POST':
        return redirect('mantenedor')

    if not puede_editar(request.user):
        messages.error(request, "No tiene permisos para eliminar registros.")
        return redirect('mantenedor')

    calif = get_object_or_404(CalificacionTributaria, id=calificacion_id)
    instrumento = calif.instrumento

    AuditoriaLog.objects.create(
        calificacion=None,
        instrumento=instrumento,
        usuario=request.user.username,
        accion='ELIMINACION',
        origen='MANUAL',
        detalles={'ejercicio': calif.ejercicio, 'secuencia': calif.secuencia_evento}
    )
    calif.delete()

    messages.success(request, f"Calificación de {instrumento} eliminada exitosamente.")
    return redirect('mantenedor')


@login_required
def carga_masiva_csv(request):
    if not puede_editar(request.user):
        messages.error(request, "No tiene permisos para realizar carga masiva.")
        return redirect('mantenedor')

    if request.method == 'POST' and request.FILES.get('archivo_csv'):
        archivo = request.FILES['archivo_csv']
        if not archivo.name.lower().endswith('.csv'):
            messages.error(request, "Formato inválido: el archivo debe tener extensión .CSV")
            return redirect('mantenedor')

        try:
            datos = archivo.read().decode('utf-8')
            lineas = csv.DictReader(io.StringIO(datos))

            columnas_requeridas = {'ejercicio', 'mercado', 'instrumento', 'fecha', 'secuencia'}
            if not lineas.fieldnames or not columnas_requeridas.issubset(set(lineas.fieldnames)):
                messages.error(
                    request,
                    "El archivo CSV no tiene el formato pedido. "
                    "Debe incluir las columnas: ejercicio, mercado, instrumento, fecha, secuencia."
                )
                return redirect('mantenedor')

            registros_validos = []
            duplicados = []
            num_fila = 1

            for fila in lineas:
                num_fila += 1
                ejercicio = int(fila['ejercicio'])
                mercado = fila['mercado'].strip().upper()
                instrumento = fila['instrumento'].strip().upper()
                secuencia = int(fila['secuencia'])

                existe = CalificacionTributaria.objects.filter(
                    ejercicio=ejercicio,
                    mercado=mercado,
                    instrumento=instrumento,
                    secuencia_evento=secuencia,
                    origen='CSV'
                ).exists()

                if existe:
                    duplicados.append(f"{instrumento} (Sec. {secuencia})")
                    continue

                factores_fila = {}
                suma_principales = Decimal('0.00000000')

                for i in range(8, 38):
                    col = f'factor_{i:02d}'
                    if col in fila and fila[col] and fila[col].strip() != '':
                        valor = Decimal(fila[col].strip())
                    else:
                        valor = Decimal('0.00000000')

                    factores_fila[col] = valor
                    if 8 <= i <= 19:
                        suma_principales += valor

                if suma_principales > Decimal('1.00000000'):
                    raise ValueError(f"Fila {num_fila} ({instrumento}): la suma de factores 8-19 supera 1.00000000.")

                registros_validos.append((fila, factores_fila))

            for fila, factores_fila in registros_validos:
                calif = CalificacionTributaria.objects.create(
                    ejercicio=int(fila['ejercicio']),
                    mercado=fila['mercado'].strip().upper(),
                    instrumento=fila['instrumento'].strip().upper(),
                    secuencia_evento=int(fila['secuencia']),
                    origen='CSV',
                    fecha_pago=fila['fecha'].strip(),
                    numero_dividendo=int(fila.get('dividendo') or 0),
                    tipo_sociedad=(fila.get('tipo_sociedad') or 'A').strip(),
                    descripcion=(fila.get('descripcion') or 'Carga Masiva CSV').strip(),
                    valor_historico=Decimal(fila.get('valor_historico') or '0'),
                )

                factor_obj = FactorTributario.objects.create(calificacion=calif)
                for col, val in factores_fila.items():
                    setattr(factor_obj, col, val)
                factor_obj.save()

            if registros_validos:
                AuditoriaLog.objects.create(
                    instrumento="CARGA_LOTE",
                    usuario=request.user.username,
                    accion='CARGA_MASIVA',
                    origen='CSV',
                    detalles={
                        'archivo': archivo.name,
                        'guardados': len(registros_validos),
                        'duplicados_omitidos': duplicados
                    }
                )
                messages.success(
                    request,
                    f"Carga completada: se guardaron {len(registros_validos)} registros nuevos."
                )

            if duplicados:
                messages.warning(
                    request,
                    f"Se omitieron {len(duplicados)} registros duplicados ya existentes: {', '.join(duplicados)}."
                )

            if not registros_validos and not duplicados:
                messages.warning(request, "El archivo CSV no contiene filas para procesar.")

        except ValueError as err:
            messages.error(request, f"Error de validación en el archivo CSV: {err}")
        except Exception as e:
            messages.error(request, f"El archivo CSV no cumple con el formato válido ({e}).")

    return redirect('mantenedor')