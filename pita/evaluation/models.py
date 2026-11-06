"""One row per evaluation run, so the history of every model stays visible (plan.md §11.5)."""
from django.conf import settings
from django.db import models


class EvaluationRun(models.Model):
    STATUS_RUNNING, STATUS_DONE, STATUS_UNAVAILABLE, STATUS_FAILED = 'running', 'done', 'unavailable', 'failed'
    STATUS_CHOICES = [(STATUS_RUNNING, 'Running'), (STATUS_DONE, 'Done'),
                      (STATUS_UNAVAILABLE, 'Model unavailable'), (STATUS_FAILED, 'Failed')]

    evaluation = models.CharField(max_length=40, db_index=True)   # key in services.cards.EVALUATIONS
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_RUNNING)
    dataset = models.CharField(max_length=80, blank=True)
    backend = models.CharField(max_length=80, blank=True)        # what actually answered, from guardian-ai meta
    model_id = models.CharField(max_length=200, blank=True)
    host = models.CharField(max_length=120, blank=True)
    gpu = models.CharField(max_length=200, blank=True)
    mode = models.CharField(max_length=30, blank=True)
    progress = models.CharField(max_length=120, blank=True)
    metrics = models.JSONField(default=dict, blank=True)         # headline numbers
    details = models.JSONField(default=dict, blank=True)         # breakdowns, sweep, failure examples
    error = models.TextField(blank=True)
    started_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL)
    started_at = models.DateTimeField(auto_now_add=True)
    finished_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-started_at']

    def __str__(self):
        return f'{self.evaluation} #{self.pk} ({self.status})'

    @property
    def duration_s(self):
        if self.finished_at:
            return round((self.finished_at - self.started_at).total_seconds(), 1)
        return None
