"""Family portal and child/parent safety pages (plan.md §5.4, §7.5)."""
from datetime import timedelta
from django.conf import settings
from django.contrib import messages
from django.contrib.auth import login
from django.db import transaction
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from awarenessapp.models import ROLE_CHILD, Users
from awarenessapp.permissions import child_required, parent_required, role_home_url
from awarenessapp.services.ratelimit import rate_limit

from .forms import ChildForm, PairForm
from .models import (ChildProfile, ConsentRecord, GuardianChildLink, GuardianPreference, IncidentReport, PairingCode,
                     ParentAlert, Submission)
from .services import checks
from .services.analysis import analyse

# What a parent can and cannot see; shown at pairing and on the child's family page (plan.md §1.2).
VISIBILITY = {
    'can': [
        'A short alert if a check you make is high risk: the type of scam and what to do, never the message itself.',
        'Which practice emails you received, whether you opened the lesson, and your quiz scores.',
        'Lessons you have read and your quiz scores in the library.',
    ],
    'cannot': [
        'The messages, links, screenshots or files you check.',
        'Reports you mark as private.',
        'Your chats, browsing or anything else on your phone.',
    ],
}


def _own_child(request, pk) -> ChildProfile:
    """A child linked to the logged-in parent, or 404 (never reveal other families' children)."""
    child = (ChildProfile.objects
             .filter(pk=pk, guardian_links__guardian=request.user, guardian_links__active=True)
             .first())
    if child is None:
        raise Http404
    return child


def _welcome(child):
    """Send the welcome notice (with its 'this isn't me' link) the first time practice emails are turned on."""
    from phishsim.services.sender import send_notice
    send_notice(child)


@parent_required
def parent_home(request):
    links = (GuardianChildLink.objects.filter(guardian=request.user, active=True)
             .select_related('child', 'child__user').order_by('child__nickname'))
    children = []
    for link in links:
        c = link.child
        children.append({
            'child': c,
            'practice': ConsentRecord.active(c, ConsentRecord.KIND_SIMULATION),
            'alerts': ConsentRecord.active(c, ConsentRecord.KIND_ALERTS),
            'flagged': c.alerts.filter(parent=request.user).count(),
        })
    week = timezone.now() - timedelta(days=7)
    alerts = ParentAlert.objects.filter(parent=request.user)
    return render(request, 'parent/dashboard.html', {
        'children': children, 'nav': 'overview',
        'summary': {
            'children': len(children),
            'paired': sum(1 for row in children if row['child'].is_paired),
            'alerts_week': alerts.filter(created_at__gte=week).count(),
            'unread': alerts.filter(read_at__isnull=True).count(),
        },
        'recent_alerts': alerts.select_related('child')[:3],
    })


@parent_required
def child_add(request):
    form = ChildForm(request.POST or None, parent=request.user)
    if request.method == 'POST' and form.is_valid():
        with transaction.atomic():
            child = form.save(commit=False)
            child.created_by = request.user
            child.save()
            GuardianChildLink.objects.create(guardian=request.user, child=child)
            ConsentRecord.grant(request.user, child, ConsentRecord.KIND_NOTICE)
            if request.POST.get('alerts'):
                ConsentRecord.grant(request.user, child, ConsentRecord.KIND_ALERTS)
            practice = bool(request.POST.get('practice') and child.email)
            told_child = bool(request.POST.get('told_child'))
            if practice and told_child:
                ConsentRecord.grant(request.user, child, ConsentRecord.KIND_SIMULATION, told_child=True)
                transaction.on_commit(lambda: _welcome(child))
        messages.success(request, f'{child.nickname} has been added.')
        if practice and not told_child:
            messages.warning(request, 'Practice emails stay off until you confirm you have told your child.')
        return redirect('parent_home')
    return render(request, 'parent/child_form.html', {'form': form, 'adding': True})


@parent_required
def child_edit(request, pk):
    child = _own_child(request, pk)
    form = ChildForm(request.POST or None, instance=child, parent=request.user)
    if request.method == 'POST' and form.is_valid():
        form.save()
        if not child.email:
            ConsentRecord.revoke(child, ConsentRecord.KIND_SIMULATION)   # nowhere to send practice emails
        messages.success(request, f'{child.nickname} has been updated.')
        return redirect('parent_home')
    return render(request, 'parent/child_form.html', {'form': form, 'child': child, 'adding': False})


