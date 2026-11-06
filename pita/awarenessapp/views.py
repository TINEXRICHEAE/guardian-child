import logging
import json
import os
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse
from django.http import JsonResponse
from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from django.utils import timezone
from django.db.models import Count, Q, Avg, F, FloatField, ExpressionWrapper
from django.core.paginator import Paginator
from django.middleware.csrf import get_token
from rest_framework.decorators import api_view
from rest_framework.response import Response

from .permissions import role_home_url
from .models import (
    Users, Profile,
    ContentSource, RawContent, AwarenessContent,
    Quiz, QuizChoice, QuizAttempt, QuizAttemptAnswer,
    EmailCampaign, EmailDelivery, UserContentInteraction,
    ROLE_CHILD, ROLE_PARENT,
)
from .services.ingestion import ingest_source
from .services.file_validators import validate_document_upload
from .services.transformation import transform_raw_content
from .services.email_service import send_campaign, build_email_body

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────

def _require_perm(perm):
    """Decorator: require a specific awarenessapp permission."""
    def decorator(view_func):
        @login_required(login_url='login_user')
        def wrapper(request, *args, **kwargs):
            if not request.user.has_perm(f'awarenessapp.{perm}'):
                messages.error(request, 'Access denied.')
                return redirect('home')
            return view_func(request, *args, **kwargs)
        return wrapper
    return decorator


# ──────────────────────────────────────────────
# Public / Auth views
# ──────────────────────────────────────────────

def _google_login_enabled() -> bool:
    """Google sign-in works if configured by env vars or by a SocialApp row (as the old database had)."""
    from django.conf import settings
    from allauth.socialaccount.models import SocialApp
    return settings.GOOGLE_LOGIN_ENABLED or SocialApp.objects.filter(provider='google').exists()


def home(request):
    from django.conf import settings
    return render(request, 'home.html', {
        'android_url': settings.GUARDIAN_ANDROID_APP_URL,
        'home_url': role_home_url(request.user) if request.user.is_authenticated else '',
        'stats': _live_stats(),
    })


def _live_stats() -> dict:
    """Real totals for the home page (cached briefly so the landing page stays fast)."""
    from django.core.cache import cache
    from safety.models import ChildProfile, Submission
    stats = cache.get('home:stats')
    if stats is None:
        stats = {
            'families': Users.objects.filter(role=ROLE_PARENT, is_active=True).count(),
            'children': ChildProfile.objects.count(),
            'checks': Submission.objects.count(),
            'flagged': Submission.objects.filter(risk_level__in=['high', 'suspicious']).count(),
            'quiz_attempts': QuizAttempt.objects.count(),
        }
        cache.set('home:stats', stats, 60)
    return stats


def register_user(request):
    if request.method == 'POST':
        from django.utils.http import url_has_allowed_host_and_scheme
        email = request.POST.get('email')
        password1 = request.POST.get('password1')
        password2 = request.POST.get('password2')
        next_url = request.POST.get('next', '').strip()
        if next_url and not url_has_allowed_host_and_scheme(next_url, allowed_hosts={request.get_host()}):
            next_url = ''

        if not email or not password1 or not password2:
            return JsonResponse({'error': 'All fields are required'}, status=400)
        if password1 != password2:
            return JsonResponse({'error': 'Passwords do not match'}, status=400)
        if Users.objects.filter(email=email).exists():
            return JsonResponse({'error': 'This email already has a Guardian account. Sign in instead (with Google if you used it before), or choose "Forgot password?" on the sign-in page.'}, status=400)

        user = Users.objects.create_user(email=email, password=password1, role=ROLE_PARENT)
        user.backend = 'awarenessapp.backends.EmailBackend'
        login(request, user)
        return JsonResponse({'message': 'Account created!', 'next': next_url or role_home_url(user)}, status=201)

    if request.user.is_authenticated:
        return redirect(role_home_url(request.user))   # already signed in: no second account
    next_url = request.GET.get('next', '')
    return render(request, 'signup.html', {'next': next_url, 'google_login_enabled': _google_login_enabled()})


def login_user(request):
    if request.method == 'POST':
        from django.utils.http import url_has_allowed_host_and_scheme
        email = request.POST.get('email')
        password = request.POST.get('password')

        if not email or not password:
            return JsonResponse({'error': 'Email and password are required'}, status=400)

        user = authenticate(request, email=email, password=password)
        if user is not None:
            login(request, user)
            next_url = request.GET.get('next') or request.POST.get('next') or role_home_url(user)
            if not url_has_allowed_host_and_scheme(next_url, allowed_hosts={request.get_host()}):
                next_url = role_home_url(user)
            return JsonResponse({'message': 'Login successful', 'user_id': user.id, 'email': user.email, 'role': user.role, 'next': next_url}, status=200)
        return JsonResponse({'error': 'Invalid email or password. If you signed up with Google, use the Google button, or choose "Forgot password?" to add a password.'}, status=401)

    next_url = request.GET.get('next', '')
    return render(request, 'login.html', {'next': next_url, 'google_login_enabled': _google_login_enabled()})


def check_auth(request):
    return JsonResponse({'is_authenticated': request.user.is_authenticated})


def logout_user(request):
    if request.method == 'POST':
        logout(request)
        return JsonResponse({'message': 'Logout successful'}, status=200)
    return JsonResponse({'error': 'Invalid request method'}, status=400)


@login_required(login_url='login_user')
def user_profile(request):
    if request.method == 'POST' and request.session.get('via_practice_link'):
        return JsonResponse({'status': 'error', 'message': 'Sign in with your password to change your account.'}, status=403)
    profile, _ = Profile.objects.get_or_create(user=request.user)

    if request.method == 'GET':
        if profile.picture_url:
            avatar_url = profile.picture_url
        elif profile.profile_picture and not os.getenv('VERCEL'):
            avatar_url = request.build_absolute_uri(profile.profile_picture.url)
        else:
            avatar_url = None
        return JsonResponse({
            'status': 'success',
            'email': request.user.email,
            'phonenumber': str(request.user.phonenumber) if request.user.phonenumber else None,
            'role': request.user.role,
            'full_name': profile.full_name,
            'avatar_url': avatar_url,
        })

    if request.method == 'POST':
        try:
            data = json.loads(request.body)

            phonenumber = data.get('phonenumber')
            if phonenumber is not None:
                request.user.phonenumber = phonenumber or None
                request.user.save(update_fields=['phonenumber'])

            profile_fields = ['full_name']
            update_fields = []
            for field in profile_fields:
                if field in data:
                    setattr(profile, field, data[field])
                    update_fields.append(field)
            if update_fields:
                profile.save(update_fields=update_fields)

            return JsonResponse({'status': 'success', 'message': 'Profile updated.'})
        except Exception:
            logger.exception("Profile update failed for user %s", request.user.id)
            return JsonResponse({'status': 'error', 'message': 'An error occurred updating your profile.'}, status=500)

    return JsonResponse({'status': 'error', 'message': 'Invalid method.'}, status=405)


