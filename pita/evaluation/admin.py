from django.contrib import admin

from .models import EvaluationRun


@admin.register(EvaluationRun)
class EvaluationRunAdmin(admin.ModelAdmin):
    list_display = ('evaluation', 'status', 'backend', 'host', 'started_at', 'finished_at')
    list_filter = ('evaluation', 'status')
    readonly_fields = [f.name for f in EvaluationRun._meta.fields]
