from unittest import mock

from django.core import mail
from django.test import TestCase, override_settings

from awarenessapp.models import ROLE_PARENT, Users
from safety.models import ChildProfile, ConsentRecord, GuardianChildLink, GuardianPreference, ParentAlert, Submission
from safety.services import alert_email
from safety.services.analysis import alert_parents

PASSWORD = 'Str0ng-pass-123'


@override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend', SITE_URL='http://testserver')
@mock.patch.object(alert_email, 'SEND_IN_BACKGROUND', False)
class AlertEmailTests(TestCase):
    def setUp(self):
        self.parent = Users.objects.create_user(email='mum@x.ug', password=PASSWORD, role=ROLE_PARENT)
        self.child = ChildProfile.objects.create(nickname='Tutu', age_band='11-13', created_by=self.parent)
        GuardianChildLink.objects.create(guardian=self.parent, child=self.child)
        ConsentRecord.grant(self.parent, self.child, ConsentRecord.KIND_ALERTS)

    def high_risk(self):
        return Submission.objects.create(child=self.child, submitter_role='child', input_kind='text',
                                         sanitised_text='Send your PIN to win 500,000 now', risk_level='high', category='otp_theft')

    def test_email_sent_when_parent_turned_it_on_and_it_never_contains_the_message(self):
        prefs = GuardianPreference.for_parent(self.parent)
        prefs.alert_email = True
        prefs.save()
        with self.captureOnCommitCallbacks(execute=True):
            self.assertEqual(alert_parents(self.child, self.high_risk()), 1)
        self.assertEqual(len(mail.outbox), 1)
        msg = mail.outbox[0]
        self.assertEqual(msg.to, ['mum@x.ug'])
        self.assertIn('Tutu', msg.subject)
        self.assertIn('PIN', msg.body)                       # the safety action names PINs
        self.assertNotIn('500,000', msg.body)                # but never the child's message
        self.assertIn('/family/alerts/', msg.body)

    def test_no_email_when_the_setting_is_off(self):
        with self.captureOnCommitCallbacks(execute=True):
            alert_parents(self.child, self.high_risk())
        self.assertEqual(ParentAlert.objects.count(), 1)
        self.assertEqual(len(mail.outbox), 0)