@login_required(login_url='login_user')
def upload_profile_picture(request):
    if request.method == 'POST' and request.session.get('via_practice_link'):
        return JsonResponse({'status': 'error', 'message': 'Sign in with your password to change your account.'}, status=403)
    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'message': 'Invalid method.'}, status=405)
    profile, _ = Profile.objects.get_or_create(user=request.user)
    pic = request.FILES.get('profile_picture')
    if not pic:
        return JsonResponse({'status': 'error', 'message': 'No file provided.'}, status=400)
    if pic.size > 5 * 1024 * 1024:
        return JsonResponse({'status': 'error', 'message': 'File too large (max 5 MB).'}, status=400)
    if not pic.content_type.startswith('image/'):
        return JsonResponse({'status': 'error', 'message': 'Only image files are accepted.'}, status=400)

    if os.getenv('CLOUDINARY_CLOUD_NAME'):
        import cloudinary.uploader
        result = cloudinary.uploader.upload(
            pic,
            folder='guardian/profile_pictures',
            public_id=f'user_{request.user.id}',
            overwrite=True,
            transformation={'width': 400, 'height': 400, 'crop': 'fill', 'gravity': 'face'},
        )
        profile.picture_url = result['secure_url']
        profile.save(update_fields=['picture_url'])
        return JsonResponse({'status': 'success', 'avatar_url': result['secure_url']})

    if profile.profile_picture:
        profile.profile_picture.delete(save=False)
    profile.profile_picture = pic
    profile.save(update_fields=['profile_picture'])
    avatar_url = request.build_absolute_uri(profile.profile_picture.url)
    return JsonResponse({'status': 'success', 'avatar_url': avatar_url})


@login_required(login_url='login_user')
def delete_account(request):
    if request.method == 'POST' and request.session.get('via_practice_link'):
        return JsonResponse({'status': 'error', 'message': 'Sign in with your password to change your account.'}, status=403)
    if request.method == 'POST':
        try:
            # Soft-delete: deactivate the account
            request.user.is_active = False
            request.user.save(update_fields=['is_active'])
            logout(request)
            return JsonResponse({'status': 'success', 'message': 'Account deactivated.'})
        except Exception:
            logger.exception("Account deactivation failed for user %s", request.user.id)
            return JsonResponse({'status': 'error', 'message': 'An error occurred. Please try again.'}, status=500)
    return JsonResponse({'status': 'error', 'message': 'Invalid method.'}, status=405)


@api_view(['GET'])
def get_csrf_token(request):
    return Response({'csrfToken': get_token(request)})


# ──────────────────────────────────────────────
# Staff views
# ──────────────────────────────────────────────

def _family_redirect(request, content=None, quiz=None):
    """The old library is the analysts' view. Parents and children get the same topics in their own spaces,
    with their navigation and (for parents) sending to their children."""
    role = getattr(request.user, 'role', None)
    if role == ROLE_PARENT:
        if content is None and quiz is not None:
            content = quiz.content
            if content is None:
                from phishsim.models import TopicPack
                pack = TopicPack.objects.filter(child_quiz=quiz).select_related('content').first()
                content = pack.content if pack else None
        if content is not None and content.status in (AwarenessContent.STATUS_APPROVED, AwarenessContent.STATUS_SENT):
            return redirect(reverse('parent_news_detail', args=[content.pk]) + ('#quiz' if quiz else ''))
        return redirect('parent_news')
    if role == ROLE_CHILD:
        from phishsim.models import TopicPack
        pack = None
        if content is not None:
            pack = TopicPack.objects.filter(content=content, status=TopicPack.STATUS_PUBLISHED).first()
        elif quiz is not None:
            pack = TopicPack.objects.filter(child_quiz=quiz, status=TopicPack.STATUS_PUBLISHED).first()
        return redirect(reverse('lesson', args=[pack.pk])) if pack else redirect('child_lessons')
    return None


@login_required(login_url='login_user')
def library(request):
    if (r := _family_redirect(request)):
        return r
    threat_filter = request.GET.get('threat', '')
    search = request.GET.get('q', '').strip()

    contents = AwarenessContent.objects.filter(status=AwarenessContent.STATUS_APPROVED)
    if threat_filter:
        contents = contents.filter(threat_type=threat_filter)
    if search:
        contents = contents.filter(Q(title__icontains=search) | Q(risk__icontains=search))

    paginator = Paginator(contents, 12)
    page_obj = paginator.get_page(request.GET.get('page'))

    # Mark each as viewed / not
    viewed_ids = set()
    if request.user.is_authenticated:
        viewed_ids = set(
            UserContentInteraction.objects.filter(user=request.user, viewed=True)
            .values_list('content_id', flat=True)
        )

    from .models import INSIDER_THREAT_CHOICES
    ctx = {
        'page_obj': page_obj,
        'threat_filter': threat_filter,
        'search': search,
        'threat_choices': INSIDER_THREAT_CHOICES,
        'viewed_ids': viewed_ids,
    }
    return render(request, 'staff/library.html', ctx)


@login_required(login_url='login_user')
def content_view(request, pk):
    content = get_object_or_404(AwarenessContent, pk=pk, status__in=(AwarenessContent.STATUS_APPROVED, AwarenessContent.STATUS_SENT))
    if (r := _family_redirect(request, content=content)):
        return r

    # Record interaction
    interaction, _ = UserContentInteraction.objects.get_or_create(
        user=request.user, content=content,
        defaults={'viewed': True, 'viewed_at': timezone.now()},
    )
    if not interaction.viewed:
        interaction.viewed = True
        interaction.viewed_at = timezone.now()
        interaction.save(update_fields=['viewed', 'viewed_at'])

    quiz = getattr(content, 'quiz', None)
    user_attempt = None
    can_retake = False
    if quiz:
        user_attempt = QuizAttempt.objects.filter(user=request.user, quiz=quiz).order_by('-completed_at').first()
        attempts_taken = QuizAttempt.objects.filter(user=request.user, quiz=quiz).count()
        can_retake = attempts_taken < MAX_QUIZ_ATTEMPTS

    ctx = {'content': content, 'quiz': quiz, 'user_attempt': user_attempt, 'can_retake': can_retake}
    return render(request, 'staff/content_view.html', ctx)


@login_required(login_url='login_user')
def quizzes(request):
    if (r := _family_redirect(request)):
        return r
    quiz_list = Quiz.objects.filter(is_active=True).select_related('content').order_by('-created_at')
    attempt_counts = {
        row['quiz_id']: row['cnt']
        for row in QuizAttempt.objects.filter(user=request.user)
        .values('quiz_id')
        .annotate(cnt=Count('id'))
    }
    attempted_ids = set(attempt_counts.keys())
    maxed_ids = {qid for qid, cnt in attempt_counts.items() if cnt >= MAX_QUIZ_ATTEMPTS}
    paginator = Paginator(quiz_list, 12)
    page_obj = paginator.get_page(request.GET.get('page'))
    ctx = {'page_obj': page_obj, 'attempted_ids': attempted_ids, 'maxed_ids': maxed_ids}
    return render(request, 'staff/quizzes.html', ctx)


