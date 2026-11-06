"""Synthetic chat screenshots with known ground truth, drawn in memory (never stored) for the extraction check."""
import io
import textwrap

from PIL import Image, ImageDraw, ImageFont

# Each case: header (chat name) and messages as (role, text). 'other' = the person who sent it, 'child' = the phone owner.
CASES = [
    ('MoMo Promo', [('other', 'Congratulations! You have won UGX 300,000 in the MoMo weekend draw.'),
                    ('other', 'To receive it send your PIN and the code we just sent you.'),
                    ('child', 'Really? How did I win?')]),
    ('Unknown number', [('other', 'Hello, I sent you a code by mistake. Please send it back to me.'),
                        ('child', 'Which code?'),
                        ('other', 'The 6 digit one that just came. Quickly please.')]),
    ('Scholarship Office', [('other', 'You have been shortlisted for the 2027 bursary.'),
                            ('other', 'Pay the processing fee of 50,000 before Friday to keep your place.'),
                            ('child', 'Can I ask my mum first?')]),
    ('Brian (class)', [('child', 'Did you finish the maths homework?'),
                       ('other', 'Yes, page 54. Meet at the library at 2.'),
                       ('child', 'Okay see you')]),
    ('Free Data', [('other', 'FREE 20GB data for students! Claim before midnight at mtn-ug-bonus.xyz/claim'),
                   ('child', 'Is this real?')]),
    ('Mum', [('other', 'I will be late from work today. Please warm the food.'),
             ('child', 'Okay mum'),
             ('other', 'And do your homework first.')]),
]

W = 720
_PAD, _BUBBLE_PAD, _LINE = 24, 16, 30


def _font(size):
    try:
        return ImageFont.load_default(size=size)
    except TypeError:                     # very old Pillow
        return ImageFont.load_default()


def render(header: str, messages) -> bytes:
    font, head_font = _font(24), _font(28)
    blocks = []
    for role, text in messages:
        lines = textwrap.wrap(text, 34)
        blocks.append((role, lines, len(lines) * _LINE + 2 * _BUBBLE_PAD))
    height = 110 + sum(h + 22 for _, _, h in blocks) + _PAD
    img = Image.new('RGB', (W, height), '#ece5dd')
    d = ImageDraw.Draw(img)
    d.rectangle([0, 0, W, 80], fill='#075e54')
    d.text((_PAD, 24), header, fill='white', font=head_font)
    y = 104
    for role, lines, h in blocks:
        width = max(d.textlength(line, font=font) for line in lines) + 2 * _BUBBLE_PAD
        x0 = W - _PAD - width if role == 'child' else _PAD
        d.rounded_rectangle([x0, y, x0 + width, y + h], radius=14, fill='#dcf8c6' if role == 'child' else 'white')
        for i, line in enumerate(lines):
            d.text((x0 + _BUBBLE_PAD, y + _BUBBLE_PAD + i * _LINE), line, fill='#111111', font=font)
        y += h + 22
    buf = io.BytesIO()
    img.save(buf, 'PNG')
    return buf.getvalue()
