from django.db.models.signals import post_save, post_migrate
from django.dispatch import receiver
from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType
from .models import Users, Group, ROLE_ANALYST, ROLE_CHILD, ROLE_PARENT

_ANALYST_CODENAMES = [
    'view_panel', 'manage_sources', 'manage_content', 'manage_campaigns', 'view_analytics',
    'view_intel', 'manage_simulations', 'export_intel',
]
_ROLE_GROUPS = {ROLE_ANALYST: 'Analysts', ROLE_PARENT: 'Parents', ROLE_CHILD: 'Children'}
# Not a role group: analysts are added to it by hand, and role syncing never removes them.
SAFEGUARDING_GROUP = 'Safeguarding'


def _get_awareness_permissions(codenames):
    from django.apps import apps
    AwarenessContent = apps.get_model('awarenessapp', 'AwarenessContent')
    ct = ContentType.objects.get_for_model(AwarenessContent)
    return Permission.objects.filter(content_type=ct, codename__in=codenames)


def sync_user_group(user):
    """Assign user to exactly one role group; remove them from the other role groups."""
    target_name = _ROLE_GROUPS.get(user.role)
    if not target_name:
        return
    for g in Group.objects.filter(name__in=[n for n in _ROLE_GROUPS.values() if n != target_name]):
        user.groups.remove(g)
    target_group, _ = Group.objects.get_or_create(name=target_name)
    user.groups.add(target_group)
    if user.role != ROLE_ANALYST:
        safeguarding = Group.objects.filter(name=SAFEGUARDING_GROUP).first()
        if safeguarding:
            user.groups.remove(safeguarding)


@receiver(post_save, sender=Users)
def assign_user_to_group(sender, instance, created, **kwargs):
    if instance.email == 'anonymous@example.com':
        return
    update_fields = kwargs.get('update_fields')
    # Sync on creation, full save, or when role field is explicitly updated
    if created or update_fields is None or 'role' in (update_fields or []):
        try:
            sync_user_group(instance)
        except Exception:
            pass


@receiver(post_migrate)
def setup_group_permissions(sender, **kwargs):
    """Create the role groups and the Safeguarding group with their permissions; sync existing users."""
    if sender.name != 'awarenessapp':
        return
    try:
        analysts, _ = Group.objects.get_or_create(name='Analysts')
        analysts.permissions.set(_get_awareness_permissions(_ANALYST_CODENAMES))

        safeguarding, _ = Group.objects.get_or_create(name=SAFEGUARDING_GROUP)
        safeguarding.permissions.set(_get_awareness_permissions(['view_confidential_reports']))

        Group.objects.get_or_create(name='Parents')
        Group.objects.get_or_create(name='Children')

        for user in Users.objects.exclude(email='anonymous@example.com'):
            sync_user_group(user)
    except Exception:
        pass


def create_anonymous_user(sender, **kwargs):
    Users.objects.create_anonymous_user()