MAX_QUIZ_ATTEMPTS = 2


@login_required(login_url='login_user')
def take_quiz(request, pk):
    quiz = get_object_or_404(Quiz, pk=pk, is_active=True)
    if (r := _family_redirect(request, quiz=quiz)):
        return r
    questions = quiz.questions.prefetch_related('choices').all()

    prior_attempts = list(
        QuizAttempt.objects.filter(user=request.user, quiz=quiz).order_by('completed_at')
    )

    if request.method == 'POST':
        if len(prior_attempts) >= MAX_QUIZ_ATTEMPTS:
            messages.error(request, 'You have reached the maximum number of attempts for this quiz.')
            return redirect('quiz_review', attempt_pk=prior_attempts[-1].pk)

        score = 0
        total = questions.count()
        per_question = {}  # question pk → chosen QuizChoice or None
        for question in questions:
            selected_id = request.POST.get(f'q_{question.pk}')
            chosen = None
            if selected_id:
                try:
                    chosen = QuizChoice.objects.get(pk=selected_id, question=question)
                    if chosen.is_correct:
                        score += 1
                except QuizChoice.DoesNotExist:
                    pass
            per_question[question.pk] = chosen

        attempt = QuizAttempt.objects.create(user=request.user, quiz=quiz, score=score, total=total)

        QuizAttemptAnswer.objects.bulk_create([
            QuizAttemptAnswer(
                attempt=attempt,
                question_id=q_pk,
                selected_choice=chosen,
                is_correct=chosen.is_correct if chosen else False,
            )
            for q_pk, chosen in per_question.items()
        ])

        # Mark interaction as quiz_completed
        if quiz.content:
            UserContentInteraction.objects.update_or_create(
                user=request.user, content=quiz.content,
                defaults={'quiz_completed': True, 'viewed': True, 'viewed_at': timezone.now()},
            )

        return redirect('quiz_result', attempt_pk=attempt.pk)

    if len(prior_attempts) >= MAX_QUIZ_ATTEMPTS:
        messages.info(request, 'You have completed the maximum number of attempts for this quiz. Here is your latest review.')
        return redirect('quiz_review', attempt_pk=prior_attempts[-1].pk)

    ctx = {
        'quiz': quiz,
        'questions': questions,
        'attempt_number': len(prior_attempts) + 1,
        'max_attempts': MAX_QUIZ_ATTEMPTS,
    }
    return render(request, 'staff/take_quiz.html', ctx)


@login_required(login_url='login_user')
def quiz_result(request, attempt_pk):
    attempt = get_object_or_404(QuizAttempt, pk=attempt_pk, user=request.user)
    if (r := _family_redirect(request, quiz=attempt.quiz)):
        return r
    attempts_taken = QuizAttempt.objects.filter(user=request.user, quiz=attempt.quiz).count()
    ctx = {
        'attempt': attempt,
        'can_retake': attempts_taken < MAX_QUIZ_ATTEMPTS,
    }
    return render(request, 'staff/quiz_result.html', ctx)


@login_required(login_url='login_user')
def quiz_review(request, attempt_pk):
    attempt = get_object_or_404(QuizAttempt, pk=attempt_pk, user=request.user)
    if (r := _family_redirect(request, quiz=attempt.quiz)):
        return r
    answers = (
        attempt.question_answers
        .select_related('question', 'selected_choice')
        .prefetch_related('question__choices')
        .order_by('question__order')
    )
    attempts_taken = QuizAttempt.objects.filter(user=request.user, quiz=attempt.quiz).count()
    ctx = {
        'attempt': attempt,
        'answers': answers,
        'can_retake': attempts_taken < MAX_QUIZ_ATTEMPTS,
    }
    return render(request, 'staff/quiz_review.html', ctx)


@login_required(login_url='login_user')
def progress(request):
    if (r := _family_redirect(request)):
        return r
    interactions = UserContentInteraction.objects.filter(user=request.user).select_related('content')
    total_viewed = interactions.filter(viewed=True).count()

    # All attempts for this user, ordered chronologically per quiz
    all_attempts = list(
        QuizAttempt.objects
        .filter(user=request.user)
        .select_related('quiz')
        .order_by('quiz_id', 'completed_at')
    )
    total_quizzes = len(all_attempts)
    avg_score = round(
        (sum(a.percentage for a in all_attempts) / total_quizzes) if total_quizzes else 0, 1
    )

    # Group by quiz and attach attempt number + delta to each attempt object
    quiz_map = {}
    for attempt in all_attempts:
        qpk = attempt.quiz_id
        if qpk not in quiz_map:
            quiz_map[qpk] = {'quiz': attempt.quiz, 'attempts': []}
        idx = len(quiz_map[qpk]['attempts'])
        attempt.attempt_number = idx + 1
        prev = quiz_map[qpk]['attempts'][idx - 1] if idx > 0 else None
        attempt.attempt_delta = attempt.percentage - prev.percentage if prev else None
        quiz_map[qpk]['attempts'].append(attempt)

    progressions = []
    for data in quiz_map.values():
        attempts = data['attempts']
        first, latest = attempts[0], attempts[-1]
        progressions.append({
            'quiz': data['quiz'],
            'attempts': attempts,
            'attempt_count': len(attempts),
            'first_pct': first.percentage,
            'latest_pct': latest.percentage,
            'best_pct': max(a.percentage for a in attempts),
            'delta': latest.percentage - first.percentage if len(attempts) > 1 else None,
        })
    progressions.sort(key=lambda x: x['attempts'][-1].completed_at, reverse=True)

    recent_contents = AwarenessContent.objects.filter(
        status=AwarenessContent.STATUS_APPROVED
    ).order_by('-created_at')[:6]

    ctx = {
        'total_viewed': total_viewed,
        'total_quizzes': total_quizzes,
        'avg_score': avg_score,
        'quiz_count': len(progressions),
        'interactions': interactions,
        'recent_contents': recent_contents,
        'progressions': progressions,
    }
    return render(request, 'staff/progress.html', ctx)


# ──────────────────────────────────────────────
# Admin panel views
# ──────────────────────────────────────────────

@_require_perm('view_panel')
def panel_dashboard(request):
    ctx = {
        'total_sources': ContentSource.objects.count(),
        'total_raw': RawContent.objects.count(),
        'pending_review': AwarenessContent.objects.filter(status=AwarenessContent.STATUS_PENDING).count(),
        'approved': AwarenessContent.objects.filter(status=AwarenessContent.STATUS_APPROVED).count(),
        'total_campaigns': EmailCampaign.objects.count(),
        'sent_campaigns': EmailCampaign.objects.filter(status=EmailCampaign.STATUS_SENT).count(),
        'total_staff': Users.objects.filter(role=ROLE_CHILD).count(),
        'recent_contents': AwarenessContent.objects.order_by('-created_at')[:5],
        'recent_campaigns': EmailCampaign.objects.order_by('-created_at')[:5],
    }
    return render(request, 'panel/dashboard.html', ctx)


