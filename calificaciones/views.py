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
            for i in range(8, 38):
                montos[f'monto_{i:02d}'] = request.POST.get(f'monto_{i:02d}', '0')

            factores = calcular_factores_desde_montos(montos)
            datos_anteriores = {}

            if calificacion_id:
                calif = get_object_or_404(CalificacionTributaria, id=calificacion_id)
                accion = 'MODIFICACION'
                if hasattr(calif, 'factores'):
                    datos_anteriores = {
                        'factor_08': str(calif.factores.factor_08),
                        'factor_09': str(calif.factores.factor_09),
                        'factor_10': str(calif.factores.factor_10),
                        'factor_11': str(calif.factores.factor_11),
                    }
            else:
                calif = CalificacionTributaria()
                accion = 'CREACION'

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

            AuditoriaLog.objects.create(
                calificacion=calif,
                instrumento=calif.instrumento,
                usuario=request.user.username,
                accion=accion,
                origen='MANUAL',
                detalles={
                    'secuencia': secuencia_evento,
                    'anterior': datos_anteriores,
                    'nuevo': {
                        'factor_08': str(factores['factor_08']),
                        'factor_09': str(factores['factor_09']),
                        'factor_10': str(factores['factor_10']),
                        'factor_11': str(factores['factor_11']),
                    }
                }
            )

            messages.success(request, f"Calificación de {instrumento} guardada correctamente.")
        except ValueError as err:
            messages.error(request, str(err))
        except Exception as e:
            messages.error(request, f"Error al procesar el registro: {e}")

    return redirect('mantenedor')


@login_required
def eliminar_calificacion(request, calificacion_id):
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
        if not archivo.name.endswith('.csv'):
            messages.error(request, "El archivo debe tener formato .CSV")
            return redirect('mantenedor')

        try:
            datos = archivo.read().decode('utf-8')
            lineas = csv.DictReader(io.StringIO(datos))
            registros_validos = []
            num_fila = 1

            for fila in lineas:
                num_fila += 1
                factores_fila = {}
                suma_principales = Decimal('0.00000000')

                for i in range(8, 38):
                    col = f'factor_{i:02d}'
                    if col in fila and fila[col].strip() != '':
                        valor = Decimal(fila[col].strip())
                    else:
                        valor = Decimal('0.00000000')

                    factores_fila[col] = valor
                    if 8 <= i <= 19:
                        suma_principales += valor

                if suma_principales > Decimal('1.00000000'):
                    raise ValueError(f"Error en fila {num_fila}: la suma de factores supera 1.00000000.")

                registros_validos.append((fila, factores_fila))

            for fila, factores_fila in registros_validos:
                calif, _ = CalificacionTributaria.objects.update_or_create(
                    ejercicio=int(fila['ejercicio']),
                    mercado=fila['mercado'].strip(),
                    instrumento=fila['instrumento'].strip().upper(),
                    secuencia_evento=int(fila['secuencia']),
                    origen='CSV',
                    defaults={
                        'fecha_pago': fila['fecha'],
                        'numero_dividendo': int(fila.get('dividendo', 0)),
                        'tipo_sociedad': fila.get('tipo_sociedad', 'A'),
                        'descripcion': fila.get('descripcion', 'Carga Masiva CSV'),
                        'valor_historico': Decimal(fila.get('valor_historico', '0')),
                    }
                )

                factor_obj, _ = FactorTributario.objects.get_or_create(calificacion=calif)
                for col, val in factores_fila.items():
                    setattr(factor_obj, col, val)
                factor_obj.save()

            AuditoriaLog.objects.create(
                instrumento="CARGA_LOTE",
                usuario=request.user.username,
                accion='CARGA_MASIVA',
                origen='CSV',
                detalles={'total_registros': len(registros_validos), 'archivo': archivo.name}
            )

            messages.success(request, f"Se procesaron {len(registros_validos)} calificaciones desde el archivo CSV.")
        except Exception as e:
            messages.error(request, f"Carga cancelada por error en el archivo: {e}")

    return redirect('mantenedor')