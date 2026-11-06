from django.contrib import admin
from django.contrib.auth.models import Group as BuiltInGroup
from django.contrib.auth.admin import GroupAdmin as BaseGroupAdmin, UserAdmin
from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType
from django.utils.html import format_html
from django.utils import timezone
from django.urls import reverse
from django.db.models import Count, Q
from django.contrib import messages
from django.http import HttpResponseRedirect
from guardian.admin import GuardedModelAdmin
from guardian.shortcuts import get_objects_for_user
from .models import (
    Users, Group,
    ContentSource, RawContent, AwarenessContent,
    Quiz, QuizQuestion, QuizChoice, QuizAttempt,
    EmailCampaign, EmailDelivery, UserContentInteraction,
)


class GroupAdmin(GuardedModelAdmin, BaseGroupAdmin):
    """Enhanced Group Admin with better organization and permissions"""
    list_display = ('name', 'admin_display', 'superadmin_display', 'member_count', 'permission_count')
    search_fields = ('name', 'admin__email', 'superadmin__email')
    list_filter = ('admin__role', 'superadmin__role')
    filter_horizontal = ('permissions',)
    ordering = ('name',)

    fieldsets = (
        ('Basic Information', {
            'fields': ('name',)
        }),
        ('Management', {
            'fields': ('admin', 'superadmin'),
            'description': 'Assign administrators for this group'
        }),
        ('Permissions', {
            'fields': ('permissions',),
            'classes': ('collapse',),
            'description': 'Specific permissions for this group'
        }),
    )

    def admin_display(self, obj):
        if obj.admin:
            return format_html(
                '<span style="color: #0066cc;"><strong>{}</strong></span>',
                obj.admin.email
            )
        return format_html('<span style="color: #999;">{}</span>', 'No admin assigned')
    admin_display.short_description = 'Admin'

    def superadmin_display(self, obj):
        if obj.superadmin:
            return format_html(
                '<span style="color: #cc0000;"><strong>{}</strong></span>',
                obj.superadmin.email
            )
        return format_html('<span style="color: #999;">{}</span>', 'No superadmin assigned')
    superadmin_display.short_description = 'Super Admin'

    def member_count(self, obj):
        count = obj.user_set.count()
        return format_html('<span class="badge">{}</span>', count)
    member_count.short_description = 'Members'

    def permission_count(self, obj):
        count = obj.permissions.count()
        return format_html('<span class="badge">{}</span>', count)
    permission_count.short_description = 'Permissions'

    def has_module_permission(self, request):
        if super().has_module_permission(request):
            return True
        return self.get_model_objects(request).exists()

    def get_queryset(self, request):
        if request.user.is_superuser:
            return super().get_queryset(request).select_related('admin', 'superadmin')
        data = self.get_model_objects(request)
        return data.select_related('admin', 'superadmin')

    def get_model_objects(self, request, action=None, klass=None):
        opts = self.opts
        actions = [action] if action else ['view', 'change', 'delete']
        klass = klass if klass else opts.model
        model_name = klass._meta.model_name
        return get_objects_for_user(
            user=request.user,
            perms=[f'{opts.app_label}.{perm}_{model_name}' for perm in actions],
            klass=klass,
            any_perm=True
        )

    def has_permission(self, request, obj, action):
        opts = self.opts
        code_name = f'{action}_{opts.model_name}'
        if obj:
            return request.user.has_perm(f'{opts.app_label}.{code_name}', obj)
        else:
            return self.get_model_objects(request).exists()

    def has_view_permission(self, request, obj=None):
        return self.has_permission(request, obj, 'view')

    def has_change_permission(self, request, obj=None):
        return self.has_permission(request, obj, 'change')

    def has_delete_permission(self, request, obj=None):
        return self.has_permission(request, obj, 'delete')


