from datetime import timedelta

from django.core.cache import cache
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from awarenessapp.models import ROLE_ANALYST, ROLE_CHILD, ROLE_PARENT, Users
from safety.models import ChildProfile, ConsentRecord, GuardianChildLink, PairingCode

PASSWORD = 'Str0ng-pass-123'


def make_user(email, role):
    return Users.objects.create_user(email=email, password=PASSWORD, role=role)


class RoleTests(TestCase):
    def test_signup_creates_parent_and_redirects_home(self):
        r = self.client.post(reverse('register_user'),
                             {'email': 'p@x.ug', 'password1': PASSWORD, 'password2': PASSWORD})
        self.assertEqual(r.status_code, 201)
        self.assertEqual(Users.objects.get(email='p@x.ug').role, ROLE_PARENT)
        self.assertEqual(r.json()['next'], reverse('parent_home'))

    def test_superuser_is_analyst(self):
        u = Users.objects.create_superuser('ops@x.ug', PASSWORD)
        self.assertEqual(u.role, ROLE_ANALYST)
        self.assertTrue(u.is_superuser and u.is_staff)

    def test_analyst_is_staff_but_not_superuser(self):
        u = make_user('a@x.ug', ROLE_ANALYST)
        self.assertTrue(u.is_staff)
        self.assertFalse(u.is_superuser)
        self.assertTrue(u.groups.filter(name='Analysts').exists())

    def test_login_redirects_each_role_home(self):
        for email, role, home in (('c@x.ug', ROLE_CHILD, 'child_home'), ('p@x.ug', ROLE_PARENT, 'parent_home'),
                                  ('a@x.ug', ROLE_ANALYST, 'panel_dashboard')):
            make_user(email, role)
            r = self.client.post(reverse('login_user'), {'email': email, 'password': PASSWORD})
            self.assertEqual(r.json()['next'], reverse(home), role)
            self.client.logout()

    def test_roles_cannot_open_each_others_pages(self):
        make_user('c@x.ug', ROLE_CHILD)
        self.client.login(email='c@x.ug', password=PASSWORD)
        self.assertRedirects(self.client.get(reverse('parent_home')), reverse('child_home'),
                             fetch_redirect_response=False)
        self.client.logout()
        make_user('p@x.ug', ROLE_PARENT)
        self.client.login(email='p@x.ug', password=PASSWORD)
        self.assertRedirects(self.client.get(reverse('child_family')), reverse('parent_home'),
                             fetch_redirect_response=False)
        self.assertEqual(self.client.get(reverse('panel_dashboard')).status_code, 302)


