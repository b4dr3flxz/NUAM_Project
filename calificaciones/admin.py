from django.contrib import admin
from .models import CalificacionTributaria, FactorTributario, AuditoriaLog

# Register your models here.

admin.site.register(CalificacionTributaria)
admin.site.register(FactorTributario)
admin.site.register(AuditoriaLog)