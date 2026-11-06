"""Family topics and practice messages: analyst review, parent news, child lessons, practice links (plan.md §8.0)."""
from django.conf import settings
from django.contrib import messages
from django.contrib.auth import login, logout
from django.db import transaction
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from awarenessapp.models import AwarenessContent, QuizAttempt, QuizAttemptAnswer, ROLE_CHILD, Users
from awarenessapp.permissions import child_required, parent_required
from awarenessapp.views import _require_perm
from safety.models import ChildProfile, GuardianChildLink

from .models import PracticeDelivery, TopicPack
from .services.generate import generate_pack, recheck
from .services.sender import automate_for_published, send_pack_to_children, why_not_eligible

LINK_SESSION_KEY = 'via_practice_link'


# ── Analyst: family versions of an approved topic ──

@_require_perm('manage_content')
def panel_pack(request, pk):
    content = get_object_or_404(AwarenessContent, pk=pk)
    pack = TopicPack.objects.filter(content=content).select_related('child_quiz').first()
    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'generate':
            if content.status not in (AwarenessContent.STATUS_APPROVED, AwarenessContent.STATUS_SENT):
                messages.error(request, 'Approve the topic first, then prepare the family versions.')
                return redirect('panel_pack', pk=pk)
            try:
                generate_pack(content, user=request.user)
                messages.success(request, 'Family versions prepared. Review them, then publish to families.')
            except ValueError as e:
                messages.error(request, str(e))
        elif action == 'save' and pack:
            for field in ('parent_summary', 'parent_why', 'child_title', 'child_story', 'child_action',
                          'practice_sender', 'practice_subject', 'practice_body', 'practice_sms'):
                if field in request.POST:
                    setattr(pack, field, request.POST[field].strip())
            for field in ('parent_tips', 'child_points'):
                if field in request.POST:
                    setattr(pack, field, [line.strip() for line in request.POST[field].splitlines() if line.strip()])
            pack.safety_warnings = recheck(pack)
            pack.save()
            messages.success(request, 'Saved.' + (' Check the safety notes below.' if pack.safety_warnings else ''))
        elif action == 'publish' and pack:
            if pack.safety_warnings and not request.POST.get('override'):
                messages.error(request, 'Fix the safety notes first (or tick "publish anyway" if you have checked them).')
                return redirect('panel_pack', pk=pk)
            pack.status, pack.published_at = TopicPack.STATUS_PUBLISHED, timezone.now()
            pack.save(update_fields=['status', 'published_at'])
            sent = automate_for_published(pack)
            messages.success(request, f'Published to families.{f" {sent} automatic practice email(s) sent." if sent else ""}')
        elif action == 'unpublish' and pack:
            pack.status = TopicPack.STATUS_DRAFT
            pack.save(update_fields=['status'])
            messages.success(request, 'Moved back to draft. Parents no longer see it.')
        return redirect('panel_pack', pk=pk)
    deliveries = pack.deliveries.all() if pack else []
    return render(request, 'panel/pack.html', {
        'content': content, 'pack': pack,
        'stats': {
            'Sent': sum(d.status == 'sent' for d in deliveries),
            'Opened link': sum(bool(d.clicked_at) for d in deliveries),
            'Read lesson': sum(bool(d.lesson_viewed_at) for d in deliveries),
            'Did quiz': sum(bool(d.quiz_attempt_id) for d in deliveries),
            'Spotted and checked': sum(bool(d.reported_at) for d in deliveries),
        },
    })


# ── Parent: news for families ──

def _own_children(parent):
    return [link.child for link in GuardianChildLink.objects.filter(guardian=parent, active=True).select_related('child').order_by('child__nickname')]


@parent_required
def parent_news(request):
    packs = TopicPack.objects.filter(status=TopicPack.STATUS_PUBLISHED).select_related('content')
    children = _own_children(request.user)
    sent = {(d.pack_id, d.child_id): d for d in PracticeDelivery.objects.filter(child__in=children)}
    rows = [{'pack': p, 'sent_to': [c for c in children if (p.pk, c.pk) in sent and sent[(p.pk, c.pk)].status == 'sent']}
            for p in packs]
    return render(request, 'parent/news.html', {'rows': rows, 'children': children})


@parent_required
def parent_news_detail(request, pk):
    pack = get_object_or_404(TopicPack, pk=pk, status=TopicPack.STATUS_PUBLISHED)
    children = _own_children(request.user)
    if request.method == 'POST':
        chosen = [c for c in children if str(c.pk) in request.POST.getlist('children')]
        if not chosen:
            messages.error(request, 'Choose at least one child.')
        else:
            results = send_pack_to_children(pack, request.user, chosen)
            ok = [d.child.nickname for d in results if d.status == 'sent']
            skipped = [f'{d.child.nickname} ({d.skip_reason or d.status})' for d in results if d.status != 'sent']
            if ok:
                messages.success(request, f'Practice message sent to {", ".join(ok)}.')
            if skipped:
                messages.warning(request, f'Not sent: {"; ".join(skipped)}.')
        return redirect('parent_news_detail', pk=pk)
    deliveries = {d.child_id: d for d in pack.deliveries.filter(child__in=children).select_related('quiz_attempt')}
    rows = [{'child': c, 'delivery': deliveries.get(c.pk), 'reason': why_not_eligible(c)} for c in children]
    return render(request, 'parent/news_detail.html', {'pack': pack, 'rows': rows})