@parent_required
@require_POST
def child_consent(request, pk):
    """Toggle one consent for one child. Practice emails need an email and the 'I told my child' confirmation."""
    child = _own_child(request, pk)
    kind = request.POST.get('kind')
    if kind not in (ConsentRecord.KIND_SIMULATION, ConsentRecord.KIND_ALERTS):
        raise Http404
    if request.POST.get('enable') == '1':
        if kind == ConsentRecord.KIND_SIMULATION:
            if not child.email:
                messages.error(request, f"Add {child.nickname}'s email before turning on practice emails.")
                return redirect('parent_home')
            if child.email_blocked:
                messages.error(request, "That email address asked us to stop. Practice emails can't be sent to it.")
                return redirect('parent_home')
            if not request.POST.get('told_child'):
                messages.error(request, f'Please confirm you have told {child.nickname} that practice messages may arrive.')
                return redirect('parent_home')
        ConsentRecord.grant(request.user, child, kind, told_child=bool(request.POST.get('told_child')))
        if kind == ConsentRecord.KIND_SIMULATION:
            _welcome(child)
        messages.success(request, 'Turned on.')
    else:
        ConsentRecord.revoke(child, kind)
        messages.success(request, 'Turned off. This takes effect immediately.')
    return redirect('parent_home')


@parent_required
@require_POST
@rate_limit('pairing-issue', 20, 3600)
def pairing_code(request, pk):
    child = _own_child(request, pk)
    if child.is_paired:
        messages.info(request, f'{child.nickname} is already paired.')
        return redirect('parent_home')
    code = PairingCode.issue(request.user, child)
    return render(request, 'parent/pairing_code.html', {
        'child': child, 'code': code, 'minutes': PairingCode.VALID_MINUTES,
    })


@rate_limit('pair', 10, 3600)
def pair(request):
    """Child's device: enter the family code, create a child account bound to the parent's ChildProfile."""
    if request.user.is_authenticated:
        return redirect(role_home_url(request.user))
    form = PairForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        user = _redeem(form.cleaned_data)
        if user is None:
            form.add_error('code', 'That code is not valid or has expired. Ask your parent for a new one.')
        else:
            user.backend = 'awarenessapp.backends.EmailBackend'
            login(request, user)
            return redirect('child_family')
    return render(request, 'safety/pair.html', {'form': form})


@transaction.atomic
def _redeem(data):
    """Use a pairing code once; returns the new child user, or None if the code is not redeemable."""
    pc = PairingCode.redeemable(data['code'])
    if pc is None:
        return None
    child = ChildProfile.objects.select_for_update().get(pk=pc.child_id)
    if child.is_paired:
        return None
    user = Users.objects.create_user(email=data['email'], password=data['password1'], role=ROLE_CHILD)
    child.user = user
    if not child.email:
        child.email = user.email
    child.save(update_fields=['user', 'email'])
    pc.used_at = timezone.now()
    pc.save(update_fields=['used_at'])
    return user


@child_required
def child_family(request):
    child = getattr(request.user, 'child_profile', None)
    guardians = []
    if child:
        guardians = [link.guardian for link in child.guardian_links.filter(active=True).select_related('guardian__profile')]
    return render(request, 'safety/child_family.html', {
        'child': child, 'guardians': guardians, 'visibility': VISIBILITY,
        'practice_on': bool(child and ConsentRecord.active(child, ConsentRecord.KIND_SIMULATION)),
    })


# ── Parent: alerts, settings, removing a child ──

@parent_required
def parent_alerts(request):
    alerts = ParentAlert.objects.filter(parent=request.user).select_related('child')
    if request.method == 'POST':
        alerts.filter(read_at__isnull=True).update(read_at=timezone.now())
        messages.success(request, 'All alerts marked as read.')
        return redirect('parent_alerts')
    return render(request, 'parent/alerts.html', {'alerts': alerts[:100], 'nav': 'alerts'})


@parent_required
def parent_settings(request):
    prefs = GuardianPreference.for_parent(request.user)
    fields = ['alert_high', 'alert_suspicious', 'alert_email', 'protect_fraud', 'protect_gambling', 'protect_adult',
              'auto_drills']
    if request.method == 'POST':
        for f in fields:
            setattr(prefs, f, bool(request.POST.get(f)))
        prefs.save()
        messages.success(request, 'Preferences saved.')
        return redirect('parent_settings')
    return render(request, 'parent/settings.html', {'prefs': prefs, 'nav': 'settings',
                                                    'max_per_month': settings.GUARDIAN_SIM_MAX_PER_MONTH})


@parent_required
@require_POST
def child_remove(request, pk):
    """Disconnect a child from this parent. The profile stays for any other linked guardian; consents are revoked."""
    child = _own_child(request, pk)
    GuardianChildLink.objects.filter(guardian=request.user, child=child).update(active=False)
    ConsentRecord.objects.filter(parent=request.user, child=child, revoked_at__isnull=True).update(revoked_at=timezone.now())
    messages.success(request, f'{child.nickname} was removed from your family.')
    return redirect('parent_home')


# ── "Is this safe?" for children and parents (plan.md §7.5) ──