@_require_perm('manage_sources')
def panel_sources(request):
    sources = ContentSource.objects.select_related('created_by').order_by('-created_at')
    paginator = Paginator(sources, 15)
    page_obj = paginator.get_page(request.GET.get('page'))
    ctx = {'page_obj': page_obj}
    return render(request, 'panel/sources.html', ctx)


@_require_perm('manage_sources')
def panel_add_source(request):
    from .models import INSIDER_THREAT_CHOICES
    if request.method == 'POST':
        source_type = request.POST.get('source_type')
        name = request.POST.get('name', '').strip()
        threat_type = request.POST.get('threat_type')

        if not name or not source_type or not threat_type:
            messages.error(request, 'Name, source type and threat type are required.')
            return redirect('panel_add_source')

        source = ContentSource(
            created_by=request.user,
            name=name,
            source_type=source_type,
            threat_type=threat_type,
        )

        if source_type == ContentSource.SOURCE_TYPE_URL:
            api_url = request.POST.get('api_url', '').strip()
            if not api_url:
                messages.error(request, 'URL is required.')
                return redirect('panel_add_source')
            source.api_url = api_url
            source.fetch_frequency = request.POST.get('fetch_frequency', 'weekly')

        elif source_type == ContentSource.SOURCE_TYPE_DOCUMENT:
            doc = request.FILES.get('document')
            if not doc:
                messages.error(request, 'Document file is required.')
                return redirect('panel_add_source')
            ok, err = validate_document_upload(doc)
            if not ok:
                messages.error(request, err)
                return redirect('panel_add_source')
            if os.getenv('CLOUDINARY_CLOUD_NAME'):
                import cloudinary.uploader
                import re as _re
                safe_name = _re.sub(r'[^a-zA-Z0-9_-]', '_', name)[:80]
                file_ext = os.path.splitext(doc.name)[1].lower().lstrip('.')
                if file_ext == 'pdf':
                    # PDFs upload as image type, Cloudinary's native approach for
                    # PDFs; delivers publicly like any image, no auth complexity.
                    result = cloudinary.uploader.upload(
                        doc,
                        folder='guardian/source_documents',
                        resource_type='image',
                        public_id=safe_name,
                        overwrite=True,
                    )
                else:
                    # TXT files stay raw; access_mode='public' so they're
                    # directly downloadable server-side.
                    result = cloudinary.uploader.upload(
                        doc,
                        folder='guardian/source_documents',
                        resource_type='raw',
                        public_id=f'{safe_name}.{file_ext}',
                        overwrite=True,
                        access_mode='public',
                    )
                source.document_url = result['secure_url']
            else:
                source.document = doc

        elif source_type == ContentSource.SOURCE_TYPE_PROMPT:
            prompt_text = request.POST.get('prompt_text', '').strip()
            if not prompt_text:
                messages.error(request, 'Prompt text is required.')
                return redirect('panel_add_source')
            source.prompt_text = prompt_text

        source.save()
        messages.success(request, f'Source "{name}" created successfully.')
        return redirect('panel_sources')

    ctx = {'threat_choices': INSIDER_THREAT_CHOICES}
    return render(request, 'panel/add_source.html', ctx)


@_require_perm('manage_sources')
def panel_ingest_source(request, pk):
    source = get_object_or_404(ContentSource, pk=pk)
    from .services.ingestion import _FORWARD_HEADERS
    browser_headers = {
        k: v for k, v in request.headers.items()
        if k.lower() in _FORWARD_HEADERS
    }
    raw = ingest_source(source, browser_headers=browser_headers)
    if raw:
        messages.success(request, f'Ingested "{source.name}" successfully. RawContent #{raw.pk} created.')
    else:
        messages.error(request, f'Ingestion failed for "{source.name}". Check logs.')
    return redirect('panel_sources')


@_require_perm('manage_sources')
@require_POST
def panel_delete_source(request, pk):
    source = get_object_or_404(ContentSource, pk=pk)
    name = source.name
    source.delete()
    messages.success(request, f'Source "{name}" and all its raw content deleted.')
    return redirect('panel_sources')


@_require_perm('manage_sources')
@require_POST
def panel_delete_raw(request, pk):
    raw = get_object_or_404(RawContent, pk=pk)
    source_name = raw.source.name
    raw.delete()
    messages.success(request, f'Raw content from "{source_name}" deleted.')
    return redirect('panel_raw_contents')


@_require_perm('manage_sources')
def panel_raw_contents(request):
    raws = RawContent.objects.select_related('source').order_by('-fetched_at')
    paginator = Paginator(raws, 15)
    page_obj = paginator.get_page(request.GET.get('page'))
    ctx = {'page_obj': page_obj}
    return render(request, 'panel/raw_contents.html', ctx)


@_require_perm('manage_sources')
def panel_raw_detail(request, pk):
    raw = get_object_or_404(RawContent, pk=pk)

    if request.method == 'POST':
        raw.summary = request.POST.get('summary', raw.summary)
        raw.engagement_type = request.POST.get('engagement_type', raw.engagement_type)
        raw.save(update_fields=['summary', 'engagement_type'])
        messages.success(request, 'Summary and engagement type updated.')
        return redirect('panel_raw_detail', pk=pk)

    ctx = {'raw': raw, 'engagement_choices': RawContent.ENGAGEMENT_CHOICES}
    return render(request, 'panel/raw_detail.html', ctx)


@_require_perm('manage_sources')
def panel_transform_raw(request, pk):
    raw = get_object_or_404(RawContent, pk=pk)
    content = transform_raw_content(raw, request.user)
    if content:
        messages.success(request, f'Transformed to AwarenessContent #{content.pk}: "{content.title}".')
        return redirect('panel_content_detail', pk=content.pk)
    messages.error(request, 'AI transformation failed. Check that guardian-ai is reachable (python manage.py ai_health).')
    return redirect('panel_raw_contents')


@_require_perm('manage_content')
def panel_content_list(request):
    status_filter = request.GET.get('status', '')
    contents = AwarenessContent.objects.select_related('created_by', 'reviewed_by').order_by('-created_at')
    if status_filter:
        contents = contents.filter(status=status_filter)

    paginator = Paginator(contents, 15)
    page_obj = paginator.get_page(request.GET.get('page'))
    ctx = {
        'page_obj': page_obj,
        'status_filter': status_filter,
        'status_choices': AwarenessContent.STATUS_CHOICES,
    }
    return render(request, 'panel/content_list.html', ctx)


@_require_perm('manage_content')
def panel_content_detail(request, pk):
    content = get_object_or_404(AwarenessContent, pk=pk)

    if request.method == 'POST':
        content.title = request.POST.get('title', content.title).strip()
        content.risk = request.POST.get('risk', content.risk).strip()
        content.action = request.POST.get('action', content.action).strip()
        content.admin_notes = request.POST.get('admin_notes', content.admin_notes).strip()
        content.save(update_fields=['title', 'risk', 'action', 'admin_notes', 'updated_at'])
        messages.success(request, 'Content updated.')
        return redirect('panel_content_detail', pk=pk)

    ctx = {'content': content}
    return render(request, 'panel/content_detail.html', ctx)


