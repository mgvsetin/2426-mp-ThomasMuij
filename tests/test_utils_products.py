"""Testy validačních funkcí modulu cashier_app.utils.products."""

import pytest
from cashier_app.utils.products import (
    validate_product_or_category_name,
    validate_product_price,
)


# ---------------------------------------------------------------------------
# validate_product_or_category_name – validace názvu produktu nebo kategorie
# ---------------------------------------------------------------------------

class TestValidateProductOrCategoryName:

    def test_valid_name(self):
        ok, errors = validate_product_or_category_name('Beer')
        assert ok is True
        assert errors == []

    def test_empty_name(self):
        ok, errors = validate_product_or_category_name('')
        assert ok is False
        assert any('at least 1' in e for e in errors)

    def test_too_long(self):
        ok, errors = validate_product_or_category_name('A' * 101)
        assert ok is False
        assert any('at most 100' in e for e in errors)

    def test_non_string(self):
        ok, errors = validate_product_or_category_name(42)
        assert ok is False
        assert errors == ['name must be a string']

    def test_whitespace_only_trimmed_to_empty(self):
        ok, errors = validate_product_or_category_name('   ')
        assert ok is False

    def test_exactly_max_length(self):
        ok, errors = validate_product_or_category_name('A' * 100)
        assert ok is True

    def test_unicode_name(self):
        ok, errors = validate_product_or_category_name('Pivo české')
        assert ok is True

    def test_custom_limits(self):
        ok, errors = validate_product_or_category_name('AB', min_len=3)
        assert ok is False

        ok, errors = validate_product_or_category_name('ABCDE', max_len=3)
        assert ok is False


# ---------------------------------------------------------------------------
# validate_product_price – validace ceny produktu
# ---------------------------------------------------------------------------

class TestValidateProductPrice:

    def test_valid_integer_price(self):
        ok, errors = validate_product_price(100)
        assert ok is True
        assert errors == []

    def test_valid_zero_price(self):
        ok, errors = validate_product_price(0)
        assert ok is True

    def test_valid_negative_price(self):
        ok, errors = validate_product_price(-50)
        assert ok is True

    def test_valid_string_number(self):
        ok, errors = validate_product_price('200')
        assert ok is True

    def test_valid_float_whole_number(self):
        ok, errors = validate_product_price(50.0)
        assert ok is True

    def test_invalid_float(self):
        ok, errors = validate_product_price(10.5)
        assert ok is False
        assert any('whole number' in e for e in errors)

    def test_non_numeric_string(self):
        ok, errors = validate_product_price('abc')
        assert ok is False
        assert errors == ['price must be a number']

    def test_none_value(self):
        ok, errors = validate_product_price(None)
        assert ok is False
        assert errors == ['price must be a number']

    def test_too_low(self):
        ok, errors = validate_product_price(-100_001)
        assert ok is False
        assert any('more than or equal to' in e for e in errors)

    def test_too_high(self):
        ok, errors = validate_product_price(100_001)
        assert ok is False
        assert any('less than or equal to' in e for e in errors)

    def test_boundary_min(self):
        ok, errors = validate_product_price(-100_000)
        assert ok is True

    def test_boundary_max(self):
        ok, errors = validate_product_price(100_000)
        assert ok is True

    def test_custom_limits(self):
        ok, errors = validate_product_price(5, min_price=10)
        assert ok is False

        ok, errors = validate_product_price(15, max_price=10)
        assert ok is False