@admin.register(Users)
class UsersAdmin(GuardedModelAdmin, UserAdmin):
    """Enhanced Users Admin with comprehensive user management"""
    list_display = (
        'id', 'email', 'role_badge', 'phone_display', 'status_display',
        'last_login', 'date_joined_display'
    )
    search_fields = ('email', 'phonenumber')
    list_filter = ('role', 'is_active', 'is_staff',
                   'is_superuser', 'created_at')
    ordering = ('-created_at',)
    filter_horizontal = ('user_permissions', 'groups')

    fieldsets = (
        ('Account Information', {
            'fields': ('email', 'password'),
            'classes': ('wide',)
        }),
        ('Personal Information', {
            'fields': ('role', 'phonenumber'),
            'classes': ('wide',)
        }),
        ('Group Membership', {
            'fields': ('groups',),
            'classes': ('collapse',)
        }),
        ('Permissions & Status', {
            'fields': ('is_active', 'is_staff', 'is_superuser', 'user_permissions'),
            'classes': ('collapse',),
            'description': 'Detailed permissions and account status'
        }),
        ('Important Dates', {
            'fields': ('last_login', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

    add_fieldsets = (
        ('Create New User', {
            'classes': ('wide',),
            'fields': ('email', 'password1', 'password2', 'role', 'phonenumber', 'groups'),
            'description': 'Enter the user information below'
        }),
        ('Permissions (Optional)', {
            'classes': ('collapse',),
            'fields': ('user_permissions',),
        }),
    )

    readonly_fields = ('created_at', 'updated_at', 'last_login')

    def role_badge(self, obj):
        colors = {
            'child': '#28a745',
            'parent': '#ffc107',
            'analyst': '#dc3545'
        }
        return format_html(
            '<span style="background-color: {}; color: white; padding: 2px 8px; border-radius: 3px; font-size: 11px;">{}</span>',
            colors.get(obj.role, '#6c757d'),
            obj.get_role_display()
        )
    role_badge.short_description = 'Role'

    def phone_display(self, obj):
        if obj.phonenumber:
            return format_html('<span style="font-family: monospace;">{}</span>', obj.phonenumber)
        return format_html('<span style="color: #999;">{}</span>', 'Not provided')
    phone_display.short_description = 'Phone'

    def status_display(self, obj):
        if obj.is_active:
            if obj.is_superuser:
                return format_html('<span style="color: {};">●</span> Super User', '#dc3545')
            elif obj.is_staff:
                return format_html('<span style="color: {};">●</span> Staff', '#ffc107')
            else:
                return format_html('<span style="color: {};">●</span> Active', '#28a745')
        return format_html('<span style="color: {};">●</span> Inactive', '#6c757d')
    status_display.short_description = 'Status'

    def date_joined_display(self, obj):
        return timezone.localtime(obj.created_at).strftime('%b %d, %Y')
    date_joined_display.short_description = 'Date Joined'

    def save_model(self, request, obj, form, change):
        if obj.role == 'admin':
            obj.is_staff = True
            obj.is_superuser = False
        elif obj.role == 'superadmin':
            obj.is_staff = True
            obj.is_superuser = True
        else:
            obj.is_staff = False
            obj.is_superuser = False
        if not change:
            obj.is_active = True
        super().save_model(request, obj, form, change)

    def save_related(self, request, form, formsets, change):
        super().save_related(request, form, formsets, change)
        # Django admin saves M2M (groups) here, which can overwrite the signal.
        # Re-sync so the user always ends up in the correct role group.
        from .signals import sync_user_group
        try:
            sync_user_group(form.instance)
        except Exception:
            pass

    def get_form(self, request, obj=None, **kwargs):
        form = super().get_form(request, obj, **kwargs)
        is_superuser = request.user.is_superuser

        if not is_superuser:
            form.base_fields['role'].disabled = True
            form.base_fields['is_superuser'].disabled = True
            form.base_fields['user_permissions'].disabled = True
            form.base_fields['groups'].disabled = True
        return form

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.exclude(email="anonymous@example.com").prefetch_related('groups')


# Register models with enhanced admin
admin.site.register(Group, GroupAdmin)
admin.site.unregister(BuiltInGroup)


@admin.register(ContentSource)
class ContentSourceAdmin(admin.ModelAdmin):
    list_display = ('name', 'source_type', 'threat_type', 'last_fetched', 'is_active', 'created_by')
    list_filter = ('source_type', 'threat_type', 'is_active')
    search_fields = ('name',)
    readonly_fields = ('created_at', 'updated_at', 'last_fetched')


@admin.register(RawContent)
class RawContentAdmin(admin.ModelAdmin):
    list_display = ('source', 'fetched_at', 'processed')
    list_filter = ('processed', 'source__threat_type')
    readonly_fields = ('fetched_at',)


@admin.register(AwarenessContent)
class AwarenessContentAdmin(admin.ModelAdmin):
    list_display = ('title', 'threat_type', 'engagement_type', 'status', 'created_by', 'created_at')
    list_filter = ('status', 'threat_type', 'engagement_type')
    search_fields = ('title', 'risk', 'action')
    readonly_fields = ('created_at', 'updated_at', 'reviewed_at')


@admin.register(Quiz)
class QuizAdmin(admin.ModelAdmin):
    list_display = ('title', 'question_count', 'is_active', 'created_by', 'created_at')
    list_filter = ('is_active',)


@admin.register(EmailCampaign)
class EmailCampaignAdmin(admin.ModelAdmin):
    list_display = ('subject', 'status', 'created_by', 'sent_at', 'created_at')
    list_filter = ('status',)
    readonly_fields = ('sent_at', 'created_at', 'updated_at')


admin.site.site_header = 'PITA Guard Admin'
admin.site.site_title = 'PITA Admin'
admin.site.index_title = 'Welcome to PITA Guard Administration'