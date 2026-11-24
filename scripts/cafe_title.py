"""Canonical display text for an already approved public Cafe notice title.

Only the credential-free public reviewer calls this at ingestion. It does not
make an unverified row publishable or repair caller-supplied runtime evidence.
Literal angle punctuation is displayed with fullwidth characters so the same
title passes the existing strict server and browser metadata checks.
"""
from html import unescape
import re

TITLE_LIMIT = 220
ANGLE_DISPLAY = str.maketrans({'<': '＜', '>': '＞'})
NUMERIC_ENTITY = re.compile(r'&#(?:[xX]([0-9a-fA-F]+)|([0-9]+));?')


def _reject_controls(value):
    # Preserve the reviewer's existing whitespace collapse, but never silently
    # remove non-whitespace C0 controls. html.unescape can otherwise drop them.
    if any(ord(c) < 32 and not c.isspace() for c in value):
        raise ValueError('invalid_public_title_control')
    if any(0xD800 <= ord(c) <= 0xDFFF for c in value):
        raise ValueError('invalid_public_title_unicode')
    for match in NUMERIC_ENTITY.finditer(value):
        number = int(match[1], 16) if match[1] is not None else int(match[2])
        if number < 32 and not chr(number).isspace():
            raise ValueError('invalid_public_title_control')


def _browser_bounded(value):
    # The deployed JavaScript validator counts UTF-16 units, while Python len
    # counts Unicode code points. Keep supplementary emoji whole within both.
    chars = []
    units = 0
    for char in value:
        width = 2 if ord(char) > 0xFFFF else 1
        if units + width > TITLE_LIMIT:
            break
        chars.append(char)
        units += width
    return ''.join(chars).rstrip()


def normalize_reviewed_title(value):
    """Return one bounded title shared by proof, publication, and the browser.

Decode entities to a fixed point before replacing angle punctuation. A single
decode would leave nested entities for schedule_feed.text() to decode later,
making the published title differ from the approved evidence. The input has
the same 220-character bound as the existing reviewer, so decoding is bounded.
    """
    title = ' '.join(str(value or '').split())[:TITLE_LIMIT]
    for _ in range(TITLE_LIMIT + 1):
        _reject_controls(title)
        decoded = unescape(title)
        if decoded == title:
            break
        title = decoded
    else:
        raise ValueError('invalid_public_title_entities')
    return _browser_bounded(' '.join(title.translate(ANGLE_DISPLAY).split()))
