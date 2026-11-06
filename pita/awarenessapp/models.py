from django.utils import timezone
from django.db import models
from django.db.models.signals import post_save
from django.dispatch import receiver
from phonenumber_field.modelfields import PhoneNumberField
from django.contrib.auth.models import Group as DjangoGroup
from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin, BaseUserManager
import uuid
import json
import hashlib
from decimal import Decimal
import os


SCAM_CATEGORY_CHOICES = [
    ('reward', 'Fake reward / prize'),
    ('advance_fee', 'Scholarship / bursary / advance fee'),
    ('otp_theft', 'OTP / PIN / account takeover'),
    ('phishing_link', 'Phishing link / fake login'),
    ('impersonation', 'Impersonation (school, brand, person)'),
    ('sextortion', 'Sextortion / threats'),   # route to safeguarding; never a simulation theme
    ('other', 'Other'),
    ('all', 'All Types'),
]
INSIDER_THREAT_CHOICES = SCAM_CATEGORY_CHOICES   # temporary alias while old code is migrated

ROLE_CHILD = 'child'
ROLE_PARENT = 'parent'
ROLE_ANALYST = 'analyst'

class UsersManager(BaseUserManager):
    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError('The Email field must be set')
        email = self.normalize_email(email)

        # Public sign-up creates parents; children are created by their parent, analysts by an operator
        extra_fields.setdefault('role', ROLE_PARENT)

        if extra_fields['role'] == ROLE_ANALYST:
            extra_fields['is_staff'] = True
            extra_fields.setdefault('is_superuser', False)   # create_superuser passes True (system operator)
        else:
            extra_fields['is_staff'] = False
            extra_fields['is_superuser'] = False

        extra_fields['is_active'] = True

        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)

        return user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)

        extra_fields['role'] = ROLE_ANALYST

        return self.create_user(email, password, **extra_fields)

    def create_anonymous_user(self):
        anonymous_email = "anonymous@example.com"
        if not self.filter(email=anonymous_email).exists():
            anonymous_user = self.create(
                email=anonymous_email,
                role=ROLE_CHILD,
                is_active=False,
                is_staff=False,
                is_superuser=False,
            )
            anonymous_user.set_unusable_password()
            anonymous_user.save()
            return anonymous_user
        return None


class Users(AbstractBaseUser, PermissionsMixin):
    email = models.CharField(unique=True, max_length=50)
    password = models.CharField(max_length=128)
    ROLE_CHOICES = (
        (ROLE_CHILD, 'Child'),
        (ROLE_PARENT, 'Parent / Guardian'),
        (ROLE_ANALYST, 'UCC Analyst'),
    )
    role = models.CharField(max_length=50, choices=ROLE_CHOICES)
    phonenumber = PhoneNumberField(max_length=50, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    is_superuser = models.BooleanField(default=False)

    objects = UsersManager()

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = []

    class Meta:
        db_table = 'users'

    def __str__(self):
        return f"User(id={self.id}, email={self.email}, role={self.role})"

    def get_phone_number(self):
        return str(self.phonenumber) if self.phonenumber else None

    @property
    def is_child(self):
        return self.role == ROLE_CHILD

    @property
    def is_parent(self):
        return self.role == ROLE_PARENT

    @property
    def is_analyst(self):
        return self.role == ROLE_ANALYST


class Profile(models.Model):
    """Display details for parents and analysts. Children are described only by safety.ChildProfile."""
    user = models.OneToOneField(Users, on_delete=models.CASCADE, related_name='profile')
    full_name = models.CharField(max_length=200, blank=True)
    picture_url = models.URLField(max_length=500, blank=True)
    profile_picture = models.ImageField(upload_to='profile_pictures/', null=True, blank=True)
    date_joined = models.DateField(null=True, blank=True)

    class Meta:
        db_table = 'profiles'

    def __str__(self):
        return f"Profile({self.user.email})"

    @property
    def display_name(self):
        return self.full_name or self.user.email.split('@')[0]


@receiver(post_save, sender=Users)
def _auto_create_profile(sender, instance, created, **kwargs):
    if created:
        Profile.objects.get_or_create(
            user=instance,
            defaults={'date_joined': instance.created_at.date() if instance.created_at else timezone.now().date()},
        )


class ContentSource(models.Model):
    SOURCE_TYPE_URL = 'url'
    SOURCE_TYPE_DOCUMENT = 'document'
    SOURCE_TYPE_PROMPT = 'prompt'
    SOURCE_TYPE_CHOICES = [
        (SOURCE_TYPE_URL, 'URL Link Feed'),
        (SOURCE_TYPE_DOCUMENT, 'Document Upload'),
        (SOURCE_TYPE_PROMPT, 'Manual Prompt'),
    ]
    FETCH_FREQUENCY_CHOICES = [
        ('daily', 'Daily'),
        ('weekly', 'Weekly'),
        ('monthly', 'Monthly'),
    ]

    created_by = models.ForeignKey('Users', on_delete=models.CASCADE, related_name='content_sources')
    name = models.CharField(max_length=200)
    source_type = models.CharField(max_length=20, choices=SOURCE_TYPE_CHOICES)
    threat_type = models.CharField(max_length=20, choices=INSIDER_THREAT_CHOICES)
    # API fields
    api_url = models.URLField(max_length=500, null=True, blank=True)
    fetch_frequency = models.CharField(max_length=20, choices=FETCH_FREQUENCY_CHOICES, null=True, blank=True)
    # Document fields
    document = models.FileField(upload_to='sources/documents/', null=True, blank=True)
    document_url = models.URLField(max_length=500, blank=True, default='')
    # Prompt fields
    prompt_text = models.TextField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    last_fetched = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'content_sources'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.name} ({self.get_source_type_display()})"