@_require_perm('manage_content')
@require_POST
def panel_approve_content(request, pk):
    content = get_object_or_404(AwarenessContent, pk=pk)
    content.status = AwarenessContent.STATUS_APPROVED
    content.reviewed_by = request.user
    content.reviewed_at = timezone.now()
    content.save(update_fields=['status', 'reviewed_by', 'reviewed_at'])
    from phishsim.models import TopicPack
    from phishsim.services import autogen
    if not TopicPack.objects.filter(content=content).exists() and autogen.start(content, request.user):
        messages.success(request, f'"{content.title}" approved. Guardian is preparing the parent and child versions '
                                  f'now (about a minute); review and publish them under Family versions.')
    else:
        messages.success(request, f'"{content.title}" approved.')
    return redirect('panel_content_list')


@_require_perm('manage_content')
@require_POST
def panel_reject_content(request, pk):
    content = get_object_or_404(AwarenessContent, pk=pk)
    content.status = AwarenessContent.STATUS_REJECTED
    content.reviewed_by = request.user
    content.reviewed_at = timezone.now()
    content.admin_notes = request.POST.get('reject_reason', content.admin_notes)
    content.save(update_fields=['status', 'reviewed_by', 'reviewed_at', 'admin_notes'])
    messages.success(request, f'"{content.title}" rejected.')
    return redirect('panel_content_list')


@_require_perm('manage_content')
@require_POST
def panel_delete_content(request, pk):
    content = get_object_or_404(AwarenessContent, pk=pk)
    title = content.title
    content.delete()
    messages.success(request, f'"{title}" deleted.')
    return redirect('panel_content_list')


@_require_perm('manage_content')
def panel_content_engagement(request, pk):
    content = get_object_or_404(AwarenessContent, pk=pk)

    if request.method == 'POST':
        raw_json = request.POST.get('engagement_data', '').strip()
        try:
            parsed = json.loads(raw_json)
            content.engagement_data = parsed
            content.save(update_fields=['engagement_data'])
            messages.success(request, 'Engagement data updated.')
        except json.JSONDecodeError as e:
            messages.error(request, f'Invalid JSON: {e}')
        return redirect('panel_content_engagement', pk=pk)

    import json as _json
    current_json = _json.dumps(content.engagement_data, indent=2) if content.engagement_data else ''
    ctx = {'content': content, 'current_json': current_json}
    return render(request, 'panel/engagement_data.html', ctx)


# ── Campaign views ──

@_require_perm('manage_campaigns')
def panel_campaigns(request):
    campaigns = EmailCampaign.objects.select_related('content', 'created_by').order_by('-created_at')
    paginator = Paginator(campaigns, 15)
    page_obj = paginator.get_page(request.GET.get('page'))
    ctx = {'page_obj': page_obj}
    return render(request, 'panel/campaigns.html', ctx)


@_require_perm('manage_campaigns')
def panel_create_campaign(request, content_pk):
    content = get_object_or_404(AwarenessContent, pk=content_pk, status=AwarenessContent.STATUS_APPROVED)

    if request.method == 'POST':
        subject = request.POST.get('subject', '').strip()
        body_html = request.POST.get('body_html', '').strip()
        if not subject:
            messages.error(request, 'Subject is required.')
            return redirect('panel_create_campaign', content_pk=content_pk)

        # If body not provided, auto-generate from template
        campaign = EmailCampaign.objects.create(
            content=content,
            subject=subject,
            body_html=body_html,
            created_by=request.user,
            status=EmailCampaign.STATUS_DRAFT,
        )
        if not body_html:
            campaign.body_html = build_email_body(campaign)
            campaign.save(update_fields=['body_html'])

        from phishsim.models import TopicPack
        from phishsim.services import autogen
        if not TopicPack.objects.filter(content=content).exists():
            autogen.start(content, request.user)      # the child version is prepared alongside the parents' email
        messages.success(request, f'Campaign "{subject}" created as draft. Review the child version on this page too.')
        return redirect('panel_campaign_detail', pk=campaign.pk)

    # Pre-fill subject
    default_subject = f"[Guardian] Family safety: {content.title}"
    ctx = {'content': content, 'default_subject': default_subject}
    return render(request, 'panel/create_campaign.html', ctx)


@_require_perm('manage_campaigns')
def panel_campaign_detail(request, pk):
    campaign = get_object_or_404(EmailCampaign, pk=pk)
    deliveries = campaign.deliveries.select_related('recipient').order_by('-sent_at')

    if request.method == 'POST':
        campaign.subject = request.POST.get('subject', campaign.subject).strip()
        campaign.body_html = request.POST.get('body_html', campaign.body_html)
        campaign.save(update_fields=['subject', 'body_html'])
        messages.success(request, 'Campaign updated.')
        return redirect('panel_campaign_detail', pk=pk)

    all_staff = (
        Users.objects
        .filter(role=ROLE_PARENT, is_active=True)
        .select_related('profile')
        .order_by('email')
    )
    selected_recipient_ids = set(campaign.target_recipients.values_list('pk', flat=True))

    departments = []   # employee departments no longer exist; targeting is rebuilt in Phase 5

    # Compute effective target count for display
    extra_count = len([e for e in campaign.extra_emails.splitlines() if e.strip()])
    if campaign.target_all_staff:
        target_count = all_staff.count() + extra_count
    else:
        target_count = campaign.target_recipients.filter(is_active=True).count() + extra_count

    from phishsim.models import ChildVersionRequest, TopicPack
    from phishsim.services import autogen
    pack = TopicPack.objects.filter(content=campaign.content).select_related('child_quiz').first()
    ctx = {
        'pack': pack,
        'auto': autogen.status(campaign.content_id),
        'requests': list(ChildVersionRequest.objects.filter(content=campaign.content).select_related('parent')),
        'child_questions': list(pack.child_quiz.questions.all()) if pack and pack.child_quiz else [],
        'campaign': campaign,
        'deliveries': deliveries,
        'all_staff': all_staff,
        'selected_recipient_ids': selected_recipient_ids,
        'departments': departments,
        'extra_emails': campaign.extra_emails,
        'target_count': target_count,
    }
    return render(request, 'panel/campaign_detail.html', ctx)