# ── Child: lessons and quizzes (always available, practice link or not) ──

@child_required
def child_lessons(request):
    packs = TopicPack.objects.filter(status=TopicPack.STATUS_PUBLISHED)
    child = getattr(request.user, 'child_profile', None)
    done = set(QuizAttempt.objects.filter(user=request.user).values_list('quiz_id', flat=True))
    return render(request, 'child/lessons.html', {'packs': packs, 'done': done, 'child': child})


@child_required
def lesson(request, pk):
    pack = get_object_or_404(TopicPack, pk=pk, status=TopicPack.STATUS_PUBLISHED)
    child = getattr(request.user, 'child_profile', None)
    delivery = None
    did = request.GET.get('d') or request.POST.get('d')
    if did and child:
        delivery = PracticeDelivery.objects.filter(pk=did, child=child, pack=pack).first()
        if delivery and not delivery.lesson_viewed_at:
            delivery.lesson_viewed_at = timezone.now()
            delivery.save(update_fields=['lesson_viewed_at'])

    quiz = pack.child_quiz
    questions = list(quiz.questions.prefetch_related('choices')) if quiz else []
    result = None
    if request.method == 'POST' and quiz:
        with transaction.atomic():
            answers, score = [], 0
            for q in questions:
                choice = next((c for c in q.choices.all() if str(c.pk) == request.POST.get(f'q{q.pk}')), None)
                correct = bool(choice and choice.is_correct)
                score += correct
                answers.append((q, choice, correct))
            attempt = QuizAttempt.objects.create(user=request.user, quiz=quiz, score=score, total=len(questions))
            for q, choice, correct in answers:
                QuizAttemptAnswer.objects.create(attempt=attempt, question=q, selected_choice=choice, is_correct=correct)
            if delivery and not delivery.quiz_attempt_id:
                delivery.quiz_attempt = attempt
                delivery.save(update_fields=['quiz_attempt'])
        result = {'attempt': attempt, 'answers': {q.pk: (choice, correct) for q, choice, correct in answers}}
    return render(request, 'child/lesson.html', {'pack': pack, 'delivery': delivery, 'questions': questions,
                                                 'result': result, 'via_link': bool(request.session.get(LINK_SESSION_KEY))})


# ── Public: practice links and the welcome notice "stop" link ──

def practice_open(request, token):
    """Sign the child straight in from their practice message, then show the topic lesson (plan.md §8.6)."""
    delivery = (PracticeDelivery.objects.filter(token=token, status='sent')
                .select_related('child', 'child__user', 'pack').first())
    if delivery is None or not delivery.pack.is_published or why_not_eligible_for_link(delivery.child):
        return render(request, 'phishsim/expired.html', status=410)
    child = delivery.child
    delivery.click_count += 1
    if not delivery.clicked_at:
        delivery.clicked_at = timezone.now()
    delivery.save(update_fields=['click_count', 'clicked_at'])

    user = child.user
    if user is None:
        user = Users.objects.filter(email__iexact=child.email).first()
        if user is not None and (user.role != ROLE_CHILD or getattr(user, 'child_profile', None)):
            return render(request, 'phishsim/expired.html', status=409)
        with transaction.atomic():
            if user is None:
                user = Users.objects.create_user(email=child.email, password=None, role=ROLE_CHILD)
                user.set_unusable_password()
                user.save(update_fields=['password'])
            child.user = user
            child.save(update_fields=['user'])
    if request.user.is_authenticated and request.user != user:
        logout(request)
    login(request, user, backend='django.contrib.auth.backends.ModelBackend')
    request.session[LINK_SESSION_KEY] = delivery.pk
    request.session.set_expiry(settings.GUARDIAN_LEARNER_SESSION_DAYS * 86400)
    return redirect(f"{_lesson_url(delivery.pack)}?d={delivery.pk}")


def why_not_eligible_for_link(child) -> str:
    """Links keep working after sending unless consent was revoked or the address blocked."""
    from safety.models import ConsentRecord
    if child.email_blocked:
        return 'blocked'
    if not ConsentRecord.active(child, ConsentRecord.KIND_SIMULATION):
        return 'consent revoked'
    return ''


def _lesson_url(pack):
    from django.urls import reverse
    return reverse('lesson', args=[pack.pk])


def practice_stop(request, token):
    child = ChildProfile.objects.filter(block_token=token).first()
    if child is None:
        raise Http404
    if request.method == 'POST':
        child.email_blocked = True
        child.save(update_fields=['email_blocked'])
        return render(request, 'phishsim/stopped.html', {'done': True})
    return render(request, 'phishsim/stopped.html', {'done': False, 'token': token})