class RawContent(models.Model):
    ENGAGEMENT_QUIZ = 'quiz'
    ENGAGEMENT_LINK = 'link'
    ENGAGEMENT_ARTICLE = 'article'
    ENGAGEMENT_SCENARIO = 'scenario'
    ENGAGEMENT_POLICY = 'policy'
    ENGAGEMENT_CHOICES = [
        (ENGAGEMENT_QUIZ, 'Quiz'),
        (ENGAGEMENT_LINK, 'Link'),
        (ENGAGEMENT_ARTICLE, 'Article'),
        (ENGAGEMENT_SCENARIO, 'Scenario'),
        (ENGAGEMENT_POLICY, 'Policy Reference'),
    ]

    source = models.ForeignKey(ContentSource, on_delete=models.CASCADE, related_name='raw_contents')
    raw_data = models.TextField()
    summary = models.TextField(blank=True)
    engagement_type = models.CharField(max_length=20, choices=ENGAGEMENT_CHOICES, default=ENGAGEMENT_ARTICLE)
    processed = models.BooleanField(default=False)
    fetched_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'raw_contents'
        ordering = ['-fetched_at']

    def __str__(self):
        return f"Raw({self.source.name}, {self.fetched_at:%Y-%m-%d})"


class AwarenessContent(models.Model):
    STATUS_PENDING = 'pending'
    STATUS_APPROVED = 'approved'
    STATUS_REJECTED = 'rejected'
    STATUS_SENT = 'sent'
    STATUS_CHOICES = [
        (STATUS_PENDING, 'Pending Review'),
        (STATUS_APPROVED, 'Approved'),
        (STATUS_REJECTED, 'Rejected'),
        (STATUS_SENT, 'Sent'),
    ]
    ENGAGEMENT_QUIZ = 'quiz'
    ENGAGEMENT_LINK = 'link'
    ENGAGEMENT_ARTICLE = 'article'
    ENGAGEMENT_SCENARIO = 'scenario'
    ENGAGEMENT_POLICY = 'policy'
    ENGAGEMENT_CHOICES = [
        (ENGAGEMENT_QUIZ, 'Quiz'),
        (ENGAGEMENT_LINK, 'Link'),
        (ENGAGEMENT_ARTICLE, 'Article'),
        (ENGAGEMENT_SCENARIO, 'Scenario'),
        (ENGAGEMENT_POLICY, 'Policy Reference'),
    ]

    raw_content = models.ForeignKey(RawContent, on_delete=models.SET_NULL, null=True, blank=True, related_name='awareness_contents')
    source = models.ForeignKey(ContentSource, on_delete=models.SET_NULL, null=True, blank=True, related_name='awareness_contents')
    created_by = models.ForeignKey('Users', on_delete=models.CASCADE, related_name='created_contents')
    reviewed_by = models.ForeignKey('Users', on_delete=models.SET_NULL, null=True, blank=True, related_name='reviewed_contents')
    threat_type = models.CharField(max_length=20, choices=INSIDER_THREAT_CHOICES)
    title = models.CharField(max_length=300)
    risk = models.TextField(help_text="Why this matters to the reader")
    action = models.TextField(help_text="What the reader should do")
    engagement_type = models.CharField(max_length=20, choices=ENGAGEMENT_CHOICES, default=ENGAGEMENT_ARTICLE)
    engagement_data = models.JSONField(null=True, blank=True, help_text="Link URL, quiz ID, scenario text, etc.")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING)
    admin_notes = models.TextField(blank=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'awareness_contents'
        ordering = ['-created_at']
        permissions = [
            ('view_panel', 'Can access admin panel'),
            ('manage_sources', 'Can manage content sources'),
            ('manage_content', 'Can manage awareness content'),
            ('manage_campaigns', 'Can manage email campaigns'),
            ('view_analytics', 'Can view analytics reports'),
            ('manage_users', 'Can manage users'),
            ('view_intel', 'Can view threat intelligence'),
            ('manage_simulations', 'Can manage phishing simulations'),
            ('export_intel', 'Can export sanitised intelligence'),
            ('view_confidential_reports', 'Can view confidential incident reports'),
        ]

    def __str__(self):
        return f"{self.title} [{self.get_status_display()}]"


class Quiz(models.Model):
    content = models.OneToOneField(AwarenessContent, on_delete=models.CASCADE, null=True, blank=True, related_name='quiz')
    title = models.CharField(max_length=300)
    description = models.TextField(blank=True)
    created_by = models.ForeignKey('Users', on_delete=models.CASCADE, related_name='quizzes')
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'quizzes'
        verbose_name_plural = 'quizzes'

    def __str__(self):
        return self.title

    @property
    def question_count(self):
        return self.questions.count()


class QuizQuestion(models.Model):
    quiz = models.ForeignKey(Quiz, on_delete=models.CASCADE, related_name='questions')
    question_text = models.TextField()
    order = models.PositiveIntegerField(default=0)

    class Meta:
        db_table = 'quiz_questions'
        ordering = ['order']

    def __str__(self):
        return f"Q{self.order}: {self.question_text[:60]}"


class QuizChoice(models.Model):
    question = models.ForeignKey(QuizQuestion, on_delete=models.CASCADE, related_name='choices')
    choice_text = models.CharField(max_length=500)
    is_correct = models.BooleanField(default=False)
    explanation = models.TextField(
        blank=True,
        help_text="Correct choice: why it's right. Wrong choice: complement/energizer phrase.",
    )

    class Meta:
        db_table = 'quiz_choices'

    def __str__(self):
        return f"{'[✓] ' if self.is_correct else ''}{self.choice_text[:60]}"


class QuizAttempt(models.Model):
    user = models.ForeignKey('Users', on_delete=models.CASCADE, related_name='quiz_attempts')
    quiz = models.ForeignKey(Quiz, on_delete=models.CASCADE, related_name='attempts')
    score = models.PositiveIntegerField(default=0)
    total = models.PositiveIntegerField(default=0)
    completed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'quiz_attempts'
        ordering = ['-completed_at']

    @property
    def percentage(self):
        return round((self.score / self.total) * 100) if self.total else 0


class QuizAttemptAnswer(models.Model):
    attempt = models.ForeignKey(QuizAttempt, on_delete=models.CASCADE, related_name='question_answers')
    question = models.ForeignKey(QuizQuestion, on_delete=models.CASCADE, related_name='attempt_answers')
    selected_choice = models.ForeignKey(
        QuizChoice, on_delete=models.SET_NULL, null=True, blank=True, related_name='+'
    )
    is_correct = models.BooleanField(default=False)

    class Meta:
        db_table = 'quiz_attempt_answers'
        unique_together = [['attempt', 'question']]


class EmailCampaign(models.Model):
    STATUS_DRAFT = 'draft'
    STATUS_SCHEDULED = 'scheduled'
    STATUS_SENDING = 'sending'
    STATUS_SENT = 'sent'
    STATUS_CHOICES = [
        (STATUS_DRAFT, 'Draft'),
        (STATUS_SCHEDULED, 'Scheduled'),
        (STATUS_SENDING, 'Sending'),
        (STATUS_SENT, 'Sent'),
    ]

    content = models.ForeignKey(AwarenessContent, on_delete=models.CASCADE, related_name='campaigns')
    subject = models.CharField(max_length=300)
    body_html = models.TextField()
    created_by = models.ForeignKey('Users', on_delete=models.CASCADE, related_name='campaigns')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_DRAFT)
    target_all_staff = models.BooleanField(default=True)
    target_recipients = models.ManyToManyField(
        'Users', blank=True, related_name='targeted_campaigns',
        help_text='Explicitly selected staff recipients (used when target_all_staff is False)',
    )
    extra_emails = models.TextField(
        blank=True, help_text='Additional email addresses, one per line (non-staff or external)'
    )
    scheduled_at = models.DateTimeField(null=True, blank=True)
    sent_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'email_campaigns'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.subject} [{self.get_status_display()}]"


