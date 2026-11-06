from django.conf import settings
from django.urls import path

from . import views

P = settings.AWARENESS_PANEL_PREFIX
urlpatterns = [
    path(f'{P}/evaluation/', views.evaluation_page, name='evaluation_page'),
    path(f'{P}/evaluation/run/', views.evaluation_run, name='evaluation_run'),
    path(f'{P}/evaluation/status/', views.evaluation_status, name='evaluation_status'),
    path(f'{P}/evaluation/<int:pk>/', views.evaluation_detail, name='evaluation_detail'),
]
