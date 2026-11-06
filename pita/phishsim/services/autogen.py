"""Prepare family versions automatically when an analyst approves a topic (plan.md §8.0 item 1).

Generation takes about half a minute on the Testbed GPU, so it runs in a background thread. The result is a draft:
an analyst still reviews the safety notes and publishes it, so parents never receive unreviewed AI text.
"""
import logging
import threading

from django.core.cache import cache
from django.db import close_old_connections

logger = logging.getLogger(__name__)
_TTL = 30 * 60


def _key(content_pk):
    return f'pack-gen:{content_pk}'


def status(content_pk) -> dict | None:
    """{'state': 'running'|'failed', 'error': str} while or after a background run, else None."""
    return cache.get(_key(content_pk))


def start(content, user=None) -> bool:
    """Start preparing family versions for `content` unless a run is already going. Returns True if started."""
    if not cache.add(_key(content.pk), {'state': 'running', 'error': ''}, _TTL):
        current = cache.get(_key(content.pk)) or {}
        if current.get('state') == 'running':
            return False
        cache.set(_key(content.pk), {'state': 'running', 'error': ''}, _TTL)
    content_pk, user_pk = content.pk, getattr(user, 'pk', None)

    def work():
        from awarenessapp.models import AwarenessContent, Users
        from .generate import generate_pack
        close_old_connections()
        try:
            obj = AwarenessContent.objects.get(pk=content_pk)
            generate_pack(obj, user=Users.objects.filter(pk=user_pk).first())
            cache.delete(_key(content_pk))
        except ValueError as e:
            cache.set(_key(content_pk), {'state': 'failed', 'error': str(e)}, _TTL)
        except Exception as e:
            logger.exception('Automatic family versions failed for topic #%s', content_pk)
            cache.set(_key(content_pk), {'state': 'failed', 'error': f'{type(e).__name__}: {e}'}, _TTL)
        finally:
            close_old_connections()

    threading.Thread(target=work, daemon=True, name=f'pack-gen-{content_pk}').start()
    return True