class EmailDelivery(models.Model):
    STATUS_PENDING = 'pending'
    STATUS_SENT = 'sent'
    STATUS_OPENED = 'opened'
    STATUS_CLICKED = 'clicked'
    STATUS_FAILED = 'failed'
    STATUS_CHOICES = [
        (STATUS_PENDING, 'Pending'),
        (STATUS_SENT, 'Sent'),
        (STATUS_OPENED, 'Opened'),
        (STATUS_CLICKED, 'Clicked'),
        (STATUS_FAILED, 'Failed'),
    ]

    campaign = models.ForeignKey(EmailCampaign, on_delete=models.CASCADE, related_name='deliveries')
    recipient = models.ForeignKey(
        'Users', on_delete=models.SET_NULL, null=True, blank=True, related_name='email_deliveries'
    )
    email = models.CharField(max_length=255, default='', blank=True, db_index=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING)
    sent_at = models.DateTimeField(null=True, blank=True)
    opened_at = models.DateTimeField(null=True, blank=True)
    error_message = models.TextField(blank=True)

    class Meta:
        db_table = 'email_deliveries'
        unique_together = [['campaign', 'recipient']]


class UserContentInteraction(models.Model):
    user = models.ForeignKey('Users', on_delete=models.CASCADE, related_name='interactions')
    content = models.ForeignKey(AwarenessContent, on_delete=models.CASCADE, related_name='interactions')
    viewed = models.BooleanField(default=False)
    viewed_at = models.DateTimeField(null=True, blank=True)
    quiz_completed = models.BooleanField(default=False)

    class Meta:
        db_table = 'user_content_interactions'
        unique_together = [['user', 'content']]


class Group(DjangoGroup):
    group_id = models.AutoField(primary_key=True)
    admin = models.ForeignKey(
        'Users',
        on_delete=models.CASCADE,
        related_name='managed_group',
        limit_choices_to={'role': ROLE_ANALYST},
        null=True,
        blank=True
    )
    superadmin = models.ForeignKey(
        'Users',
        on_delete=models.CASCADE,
        related_name='supervised_groups',
        limit_choices_to={'role': ROLE_ANALYST},
        null=True,
        blank=True
    )

    class Meta:
        db_table = 'groups'

    def __str__(self):
        if self.admin:
            return f"Group(name={self.name}, admin={self.admin.email})"
        elif self.superadmin:
            return f"Group(name={self.name}, superadmin={self.superadmin.email})"
        else:
            return f"Group(name={self.name})"