class FamilyTests(TestCase):
    def setUp(self):
        cache.clear()
        self.parent = make_user('parent@x.ug', ROLE_PARENT)
        self.client.login(email='parent@x.ug', password=PASSWORD)

    def add_child(self, **extra):
        data = {'nickname': 'Kato', 'age_band': '11-13', 'district': 'Wakiso', 'email': 'kato@x.ug', **extra}
        return self.client.post(reverse('child_add'), data)

    def test_add_child_by_email_without_app(self):
        self.assertRedirects(self.add_child(alerts='1', practice='1', told_child='1'), reverse('parent_home'))
        child = ChildProfile.objects.get()
        self.assertFalse(child.is_paired)
        self.assertTrue(child.pseudonym.startswith('C-'))
        self.assertTrue(GuardianChildLink.objects.filter(guardian=self.parent, child=child, active=True).exists())
        self.assertTrue(ConsentRecord.active(child, ConsentRecord.KIND_SIMULATION).told_child)
        self.assertIsNotNone(ConsentRecord.active(child, ConsentRecord.KIND_ALERTS))

    def test_practice_needs_told_child(self):
        self.add_child(practice='1')
        self.assertIsNone(ConsentRecord.active(ChildProfile.objects.get(), ConsentRecord.KIND_SIMULATION))

    def test_parent_email_cannot_be_child_email(self):
        r = self.add_child(email='parent@x.ug')
        self.assertContains(r, "Use your child")
        self.assertFalse(ChildProfile.objects.exists())

    @override_settings(GUARDIAN_MAX_CHILD_EMAILS_PER_PARENT=2)
    def test_child_email_cap(self):
        self.add_child(email='a@x.ug')
        self.add_child(nickname='B', email='b@x.ug')
        r = self.add_child(nickname='C', email='c@x.ug')
        self.assertContains(r, 'up to 2 child email')
        self.assertEqual(ChildProfile.objects.count(), 2)

    def test_consent_toggle_and_revoke(self):
        self.add_child()
        child = ChildProfile.objects.get()
        url = reverse('child_consent', args=[child.pk])
        self.client.post(url, {'kind': 'phishing_simulation', 'enable': '1'})
        self.assertIsNone(ConsentRecord.active(child, ConsentRecord.KIND_SIMULATION))   # told_child missing
        self.client.post(url, {'kind': 'phishing_simulation', 'enable': '1', 'told_child': '1'})
        self.assertIsNotNone(ConsentRecord.active(child, ConsentRecord.KIND_SIMULATION))
        self.client.post(url, {'kind': 'phishing_simulation', 'enable': '0'})
        self.assertIsNone(ConsentRecord.active(child, ConsentRecord.KIND_SIMULATION))

    def test_other_parents_children_are_invisible(self):
        self.add_child()
        child = ChildProfile.objects.get()
        make_user('other@x.ug', ROLE_PARENT)
        self.client.logout()
        self.client.login(email='other@x.ug', password=PASSWORD)
        self.assertEqual(self.client.get(reverse('child_edit', args=[child.pk])).status_code, 404)
        self.assertEqual(self.client.post(reverse('pairing_code', args=[child.pk])).status_code, 404)
        self.assertNotContains(self.client.get(reverse('parent_home')), 'Kato')


class PairingTests(TestCase):
    def setUp(self):
        cache.clear()
        self.parent = make_user('parent@x.ug', ROLE_PARENT)
        self.child = ChildProfile.objects.create(nickname='Amina', age_band='8-10', created_by=self.parent)
        GuardianChildLink.objects.create(guardian=self.parent, child=self.child)

    def issue(self):
        self.client.login(email='parent@x.ug', password=PASSWORD)
        r = self.client.post(reverse('pairing_code', args=[self.child.pk]))
        self.client.logout()
        return r.context['code']

    def pair(self, code, email='amina@x.ug'):
        return self.client.post(reverse('pair'), {'code': code, 'email': email,
                                                  'password1': PASSWORD, 'password2': PASSWORD})

    def test_code_is_stored_hashed(self):
        code = self.issue()
        self.assertFalse(PairingCode.objects.filter(code_hash=code).exists())
        self.assertTrue(PairingCode.objects.filter(code_hash=PairingCode.hash(code)).exists())

    def test_pairing_creates_child_account_and_shows_visibility(self):
        code = self.issue()
        r = self.pair(code.split('-')[1])     # the 6 digits alone are enough
        self.assertRedirects(r, reverse('child_family'))
        self.child.refresh_from_db()
        self.assertEqual(self.child.user.role, ROLE_CHILD)
        self.assertEqual(self.child.email, 'amina@x.ug')
        self.assertContains(self.client.get(reverse('child_family')), 'Your parent cannot see')

    def test_code_works_once(self):
        code = self.issue()
        self.pair(code)
        self.client.logout()
        r = self.pair(code, email='second@x.ug')
        self.assertContains(r, 'not valid or has expired')
        self.assertFalse(Users.objects.filter(email='second@x.ug').exists())

    def test_expired_code_rejected(self):
        code = self.issue()
        PairingCode.objects.update(expires_at=timezone.now() - timedelta(seconds=1))
        self.assertContains(self.pair(code), 'not valid or has expired')

    def test_new_code_invalidates_old(self):
        old = self.issue()
        self.issue()
        self.assertContains(self.pair(old), 'not valid or has expired')

    def test_pairing_is_rate_limited(self):
        for _ in range(10):
            self.pair('SAFE-000000')
        self.assertEqual(self.pair('SAFE-000000').status_code, 429)
