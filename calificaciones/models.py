from django.db import models
from decimal import Decimal


class CalificacionTributaria(models.Model):
    MERCADO_CHOICES = [
        ('ACN', 'Acciones'),
        ('CFI', 'CFI'),
        ('FM', 'Fondos Mutuos'),
    ]

    ORIGEN_CHOICES = [
        ('BOLSA', 'Bolsa'),
        ('CORREDOR', 'Corredor'),
        ('CSV', 'Archivo CSV'),
    ]

    TIPO_SOCIEDAD_CHOICES = [
        ('A', 'Abierta'),
        ('C', 'Cerrada'),
    ]

    ejercicio = models.IntegerField(db_index=True, help_text="Año comercial, ej: 2023, 2024")
    mercado = models.CharField(max_length=3, choices=MERCADO_CHOICES, db_index=True)
    instrumento = models.CharField(max_length=50, db_index=True, help_text="Nombre o nemotécnico, ej: Copec")
    secuencia_evento = models.BigIntegerField(help_text="Secuencia numérica superior a 10.000")
    numero_dividendo = models.IntegerField(default=0)
    fecha_pago = models.DateField()
    valor_historico = models.DecimalField(max_digits=18, decimal_places=4, default=Decimal('0.0000'))
    tipo_sociedad = models.CharField(max_length=1, choices=TIPO_SOCIEDAD_CHOICES, default='A')
    descripcion = models.CharField(max_length=255)
    acogido_isfut = models.BooleanField(default=False)
    factor_actualizacion = models.DecimalField(max_digits=10, decimal_places=8, default=Decimal('0.00000000'))
    origen = models.CharField(max_length=10, choices=ORIGEN_CHOICES, default='CORREDOR', db_index=True)

    fecha_creacion = models.DateTimeField(auto_now_add=True)
    fecha_modificacion = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('ejercicio', 'mercado', 'instrumento', 'secuencia_evento', 'origen')
        ordering = ['-ejercicio', 'instrumento']

    def __str__(self):
        return f"{self.instrumento} ({self.ejercicio}) - Sec: {self.secuencia_evento}"


class FactorTributario(models.Model):
    calificacion = models.OneToOneField(
        CalificacionTributaria,
        on_delete=models.CASCADE,
        related_name='factores'
    )

    factor_08 = models.DecimalField(max_digits=18, decimal_places=8, default=Decimal('0.00000000'))
    factor_09 = models.DecimalField(max_digits=18, decimal_places=8, default=Decimal('0.00000000'))
    factor_10 = models.DecimalField(max_digits=18, decimal_places=8, default=Decimal('0.00000000'))
    factor_11 = models.DecimalField(max_digits=18, decimal_places=8, default=Decimal('0.00000000'))
    factor_12 = models.DecimalField(max_digits=18, decimal_places=8, default=Decimal('0.00000000'))
    factor_13 = models.DecimalField(max_digits=18, decimal_places=8, default=Decimal('0.00000000'))
    factor_14 = models.DecimalField(max_digits=18, decimal_places=8, default=Decimal('0.00000000'))
    factor_15 = models.DecimalField(max_digits=18, decimal_places=8, default=Decimal('0.00000000'))
    factor_16 = models.DecimalField(max_digits=18, decimal_places=8, default=Decimal('0.00000000'))
    factor_17 = models.DecimalField(max_digits=18, decimal_places=8, default=Decimal('0.00000000'))
    factor_18 = models.DecimalField(max_digits=18, decimal_places=8, default=Decimal('0.00000000'))
    factor_19 = models.DecimalField(max_digits=18, decimal_places=8, default=Decimal('0.00000000'))

    factor_20 = models.DecimalField(max_digits=18, decimal_places=8, default=Decimal('0.00000000'))
    factor_21 = models.DecimalField(max_digits=18, decimal_places=8, default=Decimal('0.00000000'))
    factor_22 = models.DecimalField(max_digits=18, decimal_places=8, default=Decimal('0.00000000'))
    factor_23 = models.DecimalField(max_digits=18, decimal_places=8, default=Decimal('0.00000000'))
    factor_24 = models.DecimalField(max_digits=18, decimal_places=8, default=Decimal('0.00000000'))
    factor_25 = models.DecimalField(max_digits=18, decimal_places=8, default=Decimal('0.00000000'))
    factor_26 = models.DecimalField(max_digits=18, decimal_places=8, default=Decimal('0.00000000'))
    factor_27 = models.DecimalField(max_digits=18, decimal_places=8, default=Decimal('0.00000000'))
    factor_28 = models.DecimalField(max_digits=18, decimal_places=8, default=Decimal('0.00000000'))
    factor_29 = models.DecimalField(max_digits=18, decimal_places=8, default=Decimal('0.00000000'))
    factor_30 = models.DecimalField(max_digits=18, decimal_places=8, default=Decimal('0.00000000'))
    factor_31 = models.DecimalField(max_digits=18, decimal_places=8, default=Decimal('0.00000000'))
    factor_32 = models.DecimalField(max_digits=18, decimal_places=8, default=Decimal('0.00000000'))
    factor_33 = models.DecimalField(max_digits=18, decimal_places=8, default=Decimal('0.00000000'))
    factor_34 = models.DecimalField(max_digits=18, decimal_places=8, default=Decimal('0.00000000'))
    factor_35 = models.DecimalField(max_digits=18, decimal_places=8, default=Decimal('0.00000000'))
    factor_36 = models.DecimalField(max_digits=18, decimal_places=8, default=Decimal('0.00000000'))
    factor_37 = models.DecimalField(max_digits=18, decimal_places=8, default=Decimal('0.00000000'))

    def suma_factores_principales(self):
        return sum([
            self.factor_08, self.factor_09, self.factor_10, self.factor_11,
            self.factor_12, self.factor_13, self.factor_14, self.factor_15,
            self.factor_16, self.factor_17, self.factor_18, self.factor_19
        ])


class AuditoriaLog(models.Model):
    calificacion = models.ForeignKey(
        CalificacionTributaria,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='auditorias'
    )
    instrumento = models.CharField(max_length=50, db_index=True)
    usuario = models.CharField(max_length=150, default='sistema')
    accion = models.CharField(max_length=20)
    origen = models.CharField(max_length=20)
    fecha_hora = models.DateTimeField(auto_now_add=True, db_index=True)
    detalles = models.JSONField(default=dict)

    class Meta:
        ordering = ['-fecha_hora']

    def __str__(self):
        return f"[{self.fecha_hora}] {self.accion} sobre {self.instrumento} por {self.usuario}"