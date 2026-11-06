"""Practice (simulated phishing) messages built from analyst-approved topics (plan.md §8.0, §8.4).

One approved AwarenessContent → one TopicPack: the parent version, the child version, the child quiz and the
captivating practice message that leads to it. Each send to one child is a PracticeDelivery with its own token.
"""
import secrets

from django.conf import settings
from django.db import models


def _token() -> str:
    return secrets.token_urlsafe(24)


class TopicPack(models.Model):
    STATUS_DRAFT = 'draft'            # generated, waiting for the analyst
    STATUS_PUBLISHED = 'published'    # visible to parents; can be sent to children
    STATUS_CHOICES = [(STATUS_DRAFT, 'Draft (analyst review)'), (STATUS_PUBLISHED, 'Published to families')]

    content = models.OneToOneField('awarenessapp.AwarenessContent', on_delete=models.CASCADE, related_name='pack')
    # Parent version
    parent_summary = models.TextField()
    parent_why = models.TextField(blank=True)
    parent_tips = models.JSONField(default=list, blank=True)          # how to talk with your child
    # Child version (child language, same format the analyst chose)
    child_title = models.CharField(max_length=200)
    child_story = models.TextField()
    child_points = models.JSONField(default=list, blank=True)         # "signs to spot"
    child_action = models.TextField(blank=True)
    child_quiz = models.ForeignKey('awarenessapp.Quiz', null=True, blank=True, on_delete=models.SET_NULL,
                                   related_name='child_packs')
    # Practice message (email now; SMS / WhatsApp text later)
    practice_sender = models.CharField(max_length=80)                 # display name only, e.g. "MoMoPay Rewards"
    practice_subject = models.CharField(max_length=160)
    practice_body = models.TextField(help_text='Use {link} where the button/link goes')
    practice_sms = models.CharField(max_length=320, blank=True, help_text='Short text version, with {link}')
    red_flags = models.JSONField(default=list, blank=True)            # [{"label": ..., "excerpt": ...}]
    safety_warnings = models.JSONField(default=list, blank=True)      # automatic safety screen findings
    status = models.CharField(max_length=12, choices=STATUS_CHOICES, default=STATUS_DRAFT)
    generated_by = models.CharField(max_length=120, blank=True)
    published_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-published_at', '-created_at']

    def __str__(self):
        return f'{self.child_title} [{self.status}]'

    @property
    def is_published(self) -> bool:
        return self.status == self.STATUS_PUBLISHED


class PracticeDelivery(models.Model):
    CHANNEL_CHOICES = [('email', 'Email'), ('sms', 'SMS'), ('whatsapp', 'WhatsApp')]
    STATUS_CHOICES = [('pending', 'Pending'), ('sent', 'Sent'), ('failed', 'Failed'),
                      ('skipped', 'Skipped')]

    pack = models.ForeignKey(TopicPack, on_delete=models.CASCADE, related_name='deliveries')
    child = models.ForeignKey('safety.ChildProfile', on_delete=models.CASCADE, related_name='practice_deliveries')
    sent_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
                                related_name='practice_sent')
    automated = models.BooleanField(default=False)
    channel = models.CharField(max_length=10, choices=CHANNEL_CHOICES, default='email')
    token = models.CharField(max_length=64, unique=True, default=_token, editable=False)
    sent_to = models.CharField(max_length=254, blank=True)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='pending')
    skip_reason = models.CharField(max_length=120, blank=True)
    error_message = models.TextField(blank=True)
    sent_at = models.DateTimeField(null=True, blank=True)
    clicked_at = models.DateTimeField(null=True, blank=True)
    click_count = models.PositiveIntegerField(default=0)
    lesson_viewed_at = models.DateTimeField(null=True, blank=True)
    quiz_attempt = models.ForeignKey('awarenessapp.QuizAttempt', null=True, blank=True, on_delete=models.SET_NULL)
    lesson_edit = models.ForeignKey('ParentLessonEdit', null=True, blank=True, on_delete=models.SET_NULL,
                                    related_name='deliveries')     # the parent's wording used for this send
    reported_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        constraints = [models.UniqueConstraint(fields=['pack', 'child', 'channel'], name='one_practice_per_pack_child_channel')]

    def __str__(self):
        return f'{self.pack.child_title} → {self.child} ({self.status})'


class ParentLessonEdit(models.Model):
    """A parent's own wording of the child lesson and practice message, used for their own children only.

    Live once it passes the automatic safety screen; analysts see every edit and can revert it (plan.md §8.0).
    """
    STATUS_ACTIVE, STATUS_REVERTED = 'active', 'reverted'
    STATUS_CHOICES = [(STATUS_ACTIVE, 'In use for their children'), (STATUS_REVERTED, 'Reverted by an analyst')]

    pack = models.ForeignKey(TopicPack, on_delete=models.CASCADE, related_name='parent_edits')
    parent = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='lesson_edits')
    child_title = models.CharField(max_length=200)
    child_story = models.TextField()
    child_points = models.JSONField(default=list, blank=True)
    child_action = models.TextField(blank=True)
    practice_subject = models.CharField(max_length=160)
    practice_body = models.TextField()
    safety_warnings = models.JSONField(default=list, blank=True)
    status = models.CharField(max_length=12, choices=STATUS_CHOICES, default=STATUS_ACTIVE)
    analyst_note = models.TextField(blank=True)
    reviewed_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
                                    related_name='lesson_edits_reviewed')
    reviewed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-updated_at']
        constraints = [models.UniqueConstraint(fields=['pack', 'parent'], name='one_lesson_edit_per_parent')]

    def __str__(self):
        return f'{self.parent} edit of {self.pack.child_title} ({self.status})'

    @property
    def is_active(self) -> bool:
        return self.status == self.STATUS_ACTIVE


class ChildVersionRequest(models.Model):
    """A parent asked for the child lesson of a topic that has none published yet."""
    content = models.ForeignKey('awarenessapp.AwarenessContent', on_delete=models.CASCADE, related_name='child_version_requests')
    parent = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='child_version_requests')
    created_at = models.DateTimeField(auto_now_add=True)
    resolved_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']
        constraints = [models.UniqueConstraint(fields=['content', 'parent'], name='one_child_version_request_per_parent')]
