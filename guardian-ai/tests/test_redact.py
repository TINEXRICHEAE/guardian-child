import pytest

from guardian_ai.redact import redact


@pytest.mark.parametrize('text, expected', [
    ('Send your Mobile Money PIN to claim.', 'Send your Mobile Money PIN to claim.'),
    ('Your PIN is 4821', 'Your PIN is [SECRET]'),
    ('OTP: 829104 expires soon', 'OTP: [SECRET] expires soon'),
    ('password = hunter22', 'password = [SECRET]'),
    ('Click the password reset link', 'Click the password reset link'),
    ('Your password is required', 'Your password is required'),
    ('Use code 551234 now', 'Use code [SECRET] now'),
    ('Call 0770 000 111 today', 'Call [PHONE] today'),
    ('Call +256 772 123456', 'Call [PHONE]'),
    ('Email kato.b@school.ac.ug', 'Email [EMAIL]'),
    ('Read back 829104 to us', 'Read back [CODE] to us'),
    ('You won UGX 500,000 and 20GB', 'You won UGX 500,000 and 20GB'),
])
def test_redact(text, expected):
    assert redact(text) == expected
