"""Testy validačních funkcí modulu cashier_app.utils.events."""

import pytest
from cashier_app.utils.events import validate_event_or_booth_name


class TestValidateEventOrBoothName:

    def test_valid_name(self):
        ok, errors = validate_event_or_booth_name('Festival2025')
        assert ok is True
        assert errors == []

    def test_valid_name_with_dash(self):
        ok, errors = validate_event_or_booth_name('My-Event')
        assert ok is True

    def test_valid_name_with_dot(self):
        ok, errors = validate_event_or_booth_name('My.Event')
        assert ok is True

    def test_valid_name_with_underscore(self):
        ok, errors = validate_event_or_booth_name('My_Event')
        assert ok is True

    def test_too_short(self):
        ok, errors = validate_event_or_booth_name('ab')
        assert ok is False
        assert any('at least 3' in e for e in errors)

    def test_too_long(self):
        ok, errors = validate_event_or_booth_name('a' * 41)
        assert ok is False
        assert any('at most 40' in e for e in errors)

    def test_non_string(self):
        ok, errors = validate_event_or_booth_name(123)
        assert ok is False
        assert errors == ['name must be a string']

    def test_starts_with_special(self):
        ok, errors = validate_event_or_booth_name('.Event')
        assert ok is False

    def test_ends_with_special(self):
        ok, errors = validate_event_or_booth_name('Event.')
        assert ok is False

    def test_forbid_all_numeric(self):
        ok, errors = validate_event_or_booth_name('12345', forbid_all_numeric=True)
        assert ok is False

    def test_forbidden_substrings(self):
        ok, errors = validate_event_or_booth_name('TestEvent', forbidden_substrings=['test'])
        assert ok is False

    def test_unicode_latin_chars(self):
        ok, errors = validate_event_or_booth_name('Létó2025')
        assert ok is True

    def test_whitespace_trimmed(self):
        ok, errors = validate_event_or_booth_name('  Event1  ')
        assert ok is True
