"""Password and sign-in: add or change a password (also for Google-only accounts), connect or disconnect Google,
and reset a forgotten password by email."""
import logging

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import update_session_auth_hash
from django.contrib.auth import views as auth_views
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import PasswordChangeForm, PasswordResetForm, SetPasswordForm
from django.core.mail import EmailMultiAlternatives
from django.shortcuts import redirect, render
from django.template.loader import render_to_string
from django.urls import reverse_lazy
from django.utils import timezone

from .models import Users
from .services.email_service import _send_with_retry, _strip_html
from .services.ratelimit import RateLimitError, client_key, hit
from .services.text import no_em_dash

logger = logging.getLogger(__name__)
_INPUT = 'w-full px-3 py-2 border border-on-surface focus:outline-none focus:border-2 focus:border-teal text-sm bg-white'


def _style(form):
    for field in form.fields.values():
        field.widget.attrs.setdefault('class', _INPUT)
    return form


def _google_account(user):
    from allauth.socialaccount.models import SocialAccount
    return SocialAccount.objects.filter(user=user, provider='google').first()


def _site():
    return getattr(settings, 'SITE_URL', 'http://localhost:8000').rstrip('/')


def notify_password_changed(user, request, added=False):
    """Security notice by email after a password is added or changed. Never blocks the change if email fails."""
    when = timezone.localtime().strftime('%a %d %b %Y, %H:%M %Z')
    html = no_em_dash(render_to_string('account_pages/emails/password_changed.html', {
        'user': user, 'added': added, 'when': when, 'site': _site(),
        'reset_url': _site() + str(reverse_lazy('password_reset')),
    }))
    msg = EmailMultiAlternatives(subject='Your Guardian password was ' + ('added' if added else 'changed'),
                                 body=_strip_html(html), from_email=settings.DEFAULT_FROM_EMAIL, to=[user.email])
    msg.attach_alternative(html, 'text/html')
    try:
        _send_with_retry(msg)
    except Exception as e:
        logger.warning('Password-change notice to user #%s failed: %s', user.pk, type(e).__name__)


@login_required(login_url='login_user')
def security(request):
    user = request.user
    if request.session.get('via_practice_link'):
        return render(request, 'account_pages/security.html', {'link_session': True})
    google = _google_account(user)
    has_password = user.has_usable_password()
    FormClass = PasswordChangeForm if has_password else SetPasswordForm
    form = _style(FormClass(user))

    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'password':
            form = _style(FormClass(user, request.POST))
            if form.is_valid():
                form.save()
                update_session_auth_hash(request, form.user)        # stay signed in on this device
                notify_password_changed(form.user, request, added=not has_password)
                messages.success(request, 'Password added. You can now sign in with your email and password too.'
                                 if not has_password else 'Password changed.')
                return redirect('account_security')
        elif action == 'disconnect_google' and google:
            if not has_password:
                messages.error(request, 'Add a password first, so you can still sign in after Google is disconnected.')
            else:
                google.delete()
                messages.success(request, 'Google disconnected. Sign in with your email and password from now on.')
            return redirect('account_security')

    from .views import _google_login_enabled
    return render(request, 'account_pages/security.html', {
        'form': form, 'has_password': has_password, 'google': google,
        'google_email': (google.extra_data.get('email') if google else ''),
        'google_enabled': _google_login_enabled(),
    })


class FamilyPasswordResetForm(PasswordResetForm):
    """Like Django's, but Google-only accounts can use it to add a password (Django skips unusable passwords)."""

    def get_users(self, email):
        return (u for u in Users.objects.filter(email__iexact=email, is_active=True) if u.email.lower() == email.lower())

    def send_mail(self, subject_template_name, email_template_name, context, from_email, to_email,
                  html_email_template_name=None):
        subject = ''.join(render_to_string(subject_template_name, context).splitlines())
        html = no_em_dash(render_to_string(html_email_template_name, context))
        msg = EmailMultiAlternatives(no_em_dash(subject), _strip_html(html), from_email, [to_email])
        msg.attach_alternative(html, 'text/html')
        try:
            _send_with_retry(msg)
        except Exception as e:
            logger.warning('Password reset email failed: %s', type(e).__name__)


class PasswordReset(auth_views.PasswordResetView):
    form_class = FamilyPasswordResetForm
    template_name = 'account_pages/reset_request.html'
    subject_template_name = 'account_pages/emails/reset_subject.txt'
    email_template_name = 'account_pages/emails/reset_email.html'
    html_email_template_name = 'account_pages/emails/reset_email.html'
    success_url = reverse_lazy('password_reset_done')

    def get_form(self, form_class=None):
        return _style(super().get_form(form_class))

    def form_valid(self, form):
        try:   # at most 5 reset emails per hour from one device, and 3 per hour to one address
            hit(f'rl:reset:{client_key(self.request)}', 5, 3600, 'password reset')
            hit(f'rl:reset:addr:{form.cleaned_data["email"].lower()}', 3, 3600, 'password reset address')
        except RateLimitError:
            return redirect(self.success_url)        # same page either way: never reveal whether an account exists
        self.extra_email_context = {'site': _site()}
        from urllib.parse import urlsplit
        site = urlsplit(_site())        # links use SITE_URL, like every other Guardian email (not the sites table)
        form.save(domain_override=site.netloc or self.request.get_host(), use_https=site.scheme == 'https',
                  request=self.request,
                  from_email=settings.DEFAULT_FROM_EMAIL, subject_template_name=self.subject_template_name,
                  email_template_name=self.email_template_name, html_email_template_name=self.html_email_template_name,
                  extra_email_context=self.extra_email_context)
        return redirect(self.success_url)


class PasswordResetDone(auth_views.PasswordResetDoneView):
    template_name = 'account_pages/reset_done.html'


class PasswordResetConfirm(auth_views.PasswordResetConfirmView):
    template_name = 'account_pages/reset_confirm.html'
    success_url = reverse_lazy('password_reset_complete')
    post_reset_login = True
    post_reset_login_backend = 'django.contrib.auth.backends.ModelBackend'

    def get_form(self, form_class=None):
        return _style(super().get_form(form_class))

    def form_valid(self, form):
        added = not form.user.has_usable_password()
        response = super().form_valid(form)
        notify_password_changed(form.user, self.request, added=added)
        return response


class PasswordResetComplete(auth_views.PasswordResetCompleteView):
    template_name = 'account_pages/reset_complete.html'
