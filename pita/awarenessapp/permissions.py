"""Role checks for views (plan.md §1, §5.2). Enforced on the server, never only hidden in templates."""
from functools import wraps

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect
from django.urls import NoReverseMatch, reverse

from .models import ROLE_ANALYST, ROLE_CHILD, ROLE_PARENT

# First URL name that exists wins, so a role's home can move as its portal is built.
_ROLE_HOMES = {
    ROLE_CHILD: ['child_home'],
    ROLE_PARENT: ['parent_home'],
    ROLE_ANALYST: ['panel_dashboard'],
}


def role_home_url(user) -> str:
    for name in _ROLE_HOMES.get(getattr(user, 'role', None), []):
        try:
            return reverse(name)
        except NoReverseMatch:
            continue
    return reverse('home')


def role_required(*roles):
    """Allow only logged-in users whose role is in `roles`; others go to their own home."""
    def decorator(view):
        @login_required(login_url='login_user')
        @wraps(view)
        def wrapper(request, *args, **kwargs):
            if request.user.role not in roles:
                messages.error(request, 'That page is not available for your account.')
                return redirect(role_home_url(request.user))
            return view(request, *args, **kwargs)
        return wrapper
    return decorator


child_required = role_required(ROLE_CHILD)
parent_required = role_required(ROLE_PARENT)
analyst_required = role_required(ROLE_ANALYST)
