"""Tests for cashier_app.utils.employees_users validation functions."""

import pytest
from cashier_app.utils.employees_users import (
    validate_username,
    validate_email,
    validate_new_password,
    validate_first_or_last_name,
    validate_phone_number,
    format_valid_phone_number,
    validate_other_identifier,
    add_more_phone_number_info,
)


# ---------------------------------------------------------------------------
# validate_username
# ---------------------------------------------------------------------------

class TestValidateUsername:

    def test_valid_username(self):
        ok, errors = validate_username('john_doe')
        assert ok is True
        assert errors == []

    def test_valid_username_with_dot(self):
        ok, errors = validate_username('john.doe')
        assert ok is True

    def test_valid_username_with_dash(self):
        ok, errors = validate_username('john-doe')
        assert ok is True

    def test_valid_username_min_length(self):
        ok, errors = validate_username('abc')
        assert ok is True

    def test_too_short(self):
        ok, errors = validate_username('ab')
        assert ok is False
        assert any('at least 3' in e for e in errors)

    def test_too_long(self):
        ok, errors = validate_username('a' * 41)
        assert ok is False
        assert any('at most 40' in e for e in errors)

    def test_non_string(self):
        ok, errors = validate_username(123)
        assert ok is False
        assert errors == ['username must be a string']

    def test_starts_with_special_char(self):
        ok, errors = validate_username('.john')
        assert ok is False

    def test_ends_with_special_char(self):
        ok, errors = validate_username('john.')
        assert ok is False

    def test_consecutive_special_chars(self):
        ok, errors = validate_username('john..doe')
        assert ok is False
        assert any('consecutive' in e for e in errors)

    def test_consecutive_mixed_special_chars(self):
        ok, errors = validate_username('john._doe')
        assert ok is False

    def test_forbid_all_numeric(self):
        ok, errors = validate_username('12345', forbid_all_numeric=True)
        assert ok is False
        assert any('all numeric' in e for e in errors)

    def test_all_numeric_allowed_by_default(self):
        ok, errors = validate_username('12345')
        assert ok is True

    def test_forbidden_substrings(self):
        ok, errors = validate_username('adminuser', forbidden_substrings=['admin'])
        assert ok is False
        assert any('reserved word' in e for e in errors)

    def test_unicode_latin_chars(self):
        ok, errors = validate_username('Černý')
        assert ok is True

    def test_whitespace_trimmed(self):
        ok, errors = validate_username('  john  ')
        assert ok is True


# ---------------------------------------------------------------------------
# validate_email
# ---------------------------------------------------------------------------

class TestValidateEmail:

    def test_valid_email(self):
        ok, errors = validate_email('user@example.com')
        assert ok is True
        assert errors == []

    def test_empty_email(self):
        ok, errors = validate_email('')
        assert ok is False
        assert errors == ['email is empty']

    def test_non_string(self):
        ok, errors = validate_email(42)
        assert ok is False
        assert errors == ['email must be a string']

    def test_invalid_format(self):
        ok, errors = validate_email('not-an-email')
        assert ok is False
        assert len(errors) > 0

    def test_missing_domain(self):
        ok, errors = validate_email('user@')
        assert ok is False

    def test_whitespace_trimmed(self):
        ok, errors = validate_email('  user@example.com  ')
        assert ok is True


# ---------------------------------------------------------------------------
# validate_new_password
# ---------------------------------------------------------------------------

class TestValidateNewPassword:

    def test_valid_password(self):
        ok, errors = validate_new_password('MyP@ssw0rd!')
        assert ok is True
        assert errors == []

    def test_too_short(self):
        ok, errors = validate_new_password('Ab1!')
        assert ok is False
        assert any('at least 8' in e for e in errors)

    def test_missing_uppercase(self):
        ok, errors = validate_new_password('mypassw0rd!')
        assert ok is False
        assert any('uppercase' in e for e in errors)

    def test_missing_lowercase(self):
        ok, errors = validate_new_password('MYPASSW0RD!')
        assert ok is False
        assert any('lowercase' in e for e in errors)

    def test_missing_digit(self):
        ok, errors = validate_new_password('MyPassword!')
        assert ok is False
        assert any('digit' in e for e in errors)

    def test_missing_special_char(self):
        ok, errors = validate_new_password('MyPassw0rd')
        assert ok is False
        assert any('special character' in e for e in errors)

    def test_contains_spaces(self):
        ok, errors = validate_new_password('My P@ss w0rd')
        assert ok is False
        assert any('spaces' in e for e in errors)

    def test_contains_tabs(self):
        ok, errors = validate_new_password('My\tP@ssw0rd')
        assert ok is False

    def test_non_string(self):
        ok, errors = validate_new_password(12345)
        assert ok is False
        assert errors == ['password must be a string']

    def test_empty_password(self):
        ok, errors = validate_new_password('')
        assert ok is False
        assert errors == ['password is empty']

    def test_contains_username(self):
        ok, errors = validate_new_password('MyP@ssadmin0!', username='admin')
        assert ok is False
        assert any('username' in e for e in errors)

    def test_contains_email_local_part(self):
        ok, errors = validate_new_password('MyP@ssuser0!', email='user@example.com')
        assert ok is False
        assert any('email' in e for e in errors)

    def test_forbidden_password(self):
        ok, errors = validate_new_password('Password1!', forbidden_passwords=['Password1!'])
        assert ok is False
        assert any('common' in e for e in errors)

    def test_repeated_characters(self):
        ok, errors = validate_new_password('AAAAAAbbb1!')
        assert ok is False
        assert any('repeated' in e for e in errors)

    def test_custom_min_length(self):
        ok, errors = validate_new_password('Ab1!', min_len=4)
        assert ok is True


