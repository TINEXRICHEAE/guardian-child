"""Families, consent and (later) detection records for Guardian's child-safety features (plan.md §5.3, §7.3)."""
import hashlib
import secrets
from datetime import timedelta

from django.conf import settings
from django.db import models
from django.utils import timezone

AGE_BANDS = [('8-10', '8–10'), ('11-13', '11–13'), ('14-17', '14–17')]


def _new_pseudonym() -> str:
    return f'C-{secrets.token_hex(2).upper()}'


class ChildProfile(models.Model):
    """A child as seen by Guardian. Nickname and age band only, never a legal name.

    A child needs no account: the parent's entry (with an email) is enough for practice emails and lessons.
    `user` is set only if the child pairs a device and signs in.
    """
    user = models.OneToOneField(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
                                related_name='child_profile')
    nickname = models.CharField(max_length=40)
    age_band = models.CharField(max_length=5, choices=AGE_BANDS)
    district = models.CharField(max_length=60, blank=True, help_text='District only, used for aggregates')
    email = models.EmailField(blank=True, help_text='Entered by the parent; used for notices, practice emails and lessons')
    email_blocked = models.BooleanField(default=False, help_text='Set by "This isn\'t me / stop" in the welcome notice')
    phone = models.CharField(max_length=20, blank=True, help_text='For SMS practice messages (coming soon)')
    whatsapp = models.CharField(max_length=40, blank=True, help_text='WhatsApp number (coming soon)')
    notice_sent_at = models.DateTimeField(null=True, blank=True, help_text='Welcome notice delivered to the child\'s email')
    block_token = models.CharField(max_length=64, unique=True, null=True, blank=True, editable=False)
    pseudonym = models.CharField(max_length=12, unique=True, default=_new_pseudonym, editable=False,
                                 help_text='Shown to analysts instead of the nickname')
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
                                   related_name='created_children')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['nickname']

    def __str__(self):
        return f'{self.nickname} ({self.pseudonym})'

    @property
    def is_paired(self) -> bool:
        return self.user_id is not None


class GuardianChildLink(models.Model):
    guardian = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='child_links')
    child = models.ForeignKey(ChildProfile, on_delete=models.CASCADE, related_name='guardian_links')
    active = models.BooleanField(default=True)
    linked_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['guardian', 'child'], name='unique_guardian_child')]

    def __str__(self):
        return f'{self.guardian} → {self.child}'


class PairingCode(models.Model):
    """One-time code a parent shows to a child's device. Only a SHA-256 hash is stored."""
    VALID_MINUTES = 10

    guardian = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='pairing_codes')
    child = models.ForeignKey(ChildProfile, on_delete=models.CASCADE, related_name='pairing_codes')
    code_hash = models.CharField(max_length=64, unique=True)
    expires_at = models.DateTimeField()
    used_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    @staticmethod
    def hash(code: str) -> str:
        """Children may type 'SAFE-123456', 'safe 123456' or just '123456': all mean the same code."""
        digits = ''.join(ch for ch in code if ch.isdigit())
        return hashlib.sha256(f'SAFE-{digits}'.encode()).hexdigest()

    @classmethod
    def issue(cls, guardian, child) -> str:
        """Create a fresh code for `child`, invalidating earlier unused ones. Returns the plain code once."""
        cls.objects.filter(child=child, used_at__isnull=True).update(expires_at=timezone.now())
        while True:
            code = f'SAFE-{secrets.randbelow(10 ** 6):06d}'
            if not cls.objects.filter(code_hash=cls.hash(code)).exists():
                break
        cls.objects.create(guardian=guardian, child=child, code_hash=cls.hash(code),
                           expires_at=timezone.now() + timedelta(minutes=cls.VALID_MINUTES))
        return code

    @classmethod
    def redeemable(cls, code: str):
        return cls.objects.filter(code_hash=cls.hash(code), used_at__isnull=True,
                                  expires_at__gt=timezone.now()).select_related('child', 'guardian').first()


class ConsentRecord(models.Model):
    KIND_SIMULATION = 'phishing_simulation'
    KIND_ALERTS = 'parent_alerts'
    KIND_NOTICE = 'data_notice'
    KIND_CHOICES = [
        (KIND_SIMULATION, 'Practice (simulated) phishing emails'),
        (KIND_ALERTS, 'Minimal safety alerts to the parent'),
        (KIND_NOTICE, 'Data and privacy notice acknowledged'),
    ]
    NOTICE_VERSION = '2026-11-05'

    parent = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='consents')
    child = models.ForeignKey(ChildProfile, on_delete=models.CASCADE, related_name='consents')
    kind = models.CharField(max_length=30, choices=KIND_CHOICES)
    told_child = models.BooleanField(default=False, help_text='Parent confirmed they told the child')
    notice_version = models.CharField(max_length=20, default=NOTICE_VERSION)
    granted_at = models.DateTimeField(auto_now_add=True)
    revoked_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-granted_at']

    @classmethod
    def active(cls, child, kind):
        return cls.objects.filter(child=child, kind=kind, revoked_at__isnull=True).first()

    @classmethod
    def grant(cls, parent, child, kind, told_child=False):
        return cls.active(child, kind) or cls.objects.create(parent=parent, child=child, kind=kind,
                                                             told_child=told_child)

    @classmethod
    def revoke(cls, child, kind):
        cls.objects.filter(child=child, kind=kind, revoked_at__isnull=True).update(revoked_at=timezone.now())