@_require_perm('manage_campaigns')
@require_POST
def panel_campaign_targets(request, pk):
    campaign = get_object_or_404(EmailCampaign, pk=pk)
    if campaign.status == EmailCampaign.STATUS_SENT:
        messages.error(request, 'Cannot modify targets of a sent campaign.')
        return redirect('panel_campaign_detail', pk=pk)

    target_mode = request.POST.get('target_mode', 'all')

    if target_mode == 'all':
        campaign.target_all_staff = True
        campaign.target_recipients.clear()
    else:
        campaign.target_all_staff = False
        recipient_ids = request.POST.getlist('recipient_ids')
        if recipient_ids:
            recipients = Users.objects.filter(pk__in=recipient_ids, role=ROLE_PARENT, is_active=True)
            campaign.target_recipients.set(recipients)
        else:
            campaign.target_recipients.clear()

    # Merge extra emails from textarea + uploaded file
    extra_text = request.POST.get('extra_emails', '').strip()
    email_file = request.FILES.get('email_file')
    if email_file:
        try:
            file_content = email_file.read().decode('utf-8', errors='ignore')
            file_lines = '\n'.join(l.strip() for l in file_content.splitlines() if l.strip())
            extra_text = f"{extra_text}\n{file_lines}".strip() if extra_text else file_lines
        except Exception as e:
            messages.warning(request, f'Could not parse uploaded file: {e}')

    seen = set()
    valid_extras = []
    for line in extra_text.splitlines():
        addr = line.strip().lower()
        if addr and '@' in addr and addr not in seen:
            seen.add(addr)
            valid_extras.append(addr)

    campaign.extra_emails = '\n'.join(valid_extras)
    campaign.save(update_fields=['target_all_staff', 'extra_emails'])

    if target_mode == 'all':
        messages.success(request, 'Targets set to all active staff.')
    else:
        n_users = campaign.target_recipients.count()
        n_extra = len(valid_extras)
        messages.success(request, f'Targets saved: {n_users} staff selected, {n_extra} extra address(es).')

    return redirect('panel_campaign_detail', pk=pk)


@_require_perm('manage_campaigns')
@require_POST
def panel_send_campaign(request, pk):
    campaign = get_object_or_404(EmailCampaign, pk=pk)
    if campaign.status == EmailCampaign.STATUS_SENT:
        messages.warning(request, 'Campaign already sent.')
        return redirect('panel_campaign_detail', pk=pk)

    # The parents' email goes out together with the child lesson and practice message (plan.md §8.0)
    from phishsim.models import TopicPack
    from phishsim.services import autogen, versions
    pack = TopicPack.objects.filter(content=campaign.content).first()
    if pack is None and not request.POST.get('without_child'):
        if (autogen.status(campaign.content_id) or {}).get('state') != 'running':
            autogen.start(campaign.content, request.user)
        messages.error(request, 'The child version is not ready yet, so nothing was sent. Guardian AI is preparing it; '
                                'review it below, then send. (Or tick "Send without a child version".)')
        return redirect(reverse('panel_campaign_detail', args=[pk]) + '#child-version')
    if pack and not pack.is_published and pack.safety_warnings and not request.POST.get('publish_override'):
        messages.error(request, 'The child version has safety notes. Fix them (or tick that you checked them), then send.')
        return redirect(reverse('panel_campaign_detail', args=[pk]) + '#child-version')

    result = send_campaign(campaign)
    if 'error' in result:
        messages.error(request, result['error'])
        return redirect('panel_campaign_detail', pk=pk)
    messages.success(request, f"Campaign sent: {result['sent']} delivered, {result['failed']} failed.")
    if pack and not pack.is_published:
        sent = versions.publish(pack)
        messages.success(request, 'Child lesson and practice message published with the campaign'
                                  + (f'; {sent} automatic practice email(s) sent to children.' if sent else '.'))
    return redirect('panel_campaign_detail', pk=pk)


# ── Analytics view ──

@_require_perm('view_analytics')
def panel_analytics(request):
    from .models import INSIDER_THREAT_CHOICES

    threat_breakdown = (
        AwarenessContent.objects
        .filter(status=AwarenessContent.STATUS_APPROVED)
        .values('threat_type')
        .annotate(count=Count('id'))
    )
    threat_map = {t: 0 for t, _ in INSIDER_THREAT_CHOICES}
    for row in threat_breakdown:
        threat_map[row['threat_type']] = row['count']

    campaign_stats = EmailCampaign.objects.aggregate(
        total=Count('id'),
        sent=Count('id', filter=Q(status=EmailCampaign.STATUS_SENT)),
    )

    delivery_stats = EmailDelivery.objects.aggregate(
        total=Count('id'),
        sent=Count('id', filter=Q(status=EmailDelivery.STATUS_SENT)),
        opened=Count('id', filter=Q(status=EmailDelivery.STATUS_OPENED)),
        failed=Count('id', filter=Q(status=EmailDelivery.STATUS_FAILED)),
    )

    quiz_stats = QuizAttempt.objects.aggregate(
        total=Count('id'),
        avg_score=Avg('score'),
    )

    top_quizzes = (
        Quiz.objects.annotate(attempt_count=Count('attempts'))
        .order_by('-attempt_count')[:5]
    )

    ctx = {
        'threat_map': threat_map,
        'threat_choices': INSIDER_THREAT_CHOICES,
        'campaign_stats': campaign_stats,
        'delivery_stats': delivery_stats,
        'quiz_stats': quiz_stats,
        'top_quizzes': top_quizzes,
        'total_staff': Users.objects.filter(role=ROLE_CHILD).count(),
        'total_content': AwarenessContent.objects.filter(status=AwarenessContent.STATUS_APPROVED).count(),
    }
    return render(request, 'panel/analytics.html', ctx)


# ──────────────────────────────────────────────
# Analytics drill-down views
# ──────────────────────────────────────────────

def _delivery_email(d):
    """Return the email address for a delivery regardless of recipient type."""
    return d.email or (d.recipient.email if d.recipient else '-')


@_require_perm('view_analytics')
def analytics_staff(request):
    from .models import INSIDER_THREAT_CHOICES
    staff = (
        Users.objects.filter(role=ROLE_CHILD)
        .select_related('profile')
        .annotate(
            emails_received=Count(
                'email_deliveries',
                filter=Q(email_deliveries__status__in=['sent', 'opened', 'clicked']),
                distinct=True,
            ),
            emails_opened=Count(
                'email_deliveries',
                filter=Q(email_deliveries__status__in=['opened', 'clicked']),
                distinct=True,
            ),
            quiz_count=Count('quiz_attempts', distinct=True),
            avg_quiz_score=Avg('quiz_attempts__score'),
            content_viewed=Count(
                'interactions',
                filter=Q(interactions__viewed=True),
                distinct=True,
            ),
        )
        .order_by('email')
    )
    ctx = {
        'staff': staff,
        'active_count': staff.filter(is_active=True).count(),
        'inactive_count': staff.filter(is_active=False).count(),
    }
    return render(request, 'panel/analytics_staff.html', ctx)


@_require_perm('view_analytics')
def analytics_content(request):
    contents = (
        AwarenessContent.objects
        .filter(status=AwarenessContent.STATUS_APPROVED)
        .select_related('source', 'created_by')
        .annotate(
            campaign_count=Count('campaigns', distinct=True),
            delivery_count=Count('campaigns__deliveries', distinct=True),
            opened_count=Count(
                'campaigns__deliveries',
                filter=Q(campaigns__deliveries__status__in=['opened', 'clicked']),
                distinct=True,
            ),
            attempt_count=Count('quiz__attempts', distinct=True),
        )
        .order_by('-created_at')
    )
    ctx = {'contents': contents}
    return render(request, 'panel/analytics_content.html', ctx)


