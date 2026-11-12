import io
import time
from decimal import Decimal
from django.test import TestCase, Client
from django.contrib.auth.models import User, Group
from django.urls import reverse
from .models import CalificacionTributaria, AuditoriaLog
from .services import calcular_factores_desde_montos

# Create your tests here.

class NuamPruebas(TestCase):
    def setUp(self):
        self.client = Client()
        self.grupo_analista = Group.objects.create(name='Analista Tributario')
        self.grupo_consulta = Group.objects.create(name='Consulta')

        self.user_analista = User.objects.create_user(username='analista', password='Password123!')
        self.user_analista.groups.add(self.grupo_analista)

        self.user_consulta = User.objects.create_user(username='consulta', password='Password123!')
        self.user_consulta.groups.add(self.grupo_consulta)

    def test_calculo_ocho_decimales(self):
        montos = {'monto_08': '8000000', 'monto_09': '2000000'}
        factores = calcular_factores_desde_montos(montos)
        self.assertEqual(factores['factor_08'], Decimal('0.80000000'))
        self.assertEqual(factores['factor_09'], Decimal('0.20000000'))

    def test_division_por_cero(self):
        factores = calcular_factores_desde_montos({})
        self.assertEqual(factores['factor_08'], Decimal('0.00000000'))

    def test_carga_csv_valida(self):
        self.client.login(username='analista', password='Password123!')
        contenido = (
            "ejercicio,mercado,instrumento,fecha,secuencia,factor_08,factor_09\n"
            "2024,ACN,COPEC,2024-05-15,15420,0.80000000,0.20000000\n"
            "2024,ACN,CHILE,2024-04-18,12450,0.65000000,0.35000000\n"
        )
        archivo = io.BytesIO(contenido.encode('utf-8'))
        archivo.name = 'datos_nuam.csv'

        response = self.client.post(reverse('carga_masiva_csv'), {'archivo_csv': archivo})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(CalificacionTributaria.objects.count(), 2)
        self.assertTrue(AuditoriaLog.objects.filter(accion='CARGA_MASIVA').exists())

    def test_carga_csv_invalida_no_guarda(self):
        self.client.login(username='analista', password='Password123!')
        contenido = (
            "ejercicio,mercado,instrumento,fecha,secuencia,factor_08,factor_09\n"
            "2024,ACN,COPEC,2024-05-15,15420,0.80000000,0.20000000\n"
            "2024,ACN,CMPC,2024-05-15,15421,0.90000000,0.30000000\n"
        )
        archivo = io.BytesIO(contenido.encode('utf-8'))
        archivo.name = 'error_nuam.csv'

        self.client.post(reverse('carga_masiva_csv'), {'archivo_csv': archivo})
        self.assertEqual(CalificacionTributaria.objects.count(), 0)

    def test_permiso_solo_consulta(self):
        self.client.login(username='consulta', password='Password123!')
        response = self.client.post(reverse('guardar_calificacion'), {
            'ejercicio': '2024',
            'mercado': 'ACN',
            'instrumento': 'FALABELLA',
            'secuencia_evento': '20001',
            'fecha_pago': '2024-06-01',
            'descripcion': 'Intento sin permiso',
            'monto_08': '1000',
        })
        self.assertEqual(response.status_code, 302)
        self.assertEqual(CalificacionTributaria.objects.count(), 0)

    def test_rendimiento_grilla(self):
        self.client.login(username='analista', password='Password123!')
        lista = []
        for i in range(1000):
            lista.append(CalificacionTributaria(
                ejercicio=2024,
                mercado='ACN',
                instrumento=f'INST{i}',
                secuencia_evento=20000 + i,
                fecha_pago='2024-05-01',
                descripcion='Prueba carga'
            ))
        CalificacionTributaria.objects.bulk_create(lista)

        inicio = time.time()
        response = self.client.get(reverse('mantenedor'))
        duracion_ms = (time.time() - inicio) * 1000

        self.assertEqual(response.status_code, 200)
        self.assertLess(duracion_ms, 1500)