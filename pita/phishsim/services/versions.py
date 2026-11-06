"""Which wording a child gets, parents' own edits, publishing, and parents asking for a child version (plan.md §8.0).

The analyst's pack is the original. A parent may reword the child lesson and practice message for their own children;
the edit must pass the same automatic safety screen, and analysts can revert it at any time.
"""
import logging

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils import timezone

from awarenessapp.services.email_service import _send_with_retry, _strip_html
from awarenessapp.services.text import no_em_dash
from safety.models import GuardianChildLink

from ..models import ChildVersionRequest, ParentLessonEdit, TopicPack
from .generate import _BANNED, _repair_link, _safety_screen, fit_field

logger = logging.getLogger(__name__)
FIELDS = ('child_title', 'child_story', 'child_points', 'child_action', 'practice_subject', 'practice_body')


def _original(pack) -> dict:
    return {f: getattr(pack, f) for f in FIELDS} | {'edited': False, 'edit': None}


def _from_edit(edit) -> dict:
    return {f: getattr(edit, f) for f in FIELDS} | {'edited': True, 'edit': edit}


def active_edit(pack, parent):
    if pack is None or parent is None:
        return None
    return ParentLessonEdit.objects.filter(pack=pack, parent=parent, status=ParentLessonEdit.STATUS_ACTIVE).first()


def version_for_child(pack, child, delivery=None) -> dict:
    """The lesson and practice wording this child should see: the sender's edit, else a linked parent's, else the original."""
    if delivery is not None and delivery.lesson_edit_id and delivery.lesson_edit.is_active:
        return _from_edit(delivery.lesson_edit)
    if child is not None:
        parents = GuardianChildLink.objects.filter(child=child, active=True).values_list('guardian_id', flat=True)
        edit = ParentLessonEdit.objects.filter(pack=pack, parent_id__in=list(parents),
                                               status=ParentLessonEdit.STATUS_ACTIVE).first()
        if edit:
            return _from_edit(edit)
    return _original(pack)


def version_for_parent(pack, parent) -> dict:
    edit = active_edit(pack, parent)
    return _from_edit(edit) if edit else _original(pack)


def save_parent_edit(pack, parent, data) -> tuple[ParentLessonEdit | None, list[str]]:
    """Validate and save a parent's wording. Returns (edit, errors); nothing is saved when there are errors."""
    def text(name):
        return fit_field(ParentLessonEdit, name, data.get(name) or '')[0]

    clean = {
        'child_title': text('child_title'),
        'child_story': text('child_story'),
        'child_points': [p.strip() for p in (data.get('child_points') or '').splitlines() if p.strip()][:8],
        'child_action': text('child_action'),
        'practice_subject': text('practice_subject'),
        'practice_body': _repair_link(text('practice_body')),
    }
    errors = []
    if not clean['child_title'] or not clean['child_story']:
        errors.append('The lesson needs a title and a story.')
    if not clean['practice_subject'] or not clean['practice_body'].replace('{link}', '').strip():
        errors.append('The practice message needs a subject and some text.')
    lesson_text = ' '.join([clean['child_title'], clean['child_story'], clean['child_action'], *clean['child_points']])
    if _BANNED.search(lesson_text):
        errors.append(f'The lesson uses a theme Guardian does not allow in children\'s lessons ("{_BANNED.search(lesson_text).group(0)}").')
    warnings = _safety_screen({'quiz': [], 'practice': {
        'sender_name': pack.practice_sender, 'subject': clean['practice_subject'], 'body': clean['practice_body'],
        'sms': '{link}', 'red_flags': []}})
    errors += warnings
    if errors:
        return None, errors
    clean = no_em_dash(clean)
    edit, _ = ParentLessonEdit.objects.update_or_create(
        pack=pack, parent=parent,
        defaults={**clean, 'safety_warnings': [], 'status': ParentLessonEdit.STATUS_ACTIVE,
                  'analyst_note': '', 'reviewed_by': None, 'reviewed_at': None})
    return edit, []


def revert_edit(edit, analyst, note='') -> None:
    edit.status, edit.reviewed_by, edit.reviewed_at = ParentLessonEdit.STATUS_REVERTED, analyst, timezone.now()
    edit.analyst_note = note.strip()[:500] or 'Reverted to Guardian\'s original wording.'
    edit.save(update_fields=['status', 'reviewed_by', 'reviewed_at', 'analyst_note'])


def _site():
    return getattr(settings, 'SITE_URL', 'http://localhost:8000').rstrip('/')


def publish(pack) -> int:
    """Publish a pack to families, tell parents who asked for it, and send automatic drills. Returns drills sent."""
    from .sender import automate_for_published
    pack.status, pack.published_at = TopicPack.STATUS_PUBLISHED, pack.published_at or timezone.now()
    pack.save(update_fields=['status', 'published_at'])
    for req in ChildVersionRequest.objects.filter(content=pack.content, resolved_at__isnull=True).select_related('parent'):
        req.resolved_at = timezone.now()
        req.save(update_fields=['resolved_at'])
        _tell_parent_ready(pack, req.parent)
    return automate_for_published(pack)


def _tell_parent_ready(pack, parent):
    url = _site() + reverse('parent_news_detail', args=[pack.content_id]) + '#child-lesson'
    html = no_em_dash(render_to_string('phishsim/emails/child_version_ready.html', {'pack': pack, 'url': url}))
    msg = EmailMultiAlternatives(subject=no_em_dash(f'The child lesson for "{pack.content.title}" is ready'),
                                 body=_strip_html(html), from_email=settings.DEFAULT_FROM_EMAIL, to=[parent.email])
    msg.attach_alternative(html, 'text/html')
    try:
        _send_with_retry(msg)
    except Exception as e:
        logger.warning('Child-version-ready email to parent #%s failed: %s', parent.pk, type(e).__name__)


def request_child_version(content, parent) -> ChildVersionRequest:
    """Record the request and, if no pack exists yet, start preparing one for the analysts to review."""
    from . import autogen
    req, created = ChildVersionRequest.objects.get_or_create(content=content, parent=parent)
    if not created and req.resolved_at:
        req.resolved_at = None
        req.save(update_fields=['resolved_at'])
    if not TopicPack.objects.filter(content=content).exists():
        autogen.start(content, None)
    return req

