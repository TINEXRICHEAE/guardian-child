"""Family topics and practice messages: analyst review, parent news, child lessons, practice links (plan.md §8.0)."""
from django.conf import settings
from django.contrib import messages
from django.contrib.auth import login, logout
from django.db import transaction
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from awarenessapp.models import AwarenessContent, QuizAttempt, QuizAttemptAnswer, ROLE_CHILD, UserContentInteraction, Users
from awarenessapp.permissions import child_required, parent_required
from awarenessapp.views import _require_perm
from safety.models import ChildProfile, GuardianChildLink

from .models import ChildVersionRequest, ParentLessonEdit, PracticeDelivery, TopicPack
from .services import autogen, versions
from .services.generate import fit_field, generate_pack, recheck
from .services.sender import send_pack_to_children, why_not_eligible

LINK_SESSION_KEY = 'via_practice_link'


# ── Analyst: family versions of an approved topic ──

def _back(request, pk):
    """After an action, return to the campaign page it came from (if any), else the Family versions page."""
    nxt = request.POST.get('next', '')
    if nxt.startswith('/') and not nxt.startswith('//'):
        return redirect(nxt)
    return redirect('panel_pack', pk=pk)


@_require_perm('manage_content')
def panel_pack(request, pk):
    content = get_object_or_404(AwarenessContent, pk=pk)
    pack = TopicPack.objects.filter(content=content).select_related('child_quiz').first()
    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'generate':
            if content.status not in (AwarenessContent.STATUS_APPROVED, AwarenessContent.STATUS_SENT):
                messages.error(request, 'Approve the topic first, then prepare the family versions.')
                return _back(request, pk)
            if (autogen.status(content.pk) or {}).get('state') == 'running':
                messages.error(request, 'Family versions are already being prepared. This page refreshes when they are ready.')
                return _back(request, pk)
            try:
                generate_pack(content, user=request.user)
                messages.success(request, 'Family versions prepared. Review them, then publish to families.')
            except ValueError as e:
                messages.error(request, str(e))
        elif action == 'save' and pack:
            shortened = []
            for field in ('parent_summary', 'parent_why', 'child_title', 'child_story', 'child_action',
                          'practice_sender', 'practice_subject', 'practice_body', 'practice_sms'):
                if field in request.POST:
                    value, cut = fit_field(TopicPack, field, request.POST[field])
                    setattr(pack, field, value)
                    if cut:
                        shortened.append(TopicPack._meta.get_field(field).verbose_name)
            for field in ('parent_tips', 'child_points'):
                if field in request.POST:
                    setattr(pack, field, [line.strip() for line in request.POST[field].splitlines() if line.strip()])
            pack.safety_warnings = recheck(pack)
            pack.save()
            if shortened:
                messages.warning(request, f'Shortened to fit: {", ".join(shortened)}. Check the end of the text.')
            messages.success(request, 'Saved.' + (' Check the safety notes below.' if pack.safety_warnings else ''))
        elif action == 'publish' and pack:
            if pack.safety_warnings and not request.POST.get('override'):
                messages.error(request, 'Fix the safety notes first (or tick "publish anyway" if you have checked them).')
                return _back(request, pk)
            sent = versions.publish(pack)
            messages.success(request, f'Published to families.{f" {sent} automatic practice email(s) sent." if sent else ""}')
        elif action == 'revert_edit' and pack:
            edit = get_object_or_404(ParentLessonEdit, pk=request.POST.get('edit'), pack=pack)
            versions.revert_edit(edit, request.user, request.POST.get('note', ''))
            messages.success(request, f'Reverted {edit.parent.email}\'s edit. Their children now get Guardian\'s original wording.')
        elif action == 'unpublish' and pack:
            pack.status = TopicPack.STATUS_DRAFT
            pack.save(update_fields=['status'])
            messages.success(request, 'Moved back to draft. Parents no longer see it.')
        return _back(request, pk)
    deliveries = pack.deliveries.all() if pack else []
    return render(request, 'panel/pack.html', {
        'content': content, 'pack': pack, 'auto': autogen.status(content.pk),
        'edits': pack.parent_edits.select_related('parent', 'reviewed_by') if pack else [],
        'requests': ChildVersionRequest.objects.filter(content=content).select_related('parent'),
        'stats': {
            'Sent': sum(d.status == 'sent' for d in deliveries),
            'Opened link': sum(bool(d.clicked_at) for d in deliveries),
            'Read lesson': sum(bool(d.lesson_viewed_at) for d in deliveries),
            'Did quiz': sum(bool(d.quiz_attempt_id) for d in deliveries),
            'Spotted and checked': sum(bool(d.reported_at) for d in deliveries),
        },
    })


# ── Parent: news for families (the parent library: every published topic, its article, quiz and practice message) ──

def _own_children(parent):
    return [link.child for link in GuardianChildLink.objects.filter(guardian=parent, active=True).select_related('child').order_by('child__nickname')]


def family_topics():
    """Topics parents can see: approved (or already emailed) analyst content, newest first."""
    return (AwarenessContent.objects.filter(status__in=(AwarenessContent.STATUS_APPROVED, AwarenessContent.STATUS_SENT))
            .select_related('quiz').order_by('-created_at'))


def _published_pack(content):
    return TopicPack.objects.filter(content=content, status=TopicPack.STATUS_PUBLISHED).select_related('child_quiz').first()


def _grade(request, quiz, questions):
    """Save one quiz attempt from POST data; returns the result dict the templates show."""
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
    return {'attempt': attempt, 'chosen': {q.pk: getattr(choice, 'pk', None) for q, choice, _ in answers}}


