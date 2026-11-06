import re
from unittest import mock

from django.core import mail
from django.core.cache import cache
from django.test import RequestFactory, TestCase, override_settings
from django.urls import reverse

from .adapters import SocialAccountAdapter
from .models import AwarenessContent, ROLE_ANALYST, ROLE_PARENT, Users

PASSWORD = 'Str0ng-pass-123'
NEW = 'An0ther-good-pass-77'


def google_only_parent(email='g@x.ug'):
    from allauth.socialaccount.models import SocialAccount
    user = Users.objects.create_user(email=email, password=None, role=ROLE_PARENT)
    user.set_unusable_password()
    user.save()
    SocialAccount.objects.create(user=user, provider='google', uid='123', extra_data={'email': email})
    return user


@override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend', SITE_URL='http://testserver')
class PasswordAndSignInTests(TestCase):
    def setUp(self):
        cache.clear()

    def test_google_only_parent_adds_a_password_and_stays_signed_in(self):
        user = google_only_parent()
        self.client.force_login(user)
        page = self.client.get(reverse('account_security'))
        self.assertContains(page, 'Add a password')
        self.assertContains(page, 'Connected as g@x.ug')
        r = self.client.post(reverse('account_security'), {'action': 'password', 'new_password1': NEW, 'new_password2': NEW})
        self.assertRedirects(r, reverse('account_security'))
        user.refresh_from_db()
        self.assertTrue(user.check_password(NEW))
        self.assertContains(self.client.get(reverse('account_security')), 'Change password')   # still signed in
        self.assertEqual(mail.outbox[-1].subject, 'Your Guardian password was added')
        self.client.logout()
        self.assertEqual(self.client.post(reverse('login_user'), {'email': 'g@x.ug', 'password': NEW}).status_code, 200)

    def test_changing_a_password_needs_the_current_one(self):
        user = Users.objects.create_user(email='p@x.ug', password=PASSWORD, role=ROLE_PARENT)
        self.client.force_login(user)
        r = self.client.post(reverse('account_security'), {'action': 'password', 'old_password': 'wrong',
                                                           'new_password1': NEW, 'new_password2': NEW})
        self.assertEqual(r.status_code, 200)
        user.refresh_from_db()
        self.assertTrue(user.check_password(PASSWORD))
        self.client.post(reverse('account_security'), {'action': 'password', 'old_password': PASSWORD,
                                                       'new_password1': NEW, 'new_password2': NEW})
        user.refresh_from_db()
        self.assertTrue(user.check_password(NEW))
        self.assertEqual(mail.outbox[-1].subject, 'Your Guardian password was changed')

    def test_google_cannot_be_disconnected_without_a_password(self):
        from allauth.socialaccount.models import SocialAccount
        user = google_only_parent()
        self.client.force_login(user)
        self.client.post(reverse('account_security'), {'action': 'disconnect_google'})
        self.assertTrue(SocialAccount.objects.filter(user=user).exists())
        user.set_password(PASSWORD)
        user.save()
        self.client.force_login(user)
        self.client.post(reverse('account_security'), {'action': 'disconnect_google'})
        self.assertFalse(SocialAccount.objects.filter(user=user).exists())

    def test_reset_by_email_also_works_for_google_only_accounts(self):
        google_only_parent()
        r = self.client.post(reverse('password_reset'), {'email': 'G@x.ug'})
        self.assertRedirects(r, reverse('password_reset_done'))
        self.assertEqual(len(mail.outbox), 1)
        link = re.search(r'http://testserver(/\S+?/password/reset/[^/]+/[^/]+/)', mail.outbox[0].body).group(1)
        r = self.client.get(link, follow=True)                 # Django swaps the token for a session URL
        r = self.client.post(r.redirect_chain[-1][0], {'new_password1': NEW, 'new_password2': NEW})
        self.assertRedirects(r, reverse('password_reset_complete'))
        self.assertTrue(Users.objects.get(email='g@x.ug').check_password(NEW))

    def test_reset_does_not_reveal_unknown_addresses(self):
        r = self.client.post(reverse('password_reset'), {'email': 'nobody@x.ug'})
        self.assertRedirects(r, reverse('password_reset_done'))
        self.assertEqual(len(mail.outbox), 0)

    def test_practice_link_sessions_cannot_change_sign_in(self):
        user = Users.objects.create_user(email='kid@x.ug', password=PASSWORD, role='child')
        self.client.force_login(user)
        s = self.client.session
        s['via_practice_link'] = 1
        s.save()
        self.assertContains(self.client.get(reverse('account_security')), 'practice link')


class GoogleLinkingTests(TestCase):
    def _login(self, email, verified=True):
        return mock.Mock(is_existing=False, state={}, account=mock.Mock(extra_data={'email': email, 'email_verified': verified}))

    def test_google_joins_the_existing_account_with_the_same_email(self):
        user = Users.objects.create_user(email='Mum@x.ug', password=PASSWORD, role=ROLE_PARENT)
        social = self._login('mum@x.ug')
        SocialAccountAdapter().pre_social_login(RequestFactory().get('/'), social)
        social.connect.assert_called_once()
        self.assertEqual(social.connect.call_args[0][1], user)
        self.assertEqual(Users.objects.filter(email__iexact='mum@x.ug').count(), 1)

    def test_unverified_google_email_is_not_joined(self):
        Users.objects.create_user(email='mum@x.ug', password=PASSWORD, role=ROLE_PARENT)
        social = self._login('mum@x.ug', verified=False)
        SocialAccountAdapter().pre_social_login(RequestFactory().get('/'), social)
        social.connect.assert_not_called()


class ApproveStartsFamilyVersionsTests(TestCase):
    def test_approving_a_topic_starts_preparing_family_versions(self):
        analyst = Users.objects.create_user(email='a@x.ug', password=PASSWORD, role=ROLE_ANALYST)
        content = AwarenessContent.objects.create(created_by=analyst, threat_type='reward', title='T', risk='r', action='a')
        self.client.force_login(analyst)
        with mock.patch('phishsim.services.autogen.start', return_value=True) as start:
            self.client.post(reverse('panel_approve_content', args=[content.pk]))
        start.assert_called_once()
        content.refresh_from_db()
        self.assertEqual(content.status, AwarenessContent.STATUS_APPROVED)


class FamiliesAnalyticsTests(TestCase):
    def test_families_page_and_report_show_children_by_pseudonym_only(self):
        from safety.models import ChildProfile, GuardianChildLink
        analyst = Users.objects.create_user(email='a@x.ug', password=PASSWORD, role=ROLE_ANALYST)
        parent = Users.objects.create_user(email='mum@x.ug', password=PASSWORD, role=ROLE_PARENT)
        kid_user = Users.objects.create_user(email='tutu.kid@x.ug', password=PASSWORD, role='child')
        child = ChildProfile.objects.create(nickname='Tutu', age_band='11-13', created_by=parent,
                                            email='tutu.kid@x.ug', user=kid_user, district='Wakiso')
        GuardianChildLink.objects.create(guardian=parent, child=child)
        self.client.force_login(analyst)
        for name in ('analytics_staff', 'analytics_report'):
            r = self.client.get(reverse(name))
            self.assertEqual(r.status_code, 200, name)
            self.assertContains(r, child.pseudonym)
            self.assertContains(r, 'mum@x.ug')                       # parents receive the regulators' emails
            self.assertNotContains(r, 'tutu.kid@x.ug')               # never a child's email
            self.assertNotContains(r, '>Tutu<')                      # never a child's nickname
            self.assertNotContains(r, 'Department')
            self.assertContains(r, 'fewer than 5')                   # small groups suppressed
