from django import forms
from django.conf import settings
from django.contrib.auth.password_validation import validate_password

from awarenessapp.models import Users

from .models import AGE_BANDS, ChildProfile

_INPUT = 'w-full px-3 py-2 border border-on-surface focus:outline-none focus:border-2 focus:border-teal text-sm bg-white'


class _Styled:
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            if not isinstance(field.widget, (forms.CheckboxInput, forms.RadioSelect)):
                field.widget.attrs.setdefault('class', _INPUT)


class ChildForm(_Styled, forms.ModelForm):
    """Parent adds or edits a child: nickname, age band, district and (optionally) the child's email."""

    class Meta:
        model = ChildProfile
        fields = ['nickname', 'age_band', 'district', 'email', 'phone', 'whatsapp']
        labels = {'nickname': 'Nickname', 'age_band': 'Age band', 'district': 'District (optional)',
                  'email': "Child's email (optional)", 'phone': "Child's phone for SMS (optional, coming soon)",
                  'whatsapp': "Child's WhatsApp number (optional, coming soon)"}
        help_texts = {
            'nickname': 'A first name or nickname only. Please do not enter a full legal name.',
            'email': 'Needed for practice emails and lessons. Your child does not need to install anything.',
            'phone': 'Practice text messages will use this when SMS is switched on.',
            'whatsapp': 'Practice WhatsApp messages will use this when WhatsApp is switched on.',
        }
        widgets = {'age_band': forms.RadioSelect(choices=AGE_BANDS)}

    def __init__(self, *args, parent=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.parent = parent

    def clean_email(self):
        email = (self.cleaned_data.get('email') or '').strip().lower()
        if not email:
            return ''
        if self.parent and email == self.parent.email.lower():
            raise forms.ValidationError("Use your child's own email address, not yours.")
        others = ChildProfile.objects.filter(created_by=self.parent).exclude(email='')
        if self.instance.pk:
            others = others.exclude(pk=self.instance.pk)
        if others.filter(email__iexact=email).exists():
            raise forms.ValidationError('You have already added this email for another child.')
        limit = settings.GUARDIAN_MAX_CHILD_EMAILS_PER_PARENT
        if others.count() >= limit:
            raise forms.ValidationError(f'You can add up to {limit} child email addresses.')
        return email


class PairForm(_Styled, forms.Form):
    """Child's device: redeem the family code and create a child account."""
    code = forms.CharField(max_length=20, label='Family code',
                           widget=forms.TextInput(attrs={'placeholder': 'SAFE-123456', 'autocomplete': 'off',
                                                         'autocapitalize': 'characters'}))
    email = forms.EmailField(label='Your email')
    password1 = forms.CharField(label='Choose a password', widget=forms.PasswordInput)
    password2 = forms.CharField(label='Type the password again', widget=forms.PasswordInput)

    def clean_email(self):
        email = self.cleaned_data['email'].strip().lower()
        if Users.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError('That email already has a Guardian account. Ask your parent for help.')
        return email

    def clean(self):
        data = super().clean()
        if data.get('password1') and data.get('password1') != data.get('password2'):
            self.add_error('password2', 'The passwords do not match.')
        elif data.get('password1'):
            try:
                validate_password(data['password1'])
            except forms.ValidationError as e:
                self.add_error('password1', e)
        return data