@parent_required
def parent_news(request):
    children = _own_children(request.user)
    topics = list(family_topics())
    packs = {p.content_id: p for p in TopicPack.objects.filter(status=TopicPack.STATUS_PUBLISHED, content__in=topics)}
    seen = {i.content_id: i for i in UserContentInteraction.objects.filter(user=request.user, content__in=topics)}
    sent = {}
    for d in PracticeDelivery.objects.filter(child__in=children, status='sent').select_related('child', 'pack'):
        sent.setdefault(d.pack.content_id, []).append(d.child)
    rows = [{'content': c, 'pack': packs.get(c.pk), 'read': bool(seen.get(c.pk) and seen[c.pk].viewed),
             'quiz_done': bool(seen.get(c.pk) and seen[c.pk].quiz_completed), 'sent_to': sent.get(c.pk, [])}
            for c in topics]
    return render(request, 'parent/news.html', {
        'unread': [r for r in rows if not r['read']], 'read': [r for r in rows if r['read']], 'children': children})


@parent_required
def parent_news_detail(request, pk):
    content = get_object_or_404(family_topics(), pk=pk)
    pack = _published_pack(content)
    children = _own_children(request.user)
    quiz = getattr(content, 'quiz', None) or (pack.child_quiz if pack else None)
    questions = list(quiz.questions.prefetch_related('choices').order_by('order')) if quiz else []

    interaction, _ = UserContentInteraction.objects.get_or_create(user=request.user, content=content)
    if not interaction.viewed:
        interaction.viewed, interaction.viewed_at = True, timezone.now()
        interaction.save(update_fields=['viewed', 'viewed_at'])

    result, edit_errors = None, []
    action = request.POST.get('action') if request.method == 'POST' else None
    if action == 'quiz' and questions:
        result = _grade(request, quiz, questions)
        interaction.quiz_completed = True
        interaction.save(update_fields=['quiz_completed'])
    elif action == 'request_child_version':
        if pack is None:
            versions.request_child_version(content, request.user)
            messages.success(request, 'Thanks. Guardian\'s analysts have been asked to prepare the child lesson and '
                                      'practice message. We will email you when they are ready.')
        return redirect(reverse('parent_news_detail', args=[pk]) + '#send')
    elif action == 'save_edit' and pack:
        edit, edit_errors = versions.save_parent_edit(pack, request.user, request.POST)
        if edit:
            messages.success(request, 'Saved. Your children will get your wording. Guardian\'s analysts can see edits.')
            return redirect(reverse('parent_news_detail', args=[pk]) + '#child-lesson')
    elif action == 'send_notice':
        child = next((c for c in children if str(c.pk) == request.POST.get('child')), None)
        if child is None:
            raise Http404
        from .services.sender import send_notice
        if send_notice(child):
            messages.success(request, f'Welcome note sent to {child.nickname}. You can now send the practice message and lesson.')
        else:
            messages.error(request, f'The welcome note to {child.nickname} could not be sent. Check the email address in '
                                    'My family, then try again.')
        return redirect(reverse('parent_news_detail', args=[pk]) + '#send')
    elif action == 'reset_edit' and pack:
        ParentLessonEdit.objects.filter(pack=pack, parent=request.user).delete()
        messages.success(request, 'Back to Guardian\'s original wording.')
        return redirect(reverse('parent_news_detail', args=[pk]) + '#child-lesson')
    elif request.method == 'POST':
        if pack is None:
            messages.error(request, 'The child version of this topic is not ready yet.')
            return redirect('parent_news_detail', pk=pk)
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

    deliveries = {d.child_id: d for d in pack.deliveries.filter(child__in=children).select_related('quiz_attempt')} if pack else {}
    rows = [{'child': c, 'delivery': deliveries.get(c.pk), 'reason': why_not_eligible(c)} for c in children]
    last = QuizAttempt.objects.filter(user=request.user, quiz=quiz).order_by('-completed_at').first() if quiz else None
    my_edit = ParentLessonEdit.objects.filter(pack=pack, parent=request.user).first() if pack else None
    return render(request, 'parent/news_detail.html', {
        'content': content, 'pack': pack, 'rows': rows, 'quiz': quiz, 'questions': questions, 'result': result,
        'last_attempt': last, 'children': children, 'edit_errors': edit_errors,
        'preview_name': children[0].nickname if len(children) == 1 else 'your child',
        'v': versions.version_for_parent(pack, request.user) if pack else None, 'my_edit': my_edit,
        'form_data': request.POST if edit_errors else None,
        'child_request': ChildVersionRequest.objects.filter(content=content, parent=request.user, resolved_at__isnull=True).first(),
    })


# ── Child: lessons and quizzes (always available, practice link or not) ──

@child_required
def child_lessons(request):
    packs = TopicPack.objects.filter(status=TopicPack.STATUS_PUBLISHED)
    child = getattr(request.user, 'child_profile', None)
    done = set(QuizAttempt.objects.filter(user=request.user).values_list('quiz_id', flat=True))
    rows = [{'pack': p, 'v': versions.version_for_child(p, child)} for p in packs]
    return render(request, 'child/lessons.html', {'rows': rows, 'done': done, 'child': child,
                                                  'name': getattr(child, 'nickname', '')})


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
        g = _grade(request, quiz, questions)
        if delivery and not delivery.quiz_attempt_id:
            delivery.quiz_attempt = g['attempt']
            delivery.save(update_fields=['quiz_attempt'])
        result = {'attempt': g['attempt']}
    return render(request, 'child/lesson.html', {'pack': pack, 'delivery': delivery, 'questions': questions,
                                                 'v': versions.version_for_child(pack, child, delivery),
                                                 'name': getattr(child, 'nickname', ''),
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
