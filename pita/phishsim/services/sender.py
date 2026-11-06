"""Sending practice messages and welcome notices (plan.md §8.1, §8.5). Email now; SMS/WhatsApp share the same rules."""
import logging
import secrets
from datetime import timedelta

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils import timezone
from django.utils.html import escape, linebreaks

from awarenessapp.services.email_service import _send_with_retry, _strip_html
from awarenessapp.services.text import no_em_dash
from safety.models import ConsentRecord, GuardianChildLink, GuardianPreference

from ..models import PracticeDelivery

logger = logging.getLogger(__name__)


def _site() -> str:
    return getattr(settings, 'SITE_URL', 'http://localhost:8001').rstrip('/')


def _from(display_name: str) -> str:
    """Honest sending: Guardian's own address; only the display name is playful (plan.md §8.1 rule 4)."""
    address = settings.EMAIL_HOST_USER or 'practice@guardian.local'
    safe = ''.join(ch for ch in display_name if ch.isalnum() or ch in ' .-').strip() or 'Guardian'
    return f'{safe} <{address}>'


# ── Eligibility ──

def why_not_eligible(child) -> str:
    """Empty string if this child can receive a practice email now, else a plain reason for the parent."""
    if not child.email:
        return 'No email address yet'
    if child.email_blocked:
        return 'The email address asked Guardian to stop'
    if getattr(settings, 'GUARDIAN_PRACTICE_OPEN', False):
        return ''                    # demo mode: welcome note is sent with the first practice email
    if not ConsentRecord.active(child, ConsentRecord.KIND_SIMULATION):
        return 'Practice emails are turned off'
    if not child.notice_sent_at:
        return 'Welcome note not delivered yet'
    month_ago = timezone.now() - timedelta(days=30)
    if child.practice_deliveries.filter(status='sent', sent_at__gte=month_ago).count() >= settings.GUARDIAN_SIM_MAX_PER_MONTH:
        return f'Monthly limit reached ({settings.GUARDIAN_SIM_MAX_PER_MONTH} practice messages)'
    return ''


# ── Welcome notice (sent when the parent turns practice emails on) ──

def send_notice(child) -> bool:
    if child.notice_sent_at or not child.email or child.email_blocked:
        return bool(child.notice_sent_at)
    if not child.block_token:
        child.block_token = secrets.token_urlsafe(24)
        child.save(update_fields=['block_token'])
    parents = [link.guardian for link in GuardianChildLink.objects.filter(child=child, active=True).select_related('guardian__profile')]
    html = no_em_dash(render_to_string('phishsim/emails/notice.html', {
        'child': child, 'parent_names': [p.profile.display_name for p in parents],
        'stop_url': _site() + reverse('practice_stop', args=[child.block_token]), 'site': _site(),
    }))
    msg = EmailMultiAlternatives(subject='Your family set up Guardian for you', body=_strip_html(html),
                                 from_email=_from('Guardian'), to=[child.email])
    msg.attach_alternative(html, 'text/html')
    try:
        _send_with_retry(msg)
    except Exception as e:
        logger.error('Welcome notice to child #%s failed: %s', child.pk, e)
        return False
    child.notice_sent_at = timezone.now()
    child.save(update_fields=['notice_sent_at'])
    return True


# ── Practice emails ──

def render_practice(delivery: PracticeDelivery) -> tuple[str, str]:
    """(html, text) for one delivery. The link carries the delivery token; no login page on the way (§8.6)."""
    pack = delivery.pack
    edit = delivery.lesson_edit if delivery.lesson_edit_id and delivery.lesson_edit.is_active else None
    body = edit.practice_body if edit else pack.practice_body
    link = _site() + reverse('practice_open', args=[delivery.token])
    name = delivery.child.nickname
    body_html = (linebreaks(escape(body)).replace('{name}', escape(name))
                 .replace('{link}', f'<a href="{link}">{link}</a>'))
    html = no_em_dash(render_to_string('phishsim/emails/practice.html', {
        'pack': pack, 'body_html': body_html, 'link': link, 'child': delivery.child}))
    text = body.replace('{name}', name).replace('{link}', link)
    return html, no_em_dash(text)


def practice_subject(delivery) -> str:
    edit = delivery.lesson_edit if delivery.lesson_edit_id and delivery.lesson_edit.is_active else None
    subject = edit.practice_subject if edit else delivery.pack.practice_subject
    return no_em_dash(subject.replace('{name}', delivery.child.nickname))


def send_delivery(delivery: PracticeDelivery) -> PracticeDelivery:
    reason = why_not_eligible(delivery.child)
    if reason:
        delivery.status, delivery.skip_reason = 'skipped', reason
        delivery.save(update_fields=['status', 'skip_reason'])
        return delivery
    if not delivery.child.notice_sent_at:
        send_notice(delivery.child)  # demo mode: the welcome note goes out together with the first practice email
    html, text = render_practice(delivery)
    msg = EmailMultiAlternatives(subject=practice_subject(delivery), body=text,
                                 from_email=_from(delivery.pack.practice_sender), to=[delivery.child.email],
                                 headers={'X-Guardian-Simulation': str(delivery.pk)})
    msg.attach_alternative(html, 'text/html')
    try:
        _send_with_retry(msg)
    except Exception as e:
        logger.error('Practice email #%s failed: %s', delivery.pk, e)
        delivery.status, delivery.error_message = 'failed', str(e)[:500]
        delivery.save(update_fields=['status', 'error_message'])
        return delivery
    delivery.status, delivery.sent_at, delivery.sent_to = 'sent', timezone.now(), delivery.child.email
    delivery.save(update_fields=['status', 'sent_at', 'sent_to'])
    return delivery


def send_pack_to_children(pack, parent, children, *, automated=False, resend=None) -> list[PracticeDelivery]:
    """One delivery per child (re-sending a failed one retries it). Only the parent's own linked children.
    In demo mode (GUARDIAN_PRACTICE_OPEN) a parent may send the same practice message again."""
    if resend is None:
        resend = getattr(settings, 'GUARDIAN_PRACTICE_OPEN', False) and not automated
    from .versions import active_edit
    own = set(GuardianChildLink.objects.filter(guardian=parent, active=True).values_list('child_id', flat=True))
    edit = active_edit(pack, parent)          # the parent's own wording, if they edited it
    results = []
    for child in children:
        if child.pk not in own:
            continue
        delivery, created = PracticeDelivery.objects.get_or_create(
            pack=pack, child=child, channel='email', defaults={'sent_by': parent, 'automated': automated})
        if not created and delivery.status == 'sent' and not resend:
            results.append(delivery)
            continue
        if delivery.lesson_edit_id != getattr(edit, 'pk', None):
            delivery.lesson_edit = edit
            delivery.save(update_fields=['lesson_edit'])
        results.append(send_delivery(delivery))
    return results


def automate_for_published(pack) -> int:
    """After an analyst publishes: send to every eligible child of parents who turned on automatic drills."""
    sent = 0
    for pref in GuardianPreference.objects.filter(auto_drills=True).select_related('parent'):
        children = [link.child for link in GuardianChildLink.objects.filter(guardian=pref.parent, active=True).select_related('child')]
        for d in send_pack_to_children(pack, pref.parent, children, automated=True):
            sent += d.status == 'sent'
    return sent
