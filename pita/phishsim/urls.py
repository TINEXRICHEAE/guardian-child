from django.conf import settings
from django.urls import path

from . import views

urlpatterns = [
    path(f'{settings.AWARENESS_PANEL_PREFIX}/content/<int:pk>/family/', views.panel_pack, name='panel_pack'),
    path(f'{settings.GUARDIAN_PARENT_PREFIX}/news/', views.parent_news, name='parent_news'),
    path(f'{settings.GUARDIAN_PARENT_PREFIX}/news/<int:pk>/', views.parent_news_detail, name='parent_news_detail'),
    path(f'{settings.GUARDIAN_CHILD_PREFIX}/lessons/', views.child_lessons, name='child_lessons'),
    path('learn/<int:pk>/', views.lesson, name='lesson'),
    path('p/<str:token>/', views.practice_open, name='practice_open'),
    path('stop/<str:token>/', views.practice_stop, name='practice_stop'),
]
