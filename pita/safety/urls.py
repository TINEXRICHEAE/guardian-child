from django.conf import settings
from django.urls import include, path

from . import views

urlpatterns = [
    path(f'{settings.GUARDIAN_PARENT_PREFIX}/', include([
        path('', views.parent_home, name='parent_home'),
        path('children/add/', views.child_add, name='child_add'),
        path('children/<int:pk>/edit/', views.child_edit, name='child_edit'),
        path('children/<int:pk>/consent/', views.child_consent, name='child_consent'),
        path('children/<int:pk>/code/', views.pairing_code, name='pairing_code'),
        path('children/<int:pk>/remove/', views.child_remove, name='child_remove'),
        path('alerts/', views.parent_alerts, name='parent_alerts'),
        path('settings/', views.parent_settings, name='parent_settings'),
        path('check/', views.parent_check, name='parent_check'),
        path('check/<int:pk>/', views.parent_result, name='parent_result'),
    ])),
    path('help/', views.help_page, name='help'),
    path('privacy/', views.privacy_page, name='privacy'),
    path('pair/', views.pair, name='pair'),
    path(f'{settings.GUARDIAN_CHILD_PREFIX}/', include([
        path('', views.child_home, name='child_home'),
        path('check/', views.child_check, name='child_check'),
        path('check/<int:pk>/', views.child_result, name='child_result'),
        path('history/', views.child_history, name='child_history'),
        path('report/', views.child_report, name='child_report'),
        path('family/', views.child_family, name='child_family'),
    ])),
]