@_require_perm('view_analytics')
def analytics_content_detail(request, pk):
    content = get_object_or_404(AwarenessContent, pk=pk)
    campaigns = content.campaigns.order_by('-created_at')
    deliveries = (
        EmailDelivery.objects
        .filter(campaign__content=content)
        .select_related('recipient', 'recipient__profile', 'campaign')
        .order_by('-sent_at')
    )

    opened = [d for d in deliveries if d.status in ('opened', 'clicked')]
    sent_not_opened = [d for d in deliveries if d.status == 'sent']
    failed = [d for d in deliveries if d.status == 'failed']
    pending = [d for d in deliveries if d.status == 'pending']

    interactions = (
        UserContentInteraction.objects
        .filter(content=content)
        .select_related('user', 'user__profile')
    )

    quiz = getattr(content, 'quiz', None)
    quiz_attempts = (
        quiz.attempts.select_related('user', 'user__profile').order_by('-completed_at')
        if quiz else []
    )

    ctx = {
        'content': content,
        'campaigns': campaigns,
        'deliveries': deliveries,
        'opened': opened,
        'sent_not_opened': sent_not_opened,
        'failed': failed,
        'pending': pending,
        'interactions': interactions,
        'quiz': quiz,
        'quiz_attempts': quiz_attempts,
        'delivery_email': _delivery_email,
    }
    return render(request, 'panel/analytics_content_detail.html', ctx)


@_require_perm('view_analytics')
def analytics_campaigns(request):
    campaigns = (
        EmailCampaign.objects
        .select_related('content', 'created_by')
        .annotate(
            total_deliveries=Count('deliveries', distinct=True),
            opened_count=Count(
                'deliveries',
                filter=Q(deliveries__status__in=['opened', 'clicked']),
                distinct=True,
            ),
            sent_count=Count(
                'deliveries',
                filter=Q(deliveries__status__in=['sent', 'opened', 'clicked']),
                distinct=True,
            ),
            failed_count=Count(
                'deliveries',
                filter=Q(deliveries__status='failed'),
                distinct=True,
            ),
        )
        .order_by('-created_at')
    )
    ctx = {'campaigns': campaigns}
    return render(request, 'panel/analytics_campaigns.html', ctx)


@_require_perm('view_analytics')
def analytics_campaign_detail(request, pk):
    campaign = get_object_or_404(EmailCampaign, pk=pk)
    deliveries = (
        campaign.deliveries
        .select_related('recipient', 'recipient__profile')
        .order_by('-sent_at')
    )
    opened = [d for d in deliveries if d.status in ('opened', 'clicked')]
    delivered_not_opened = [d for d in deliveries if d.status == 'sent']
    failed = [d for d in deliveries if d.status == 'failed']
    ctx = {
        'campaign': campaign,
        'deliveries': deliveries,
        'opened': opened,
        'delivered_not_opened': delivered_not_opened,
        'failed': failed,
    }
    return render(request, 'panel/analytics_campaign_detail.html', ctx)


@_require_perm('view_analytics')
def analytics_emails(request):
    deliveries = (
        EmailDelivery.objects
        .select_related('recipient', 'recipient__profile', 'campaign', 'campaign__content')
        .order_by('-sent_at')
    )
    stats = EmailDelivery.objects.aggregate(
        total=Count('id'),
        delivered=Count('id', filter=Q(status__in=['sent', 'opened', 'clicked'])),
        opened=Count('id', filter=Q(status__in=['opened', 'clicked'])),
        failed=Count('id', filter=Q(status='failed')),
        pending=Count('id', filter=Q(status='pending')),
    )
    total = stats['delivered'] or 1
    stats['open_rate'] = round(stats['opened'] * 100 / total, 1)
    ctx = {
        'deliveries': deliveries,
        'stats': stats,
    }
    return render(request, 'panel/analytics_emails.html', ctx)


@_require_perm('view_analytics')
def analytics_threat(request, threat_type):
    from .models import INSIDER_THREAT_CHOICES
    threat_map = dict(INSIDER_THREAT_CHOICES)
    if threat_type not in threat_map:
        from django.http import Http404
        raise Http404

    sources = ContentSource.objects.filter(threat_type=threat_type).order_by('-created_at')
    content_qs = (
        AwarenessContent.objects
        .filter(threat_type=threat_type, status=AwarenessContent.STATUS_APPROVED)
        .annotate(
            delivery_count=Count('campaigns__deliveries', distinct=True),
            opened_count=Count(
                'campaigns__deliveries',
                filter=Q(campaigns__deliveries__status__in=['opened', 'clicked']),
                distinct=True,
            ),
        )
        .order_by('-created_at')
    )
    campaigns = (
        EmailCampaign.objects
        .filter(content__threat_type=threat_type)
        .select_related('content', 'created_by')
        .annotate(
            delivery_count=Count('deliveries', distinct=True),
            opened_count=Count(
                'deliveries',
                filter=Q(deliveries__status__in=['opened', 'clicked']),
                distinct=True,
            ),
        )
        .order_by('-sent_at')
    )
    deliveries = EmailDelivery.objects.filter(campaign__content__threat_type=threat_type)
    delivery_stats = deliveries.aggregate(
        total=Count('id'),
        delivered=Count('id', filter=Q(status__in=['sent', 'opened', 'clicked'])),
        opened=Count('id', filter=Q(status__in=['opened', 'clicked'])),
        failed=Count('id', filter=Q(status='failed')),
    )
    # Staff reached (by email field)
    reached_emails = list(
        deliveries.filter(status__in=['sent', 'opened', 'clicked'])
        .values_list('email', flat=True)
        .distinct()
    )
    # Staff who interacted (opened)
    interacted_emails = list(
        deliveries.filter(status__in=['opened', 'clicked'])
        .values_list('email', flat=True)
        .distinct()
    )

    ctx = {
        'threat_type': threat_type,
        'threat_label': threat_map[threat_type],
        'sources': sources,
        'content_qs': content_qs,
        'campaigns': campaigns,
        'delivery_stats': delivery_stats,
        'reached_emails': reached_emails,
        'interacted_emails': interacted_emails,
    }
    return render(request, 'panel/analytics_threat.html', ctx)


