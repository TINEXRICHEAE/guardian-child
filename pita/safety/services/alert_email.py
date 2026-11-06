"""Email a parent their safety alert when they chose "Email me alerts too" (Preferences).

The email carries exactly what the alerts page shows: the type of threat, the safety action and the time. Never the
message, link or screenshot the child checked.
"""
import logging
import threading

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.db import close_old_connections, transaction
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils import timezone

from awarenessapp.services.email_service import _send_with_retry, _strip_html
from awarenessapp.services.text import no_em_dash

from ..models import GuardianPreference

logger = logging.getLogger(__name__)
SEND_IN_BACKGROUND = True        # tests switch this off; a slow mail server must not slow down a child's check


def _send(alert_pk):
    from ..models import ParentAlert
    alert = ParentAlert.objects.select_related('parent', 'child').filter(pk=alert_pk).first()
    if alert is None or not alert.parent.email:
        return
    site = getattr(settings, 'SITE_URL', 'http://localhost:8000').rstrip('/')
    html = no_em_dash(render_to_string('safety/emails/parent_alert.html', {
        'alert': alert, 'when': timezone.localtime(alert.created_at).strftime('%a %d %b, %H:%M %Z'),
        'alerts_url': site + reverse('parent_alerts'), 'settings_url': site + reverse('parent_settings'),
    }))
    level = 'High-risk' if alert.severity == 'high' else 'Warning'
    msg = EmailMultiAlternatives(subject=no_em_dash(f'Guardian {level} alert for {alert.child.nickname}'),
                                 body=_strip_html(html), from_email=settings.DEFAULT_FROM_EMAIL, to=[alert.parent.email])
    msg.attach_alternative(html, 'text/html')
    try:
        _send_with_retry(msg)
    except Exception as e:
        logger.warning('Alert email #%s to parent #%s failed: %s', alert.pk, alert.parent_id, type(e).__name__)


def notify(alert) -> bool:
    """Queue the email for one new alert if this parent asked for alert emails. Returns True if queued."""
    if not GuardianPreference.for_parent(alert.parent).alert_email:
        return False

    def go():
        if not SEND_IN_BACKGROUND:
            return _send(alert.pk)

        def work():
            close_old_connections()
            try:
                _send(alert.pk)
            finally:
                close_old_connections()
        threading.Thread(target=work, daemon=True, name=f'alert-email-{alert.pk}').start()

    transaction.on_commit(go)
    return True