# ---------------------------------------------------------------------------
# validate_first_or_last_name
# ---------------------------------------------------------------------------

class TestValidateFirstOrLastName:

    def test_valid_name(self):
        ok, errors = validate_first_or_last_name('John')
        assert ok is True

    def test_single_character(self):
        ok, errors = validate_first_or_last_name('A')
        assert ok is True

    def test_empty_name(self):
        ok, errors = validate_first_or_last_name('')
        assert ok is False

    def test_non_string(self):
        ok, errors = validate_first_or_last_name(123)
        assert ok is False
        assert errors == ['name must be a string']

    def test_too_long(self):
        ok, errors = validate_first_or_last_name('A' * 101)
        assert ok is False

    def test_unicode_chars(self):
        ok, errors = validate_first_or_last_name('Černý')
        assert ok is True

    def test_name_with_dash(self):
        ok, errors = validate_first_or_last_name('Jean-Pierre')
        assert ok is True

    def test_name_with_dot(self):
        ok, errors = validate_first_or_last_name('J.P.')
        assert ok is True

    def test_forbidden_substrings(self):
        ok, errors = validate_first_or_last_name('Badword', forbidden_substrings=['badword'])
        assert ok is False

    def test_whitespace_trimmed(self):
        ok, errors = validate_first_or_last_name('  Alice  ')
        assert ok is True


# ---------------------------------------------------------------------------
# validate_phone_number
# ---------------------------------------------------------------------------

class TestValidatePhoneNumber:

    def test_valid_czech_number(self):
        assert validate_phone_number('+420601234567') is True

    def test_valid_us_number(self):
        assert validate_phone_number('+12025551234') is True

    def test_invalid_number(self):
        assert validate_phone_number('not-a-number') is False

    def test_empty_string(self):
        assert validate_phone_number('') is False

    def test_too_short(self):
        assert validate_phone_number('+1234') is False

    def test_number_without_country_code(self):
        assert validate_phone_number('123456789') is False


# ---------------------------------------------------------------------------
# format_valid_phone_number
# ---------------------------------------------------------------------------

class TestFormatValidPhoneNumber:

    def test_returns_all_formats(self):
        result = format_valid_phone_number('+420601234567')
        assert 'e164' in result
        assert 'international' in result
        assert 'national' in result
        assert 'national_significant_number' in result
        assert 'country_code' in result

    def test_e164_format(self):
        result = format_valid_phone_number('+420601234567')
        assert result['e164'].startswith('+420')

    def test_country_code(self):
        result = format_valid_phone_number('+420601234567')
        assert result['country_code'] == '+420'


# ---------------------------------------------------------------------------
# validate_other_identifier
# ---------------------------------------------------------------------------

class TestValidateOtherIdentifier:

    def test_valid_identifier(self):
        ok, errors = validate_other_identifier('ID12345')
        assert ok is True

    def test_empty_is_invalid(self):
        ok, errors = validate_other_identifier('')
        assert ok is False

    def test_too_long(self):
        ok, errors = validate_other_identifier('A' * 101)
        assert ok is False

    def test_forbidden_substrings(self):
        ok, errors = validate_other_identifier('test_admin', forbidden_substrings=['admin'])
        assert ok is False


# ---------------------------------------------------------------------------
# add_more_phone_number_info
# ---------------------------------------------------------------------------

class TestAddMorePhoneNumberInfo:

    def test_adds_formats_to_user_with_phone(self):
        users = [{'phone_number': '+420601234567'}]
        add_more_phone_number_info(users)
        assert users[0]['phone_number_international'] is not None
        assert users[0]['phone_number_national'] is not None
        assert users[0]['phone_number_country_code'] == '+420'

    def test_none_phone_number(self):
        users = [{'phone_number': None}]
        add_more_phone_number_info(users)
        assert users[0]['phone_number_international'] is None
        assert users[0]['phone_number_country_code'] is None

    def test_multiple_users(self):
        users = [
            {'phone_number': '+420601234567'},
            {'phone_number': None},
        ]
        add_more_phone_number_info(users)
        assert users[0]['phone_number_country_code'] == '+420'
        assert users[1]['phone_number_country_code'] is None
