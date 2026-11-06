from django.contrib import admin

from .models import (ChildProfile, ConsentRecord, GuardianChildLink, GuardianPreference, IncidentReport,
                     PairingCode, ParentAlert, Submission)


@admin.register(ChildProfile)
class ChildProfileAdmin(admin.ModelAdmin):
    list_display = ('pseudonym', 'nickname', 'age_band', 'district', 'is_paired', 'email_blocked', 'created_at')
    list_filter = ('age_band', 'email_blocked')
    search_fields = ('pseudonym', 'nickname')


@admin.register(GuardianChildLink)
class GuardianChildLinkAdmin(admin.ModelAdmin):
    list_display = ('guardian', 'child', 'active', 'linked_at')
    list_filter = ('active',)


@admin.register(PairingCode)
class PairingCodeAdmin(admin.ModelAdmin):
    list_display = ('child', 'guardian', 'expires_at', 'used_at')
    readonly_fields = ('code_hash',)


@admin.register(ConsentRecord)
class ConsentRecordAdmin(admin.ModelAdmin):
    list_display = ('child', 'parent', 'kind', 'told_child', 'granted_at', 'revoked_at')
    list_filter = ('kind',)


@admin.register(Submission)
class SubmissionAdmin(admin.ModelAdmin):
    list_display = ('pk', 'submitter_role', 'input_kind', 'risk_level', 'category', 'mode', 'review_status', 'created_at')
    list_filter = ('risk_level', 'submitter_role', 'input_kind', 'mode', 'review_status')
    readonly_fields = ('content_hash', 'file_sha256', 'providers')


@admin.register(IncidentReport)
class IncidentReportAdmin(admin.ModelAdmin):
    list_display = ('pk', 'category', 'confidential', 'needs_safeguarding', 'status', 'created_at')
    list_filter = ('category', 'confidential', 'needs_safeguarding', 'status')


@admin.register(ParentAlert)
class ParentAlertAdmin(admin.ModelAdmin):
    list_display = ('parent', 'child', 'severity', 'title', 'read_at', 'created_at')


admin.site.register(GuardianPreference)