_IMAGE_TYPES = {'image/png', 'image/jpeg', 'image/webp'}
_MAX_IMAGE = 5 * 1024 * 1024
EXAMPLES = [
    ('Reward example', 'Congratulations! You won UGX 500,000. Send your Mobile Money PIN to claim the cash reward.'),
    ('Scholarship example', 'You have a full scholarship. Pay a processing fee today.'),
    ('Link example', 'Airtel back-to-school bundle: claim 20GB free. Register at airtel-bonus.example before 6pm.'),
]


def _read_upload(request):
    """Return (bytes, mime, error). The upload stays in memory and is never saved."""
    f = request.FILES.get('screenshot')
    if not f:
        return None, '', None
    if f.content_type not in _IMAGE_TYPES or f.size > _MAX_IMAGE:
        return None, '', 'Choose a PNG, JPEG or WebP screenshot smaller than 5 MB.'
    return f.read(), f.content_type, None


def _check(request, *, role, template, result_url, extra):
    context = {'examples': EXAMPLES, **extra}
    if request.method == 'POST':
        text = request.POST.get('content', '').strip()
        image, mime, error = _read_upload(request)
        if error:
            context.update(error=error, content=text)
        elif not text and not image:
            context.update(error='Paste a message or link, or add a screenshot.', content=text)
        else:
            child = getattr(request.user, 'child_profile', None) if role == 'child' else None
            sub = analyse(user=request.user, role=role, child=child, text=text, image=image, mime=mime,
                          already_acted=bool(request.POST.get('already_acted')))
            return redirect(result_url, pk=sub.pk)
    return render(request, template, context)


@child_required
def child_home(request):
    child = getattr(request.user, 'child_profile', None)
    return render(request, 'child/home.html', {'child': child, 'nav': 'home'})


@child_required
@rate_limit('check', 30, 3600)
def child_check(request):
    return _check(request, role='child', template='child/check.html', result_url='child_result', extra={'nav': 'check'})


@child_required
def child_result(request, pk):
    sub = get_object_or_404(Submission, pk=pk, submitted_by=request.user)
    return render(request, 'child/result.html', {'sub': sub, 'nav': 'check'})


@child_required
def child_history(request):
    subs = Submission.objects.filter(submitted_by=request.user)[:30]
    return render(request, 'child/history.html', {'subs': subs, 'nav': 'history'})


@child_required
@rate_limit('report', 10, 3600)
def child_report(request):
    child = getattr(request.user, 'child_profile', None)
    context = {'nav': 'home', 'categories': IncidentReport.CATEGORY_CHOICES,
               'from_check': request.GET.get('from')}
    if request.method == 'POST':
        summary = request.POST.get('summary', '').strip()
        if len(summary) < 10:
            context.update(error='Please write a little more about what happened.', summary=summary)
            return render(request, 'child/report.html', context)
        confidential = bool(request.POST.get('confidential'))
        sensitive = checks.needs_safeguarding(summary)
        category = request.POST.get('category') if request.POST.get('category') in dict(IncidentReport.CATEGORY_CHOICES) else 'other'
        sub = Submission.objects.filter(pk=request.POST.get('submission') or 0, submitted_by=request.user).first()
        report = IncidentReport.objects.create(
            child=child, submitted_by=request.user, category=category, summary=checks.redact(summary)[:4000],
            confidential=confidential or sensitive, notify_parent=bool(request.POST.get('notify_parent')) and not confidential,
            needs_safeguarding=sensitive, status='restricted' if (confidential or sensitive) else 'new', submission=sub,
        )
        if child and report.notify_parent and not report.confidential:
            for link in child.guardian_links.filter(active=True):
                alert = ParentAlert.objects.create(parent=link.guardian, child=child, severity='high', source='report',
                                                   title=f'{child.nickname} reported: {report.get_category_display().lower()}',
                                                   safety_action='Talk with your child calmly. They chose to let you know.')
                from .services import alert_email
                alert_email.notify(alert)
        return render(request, 'child/report_done.html', {'report': report, 'sensitive': sensitive, 'nav': 'home'})
    return render(request, 'child/report.html', context)


@parent_required
@rate_limit('check', 30, 3600)
def parent_check(request):
    return _check(request, role='parent', template='parent/check.html', result_url='parent_result', extra={'nav': 'check'})


@parent_required
def parent_result(request, pk):
    sub = get_object_or_404(Submission, pk=pk, submitted_by=request.user)
    return render(request, 'parent/result.html', {'sub': sub, 'nav': 'check'})


# ── Public pages ──

SAFETY_STEPS = [
    'Stop replying or sending money.',
    'Do not share your PIN, password or one-time codes.',
    'If you already shared a password, use the official app or website to change it.',
    'Save the message only if it is safe to do so, and ask a trusted adult for help.',
]


def help_page(request):
    return render(request, 'app/help.html', {'steps': SAFETY_STEPS, 'nav': 'home'})


def privacy_page(request):
    return render(request, 'app/privacy.html', {'visibility': VISIBILITY, 'nav': 'home'})
