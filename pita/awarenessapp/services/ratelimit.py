"""Fixed-window rate limiting on the Django cache (moved out of services/transformation.py)."""
from functools import wraps

from django.core.cache import cache
from django.http import JsonResponse
from django.shortcuts import render


class RateLimitError(Exception):
    """Raised when a fixed-window counter is over its limit."""


def hit(key: str, limit: int, window: int, label: str = '') -> None:
    """Increment a fixed-window counter; raise RateLimitError if over limit. Fails open if the cache is down."""
    if cache.add(key, 1, timeout=window):
        return  # first call in this window, always allowed
    try:
        count = cache.incr(key)
    except Exception:
        return
    if count > limit:
        raise RateLimitError(f"Rate limit exceeded ({label or key}): {limit} calls per {window}s")


def client_key(request) -> str:
    if request.user.is_authenticated:
        return f'u{request.user.pk}'
    forwarded = request.META.get('HTTP_X_FORWARDED_FOR', '')
    return 'ip' + (forwarded.split(',')[0].strip() or request.META.get('REMOTE_ADDR', ''))


def rate_limit(scope: str, limit: int, window: int, methods=('POST',)):
    """View decorator: at most `limit` requests per `window` seconds per user (or IP) for `scope`."""
    def decorator(view):
        @wraps(view)
        def wrapper(request, *args, **kwargs):
            if request.method in methods:
                try:
                    hit(f'rl:{scope}:{client_key(request)}', limit, window, scope)
                except RateLimitError:
                    message = 'Too many attempts. Please wait a while and try again.'
                    if request.headers.get('Accept', '').startswith('application/json'):
                        return JsonResponse({'error': message}, status=429)
                    return render(request, 'rate_limited.html', {'message': message}, status=429)
            return view(request, *args, **kwargs)
        return wrapper
    return decorator
