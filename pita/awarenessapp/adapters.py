from allauth.socialaccount.adapter import DefaultSocialAccountAdapter
from allauth.core.exceptions import ImmediateHttpResponse
from .models import ROLE_PARENT


class SocialAccountAdapter(DefaultSocialAccountAdapter):

    def pre_social_login(self, request, sociallogin):
        """
        Link a Google sign-in to an existing manual account if the email matches,
        so users can use either method to sign in.
        Also refresh picture_url on every Google login.
        """
        if sociallogin.is_existing:
            # Existing linked account, update the picture URL in case it changed
            self._sync_google_profile(sociallogin.user, sociallogin.account.extra_data)
            return

        email = (sociallogin.account.extra_data.get('email') or '').strip().lower()
        if not email:
            return

        from .models import Users
        try:
            existing_user = Users.objects.get(email__iexact=email)
            sociallogin.connect(request, existing_user)
            self._sync_google_profile(existing_user, sociallogin.account.extra_data)
        except Users.DoesNotExist:
            pass

    def save_user(self, request, sociallogin, form=None):
        user = super().save_user(request, sociallogin, form)
        if not user.role:
            user.role = ROLE_PARENT   # Google sign-in is for parents; children never need an email account
            user.save(update_fields=['role'])
        self._sync_google_profile(user, sociallogin.account.extra_data)
        return user

    def _sync_google_profile(self, user, extra_data):
        """Populate full_name and picture_url from Google's extra_data."""
        try:
            from .models import Profile
            profile, _ = Profile.objects.get_or_create(user=user)
            update_fields = []

            if not profile.full_name:
                name = extra_data.get('name') or (
                    f"{extra_data.get('given_name', '')} {extra_data.get('family_name', '')}".strip()
                )
                if name:
                    profile.full_name = name
                    update_fields.append('full_name')

            picture = extra_data.get('picture', '')
            if picture and profile.picture_url != picture:
                profile.picture_url = picture
                update_fields.append('picture_url')

            if update_fields:
                profile.save(update_fields=update_fields)
        except Exception:
            pass
