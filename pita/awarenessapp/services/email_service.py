import logging
from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils import timezone
from ..models import EmailCampaign, EmailDelivery, Users, ROLE_PARENT
from .text import no_em_dash
from safety.templatetags.app_ui import as_steps

logger = logging.getLogger(__name__)


def build_email_body(campaign: EmailCampaign) -> str:
    """Render the HTML email body for a campaign."""
    content = campaign.content
    site_url = getattr(settings, 'SITE_URL', 'http://localhost:8000').rstrip('/')

    # Parents land on the family news page for this topic: article, quiz and sending to their children (plan.md §8.0)
    content_url = site_url + reverse('parent_news_detail', args=[content.pk])
    quiz_url = content_url + '#quiz'

    ctx = {
        'title': content.title,
        'risk': content.risk,
        'action': content.action,
        'steps': as_steps(content.action),
        'threat_type': content.get_threat_type_display(),
        'engagement_type': content.engagement_type,
        'engagement_data': content.engagement_data or {},
        'content_url': content_url,
        'quiz_url': quiz_url,
        'campaign': campaign,
    }
    return no_em_dash(render_to_string('emails/awareness_email.html', ctx))


def send_campaign(campaign: EmailCampaign) -> dict:
    """
    Send a campaign to selected recipients. Returns a summary dict.
    Creates an EmailDelivery record per recipient.
    Target logic:
      - target_all_staff=True  -> all active parent accounts
      - target_all_staff=False -> explicit target_recipients + extra_emails
    """
    if campaign.status == EmailCampaign.STATUS_SENT:
        return {'error': 'Campaign already sent'}

    # Resolve user-based recipients
    if campaign.target_all_staff:
        user_recipients = list(Users.objects.filter(role=ROLE_PARENT, is_active=True))
    else:
        user_recipients = list(campaign.target_recipients.filter(is_active=True))

    # Resolve extra email-only addresses, deduplicated against user list
    user_email_set = {u.email.lower() for u in user_recipients}
    extra_emails = [
        e.strip().lower()
        for e in campaign.extra_emails.splitlines()
        if e.strip() and e.strip().lower() not in user_email_set
    ]

    if not user_recipients and not extra_emails:
        return {'error': 'No recipients selected. Add parents, extra email addresses, or upload a list.'}

    campaign.status = EmailCampaign.STATUS_SENDING
    campaign.save(update_fields=['status'])

    sent_count = 0
    failed_count = 0

    def _send_to(to_email: str, delivery: EmailDelivery):
        nonlocal sent_count, failed_count
        html_content = build_email_body(campaign)
        try:
            msg = EmailMultiAlternatives(
                subject=no_em_dash(campaign.subject),
                body=_strip_html(html_content),
                from_email=settings.DEFAULT_FROM_EMAIL,
                to=[to_email],
            )
            msg.attach_alternative(html_content, 'text/html')
            _send_with_retry(msg)
            delivery.status = EmailDelivery.STATUS_SENT
            delivery.sent_at = timezone.now()
            delivery.save(update_fields=['status', 'sent_at'])
            sent_count += 1
        except Exception as e:
            logger.error(f"Failed to send campaign #{campaign.pk} to {to_email}: {e}")
            delivery.status = EmailDelivery.STATUS_FAILED
            delivery.error_message = str(e)
            delivery.save(update_fields=['status', 'error_message'])
            failed_count += 1

    # Send to Users
    for recipient in user_recipients:
        delivery, created = EmailDelivery.objects.get_or_create(
            campaign=campaign,
            recipient=recipient,
            defaults={'email': recipient.email, 'status': EmailDelivery.STATUS_PENDING},
        )
        if not created and not delivery.email:
            delivery.email = recipient.email
            delivery.save(update_fields=['email'])
        if delivery.status == EmailDelivery.STATUS_SENT:
            sent_count += 1
            continue
        _send_to(recipient.email, delivery)

    # Send to extra (non-User) emails
    for extra_email in extra_emails:
        delivery = EmailDelivery.objects.filter(campaign=campaign, email=extra_email).first()
        if not delivery:
            delivery = EmailDelivery.objects.create(
                campaign=campaign,
                recipient=None,
                email=extra_email,
                status=EmailDelivery.STATUS_PENDING,
            )
        if delivery.status == EmailDelivery.STATUS_SENT:
            sent_count += 1
            continue
        _send_to(extra_email, delivery)

    if sent_count:
        campaign.status = EmailCampaign.STATUS_SENT
        campaign.sent_at = timezone.now()
        campaign.save(update_fields=['status', 'sent_at'])
    else:
        # Nothing went out (e.g. the mail server connection dropped): keep it re-sendable
        campaign.status = EmailCampaign.STATUS_DRAFT
        campaign.save(update_fields=['status'])

    logger.info(f"Campaign #{campaign.pk} sent: {sent_count} ok, {failed_count} failed")
    return {'sent': sent_count, 'failed': failed_count}


def _send_with_retry(msg, attempts: int = 3, wait: float = 2.0) -> None:
    """Send, retrying briefly on network/TLS drops (e.g. 'UNEXPECTED_EOF_WHILE_READING' on a flaky link)."""
    import smtplib, socket, ssl, time
    for attempt in range(1, attempts + 1):
        try:
            msg.send()
            return
        except (smtplib.SMTPServerDisconnected, smtplib.SMTPConnectError, ssl.SSLError, socket.timeout,
                ConnectionError, OSError) as e:
            if attempt == attempts or isinstance(e, smtplib.SMTPAuthenticationError):
                raise
            logger.warning('Email send attempt %s failed (%s), retrying', attempt, type(e).__name__)
            time.sleep(wait * attempt)


def _strip_html(html: str) -> str:
    import re
    return re.sub(r'<[^>]+>', '', html)
