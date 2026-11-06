from django.conf import settings
from django.urls import path, include
from . import account_views, views

urlpatterns = [
    # Home (always at root)
    path('', views.home, name='home'),

    # Auth + API endpoints
    path(f'{settings.AWARENESS_AUTH_PREFIX}/', include([
        path('register/', views.register_user, name='register_user'),
        path('login/', views.login_user, name='login_user'),
        path('security/', account_views.security, name='account_security'),
        path('password/reset/', account_views.PasswordReset.as_view(), name='password_reset'),
        path('password/reset/sent/', account_views.PasswordResetDone.as_view(), name='password_reset_done'),
        path('password/reset/<uidb64>/<token>/', account_views.PasswordResetConfirm.as_view(), name='password_reset_confirm'),
        path('password/reset/complete/', account_views.PasswordResetComplete.as_view(), name='password_reset_complete'),
        path('logout/', views.logout_user, name='logout_user'),
        path('check/', views.check_auth, name='check_auth'),
        path('profile/', views.user_profile, name='user_profile'),
        path('picture/', views.upload_profile_picture, name='upload_profile_picture'),
        path('account/delete/', views.delete_account, name='delete_account'),
        path('api/csrf/', views.get_csrf_token, name='get_csrf'),
    ])),

    # Staff section
    path(f'{settings.AWARENESS_STAFF_PREFIX}/', include([
        path('library/', views.library, name='library'),
        path('library/<int:pk>/', views.content_view, name='content_view'),
        path('quizzes/', views.quizzes, name='quizzes'),
        path('quizzes/<int:pk>/', views.take_quiz, name='take_quiz'),
        path('quizzes/result/<int:attempt_pk>/', views.quiz_result, name='quiz_result'),
        path('quizzes/review/<int:attempt_pk>/', views.quiz_review, name='quiz_review'),
        path('progress/', views.progress, name='progress'),
    ])),

    # Admin panel
    path(f'{settings.AWARENESS_PANEL_PREFIX}/', include([
        path('dashboard/', views.panel_dashboard, name='panel_dashboard'),
        # Sources
        path('sources/', views.panel_sources, name='panel_sources'),
        path('sources/add/', views.panel_add_source, name='panel_add_source'),
        path('sources/<int:pk>/ingest/', views.panel_ingest_source, name='panel_ingest_source'),
        path('sources/<int:pk>/delete/', views.panel_delete_source, name='panel_delete_source'),
        # Raw content
        path('raw/', views.panel_raw_contents, name='panel_raw_contents'),
        path('raw/<int:pk>/', views.panel_raw_detail, name='panel_raw_detail'),
        path('raw/<int:pk>/delete/', views.panel_delete_raw, name='panel_delete_raw'),
        path('raw/<int:pk>/transform/', views.panel_transform_raw, name='panel_transform_raw'),
        # Awareness content
        path('content/', views.panel_content_list, name='panel_content_list'),
        path('content/<int:pk>/', views.panel_content_detail, name='panel_content_detail'),
        path('content/<int:pk>/approve/', views.panel_approve_content, name='panel_approve_content'),
        path('content/<int:pk>/reject/', views.panel_reject_content, name='panel_reject_content'),
        path('content/<int:pk>/delete/', views.panel_delete_content, name='panel_delete_content'),
        path('content/<int:pk>/engagement/', views.panel_content_engagement, name='panel_content_engagement'),
        # Campaigns
        path('campaigns/', views.panel_campaigns, name='panel_campaigns'),
        path('campaigns/create/<int:content_pk>/', views.panel_create_campaign, name='panel_create_campaign'),
        path('campaigns/<int:pk>/', views.panel_campaign_detail, name='panel_campaign_detail'),
        path('campaigns/<int:pk>/send/', views.panel_send_campaign, name='panel_send_campaign'),
        path('campaigns/<int:pk>/targets/', views.panel_campaign_targets, name='panel_campaign_targets'),
        # Analytics
        path('analytics/', views.panel_analytics, name='panel_analytics'),
        path('analytics/staff/', views.analytics_staff, name='analytics_staff'),
        path('analytics/content/', views.analytics_content, name='analytics_content'),
        path('analytics/content/<int:pk>/', views.analytics_content_detail, name='analytics_content_detail'),
        path('analytics/campaigns/', views.analytics_campaigns, name='analytics_campaigns'),
        path('analytics/campaigns/<int:pk>/', views.analytics_campaign_detail, name='analytics_campaign_detail'),
        path('analytics/emails/', views.analytics_emails, name='analytics_emails'),
        path('analytics/threats/<str:threat_type>/', views.analytics_threat, name='analytics_threat'),
        path('analytics/quizzes/', views.analytics_quizzes, name='analytics_quizzes'),
        path('analytics/report/', views.analytics_report, name='analytics_report'),
    ])),
]
