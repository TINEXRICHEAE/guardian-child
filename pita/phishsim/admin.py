from django.contrib import admin

from .models import PracticeDelivery, TopicPack


@admin.register(TopicPack)
class TopicPackAdmin(admin.ModelAdmin):
    list_display = ('child_title', 'content', 'status', 'generated_by', 'published_at')
    list_filter = ('status',)


@admin.register(PracticeDelivery)
class PracticeDeliveryAdmin(admin.ModelAdmin):
    list_display = ('pack', 'child', 'channel', 'status', 'sent_at', 'clicked_at', 'lesson_viewed_at', 'reported_at')
    list_filter = ('status', 'channel', 'automated')
    readonly_fields = ('token',)