# ── Detection, reports and alerts (plan.md §7.3) ──

RISK_CHOICES = [('low', 'Low observed risk'), ('suspicious', 'Suspicious'),
                ('high', 'High risk'), ('unable_to_verify', 'Unable to verify')]
INPUT_KINDS = [('text', 'Text or link'), ('image', 'Screenshot'), ('pdf', 'PDF'), ('email', 'Email'), ('txt', 'Text file')]


class Submission(models.Model):
    """One 'Is this safe?' check. Stores only redacted, scammer-supplied evidence; files are never kept."""
    submitted_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
                                     related_name='submissions')
    submitter_role = models.CharField(max_length=10)                      # child | parent | guest
    child = models.ForeignKey(ChildProfile, null=True, blank=True, on_delete=models.SET_NULL, related_name='submissions')
    input_kind = models.CharField(max_length=10, choices=INPUT_KINDS, default='text')
    file_sha256 = models.CharField(max_length=64, blank=True)
    file_mime = models.CharField(max_length=60, blank=True)
    sanitised_text = models.TextField(blank=True)
    urls = models.JSONField(default=list, blank=True)                      # inert text, never fetched
    content_hash = models.CharField(max_length=64, db_index=True)
    risk_level = models.CharField(max_length=20, choices=RISK_CHOICES)
    category = models.CharField(max_length=20, default='other')
    signals = models.JSONField(default=list, blank=True)
    evidence_sources = models.JSONField(default=list, blank=True)
    classifier_score = models.FloatField(null=True, blank=True)            # uncalibrated
    explanation = models.TextField(blank=True)
    recommended_actions = models.JSONField(default=list, blank=True)
    needs_human_review = models.BooleanField(default=False)
    already_acted = models.BooleanField(default=False)                     # child said they clicked / paid / shared
    practice_delivery = models.ForeignKey('phishsim.PracticeDelivery', null=True, blank=True, on_delete=models.SET_NULL,
                                          related_name='reports')   # set when a child reports a practice message (§8.7)
    mode = models.CharField(max_length=20, default='live')                 # live | cloud-dev | demo | unable_to_verify
    providers = models.JSONField(default=dict, blank=True)                 # guardian-ai host/backend per step
    latency_ms = models.IntegerField(null=True, blank=True)
    review_status = models.CharField(max_length=12, default='new')         # new | reviewing | reviewed | escalated
    district = models.CharField(max_length=60, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'Submission #{self.pk} {self.risk_level}'

    @property
    def label(self) -> str:
        """Short, content-free label for history lists."""
        if self.input_kind == 'image':
            return 'Screenshot check'
        return 'Link check' if self.urls and len(self.sanitised_text) < 300 and self.sanitised_text.strip() in self.urls else 'Message check'


class IncidentReport(models.Model):
    """'Something happened'. Confidential reports never notify a parent (plan.md §7.6, §13)."""
    CATEGORY_CHOICES = [('money_sent', 'I sent money'), ('shared_code', 'I shared a code or password'),
                        ('threatened', 'Someone threatened me'), ('clicked_link', 'I clicked a link'), ('other', 'Something else')]
    STATUS_CHOICES = [('new', 'New'), ('priority_review', 'Priority review'), ('restricted', 'Restricted'),
                      ('reviewed', 'Reviewed')]

    child = models.ForeignKey(ChildProfile, null=True, blank=True, on_delete=models.SET_NULL, related_name='reports')
    submitted_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
                                     related_name='incident_reports')
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES, default='other')
    summary = models.TextField()                                           # redacted
    confidential = models.BooleanField(default=False)
    notify_parent = models.BooleanField(default=False)
    needs_safeguarding = models.BooleanField(default=False)                # danger / self-harm wording found
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='new')
    submission = models.ForeignKey(Submission, null=True, blank=True, on_delete=models.SET_NULL)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']


class ParentAlert(models.Model):
    """Minimum necessary context for a parent: threat type, safety action, time. Never message content."""
    parent = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='parent_alerts')
    child = models.ForeignKey(ChildProfile, on_delete=models.CASCADE, related_name='alerts')
    severity = models.CharField(max_length=12)                             # high | suspicious
    title = models.CharField(max_length=160)
    safety_action = models.CharField(max_length=300)
    source = models.CharField(max_length=20, default='check')              # check | report
    read_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']


class GuardianPreference(models.Model):
    """Parent notification and (prepared, not yet enforced) protection preferences."""
    parent = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='guardian_preference')
    alert_high = models.BooleanField(default=True)
    alert_suspicious = models.BooleanField(default=False)
    alert_email = models.BooleanField(default=False)
    protect_fraud = models.BooleanField(default=True)
    protect_gambling = models.BooleanField(default=False)
    protect_adult = models.BooleanField(default=False)
    auto_drills = models.BooleanField(default=False, help_text='Send new published topics to my children automatically')
    updated_at = models.DateTimeField(auto_now=True)

    @classmethod
    def for_parent(cls, parent):
        return cls.objects.get_or_create(parent=parent)[0]