@_require_perm('view_analytics')
def analytics_quizzes(request):
    quizzes = (
        Quiz.objects
        .select_related('content', 'content__source')
        .annotate(
            attempt_count=Count('attempts', distinct=True),
            avg_score=Avg('attempts__score'),
            avg_total=Avg('attempts__total'),
        )
        .order_by('-attempt_count')
    )

    # Load all attempts sorted by (user, quiz, completed_at) for progression math
    all_attempts_ordered = list(
        QuizAttempt.objects
        .select_related('user', 'user__profile', 'quiz', 'quiz__content')
        .order_by('user_id', 'quiz_id', 'completed_at')
    )

    # Group per (user, quiz) → attempt number + delta
    attempt_meta = {}  # pk → {'number': int, 'delta': int|None}
    retake_progressions = []
    by_user_quiz = {}
    for a in all_attempts_ordered:
        key = (a.user_id, a.quiz_id)
        if key not in by_user_quiz:
            by_user_quiz[key] = []
        by_user_quiz[key].append(a)

    for group in by_user_quiz.values():
        for idx, a in enumerate(group):
            prev = group[idx - 1] if idx > 0 else None
            delta = a.percentage - prev.percentage if prev else None
            attempt_meta[a.pk] = {'number': idx + 1, 'delta': delta}
        if len(group) >= 2:
            first, latest = group[0], group[-1]
            profile = getattr(first.user, 'profile', None)
            retake_progressions.append({
                'user_name': profile.full_name if profile and profile.full_name else '',
                'user_email': first.user.email,
                'quiz_title': first.quiz.title,
                'attempt_count': len(group),
                'first_pct': first.percentage,
                'latest_pct': latest.percentage,
                'delta': latest.percentage - first.percentage,
            })
    retake_progressions.sort(key=lambda x: x['delta'], reverse=True)

    # Display list ordered by -completed_at, with attempt_number/attempt_delta attached
    attempts = sorted(all_attempts_ordered, key=lambda a: a.completed_at, reverse=True)
    for a in attempts:
        meta = attempt_meta.get(a.pk, {})
        a.attempt_number = meta.get('number', 1)
        a.attempt_delta = meta.get('delta')

    # Per-staff summary: first / latest / avg across all quizzes attempted
    staff_map = {}
    for a in all_attempts_ordered:
        uid = a.user_id
        if uid not in staff_map:
            profile = getattr(a.user, 'profile', None)
            staff_map[uid] = {
                'email': a.user.email,
                'name': profile.full_name if profile and profile.full_name else '',
                'quiz_groups': {},
            }
        qid = a.quiz_id
        if qid not in staff_map[uid]['quiz_groups']:
            staff_map[uid]['quiz_groups'][qid] = []
        staff_map[uid]['quiz_groups'][qid].append(a)

    staff_stats = []
    for data in staff_map.values():
        groups = list(data['quiz_groups'].values())
        total_attempts = sum(len(g) for g in groups)
        first_pcts = [g[0].percentage for g in groups]
        latest_pcts = [g[-1].percentage for g in groups]
        avg_first = round(sum(first_pcts) / len(first_pcts), 1) if first_pcts else 0
        avg_latest = round(sum(latest_pcts) / len(latest_pcts), 1) if latest_pcts else 0
        staff_stats.append({
            'email': data['email'],
            'name': data['name'],
            'total_attempts': total_attempts,
            'quiz_count': len(groups),
            'avg_first_pct': avg_first,
            'avg_latest_pct': avg_latest,
            'avg_delta': round(avg_latest - avg_first, 1),
        })
    staff_stats.sort(key=lambda x: x['total_attempts'], reverse=True)

    ctx = {
        'quizzes': quizzes,
        'attempts': attempts,
        'staff_stats': staff_stats,
        'retake_progressions': retake_progressions,
        'total_attempts': len(attempts),
        'retake_count': len(retake_progressions),
    }
    return render(request, 'panel/analytics_quizzes.html', ctx)


@_require_perm('view_analytics')
def analytics_report(request):
    from .models import INSIDER_THREAT_CHOICES

    # Staff
    staff = (
        Users.objects.filter(role=ROLE_CHILD)
        .select_related('profile')
        .annotate(
            emails_received=Count('email_deliveries', filter=Q(email_deliveries__status__in=['sent','opened','clicked']), distinct=True),
            emails_opened=Count('email_deliveries', filter=Q(email_deliveries__status__in=['opened','clicked']), distinct=True),
            quiz_count=Count('quiz_attempts', distinct=True),
            avg_quiz_score=Avg('quiz_attempts__score'),
        )
        .order_by('email')
    )

    # Content
    contents = (
        AwarenessContent.objects
        .filter(status=AwarenessContent.STATUS_APPROVED)
        .select_related('source')
        .annotate(
            delivery_count=Count('campaigns__deliveries', distinct=True),
            opened_count=Count('campaigns__deliveries', filter=Q(campaigns__deliveries__status__in=['opened','clicked']), distinct=True),
            attempt_count=Count('quiz__attempts', distinct=True),
        )
        .order_by('threat_type', '-created_at')
    )

    # Campaigns
    campaigns = (
        EmailCampaign.objects
        .filter(status=EmailCampaign.STATUS_SENT)
        .select_related('content', 'created_by')
        .annotate(
            total_deliveries=Count('deliveries', distinct=True),
            opened_count=Count('deliveries', filter=Q(deliveries__status__in=['opened','clicked']), distinct=True),
            failed_count=Count('deliveries', filter=Q(deliveries__status='failed'), distinct=True),
        )
        .order_by('-sent_at')
    )

    # Delivery stats
    delivery_stats = EmailDelivery.objects.aggregate(
        total=Count('id'),
        delivered=Count('id', filter=Q(status__in=['sent','opened','clicked'])),
        opened=Count('id', filter=Q(status__in=['opened','clicked'])),
        failed=Count('id', filter=Q(status='failed')),
    )
    delivered = delivery_stats['delivered'] or 1
    delivery_stats['open_rate'] = round(delivery_stats['opened'] * 100 / delivered, 1)

    # Threat breakdown
    threat_breakdown = (
        AwarenessContent.objects
        .filter(status=AwarenessContent.STATUS_APPROVED)
        .values('threat_type')
        .annotate(count=Count('id'))
    )
    threat_map = {t: 0 for t, _ in INSIDER_THREAT_CHOICES}
    for row in threat_breakdown:
        threat_map[row['threat_type']] = row['count']

    # Quiz stats
    quiz_stats = QuizAttempt.objects.aggregate(
        total=Count('id'),
        avg_score=Avg('score'),
    )
    quizzes = (
        Quiz.objects.select_related('content')
        .annotate(attempt_count=Count('attempts'), avg_score=Avg('attempts__score'))
        .order_by('-attempt_count')
    )
    quiz_attempts = (
        QuizAttempt.objects
        .select_related('user', 'user__profile', 'quiz', 'quiz__content')
        .order_by('-completed_at')
    )

    ctx = {
        'report_date': timezone.now(),
        'staff': staff,
        'active_staff': staff.filter(is_active=True).count(),
        'contents': contents,
        'campaigns': campaigns,
        'delivery_stats': delivery_stats,
        'threat_map': threat_map,
        'threat_choices': INSIDER_THREAT_CHOICES,
        'quiz_stats': quiz_stats,
        'quizzes': quizzes,
        'quiz_attempts': quiz_attempts,
    }
    return render(request, 'panel/analytics_report.html', ctx)
