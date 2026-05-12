"""Pomocné funkce pro validaci produktů/kategorií, ověřování a ukládání obrázků."""

from typing import List, Tuple
import unicodedata
from flask import url_for


def validate_product_or_category_name(
    name: str,
    min_len: int = 1,
    max_len: int = 100
    ) -> Tuple[bool, List[str]]:
    """
    Validate a product or category name.

    Rules (defaults):
      - length between min_len and max_len

    Returns:
      (is_valid, errors)

    Possible error messages (one or more may be returned):
    - "name must be a string"
    - "name must be at least {min_len} characters"
    - "name must be at most {max_len} characters"
    """

    errors: List[str] = []
    if not isinstance(name, str):
        return False, ["name must be a string"]

    name = unicodedata.normalize("NFC", name)
    name = name.strip()
    if len(name) < min_len:
        errors.append(f"name must be at least {min_len} characters")
    if len(name) > max_len:
        errors.append(f"name must be at most {max_len} characters")

    return (len(errors) == 0), errors


def validate_product_price(
    price: str | int | float,
    min_price: int = -100_000,
    max_price: int = 100_000,
    ) -> Tuple[bool, List[str]]:
    """
    Validate product price.

    Rules (defaults):
      - price must be a whole number (can be represented as a different data type)
      - must be between min_price and max_price

    Returns:
      (is_valid, errors)

    Possible error messages (one or more may be returned):
    - "price must be a number"
    - "price must be a whole number"
    - "price must be more than or equal to {min_price}"
    - "price must be less than or equal to {max_price}"
    """

    errors: List[str] = []
    try:
        price = float(price)
    except (TypeError, ValueError):
        return False, ["price must be a number"]
    
    if not price.is_integer():
        errors.append("price must be a whole number")

    # if price < 0:
    #     errors.append("price must be positive")

    if price < min_price:
        errors.append(f"price must be more than or equal to {min_price}")
    if price > max_price:
        errors.append(f"price must be less than or equal to {max_price}")

    return (len(errors) == 0), errors


def convert_image_paths_from_relative(products):
    """Převede relativní cesty obrázků produktů na absolutní URL."""
    for product in products:
        if product['image_path']:
            product['image_path'] = url_for('uploaded_product_image', filename=product['image_path'])