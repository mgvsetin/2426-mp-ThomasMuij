from typing import List, Tuple
import unicodedata
import os
import shutil
import uuid
from flask import Flask, request, url_for, jsonify, current_app
from werkzeug.utils import secure_filename
from PIL import Image
from werkzeug.exceptions import RequestEntityTooLarge


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
    - "price must must be a whole number"
    - "price must be more than or equal to {min_price}"
    - "price must be less than or equal to {max_price}"
    """

    errors: List[str] = []
    try:
        price = float(price)
    except (TypeError, ValueError):
        return False, ["price must be a number"]
    
    if not price.is_integer():
        errors.append("price must must be a whole number")

    # if price < 0:
    #     errors.append("price must be positive")

    if price < min_price:
        errors.append(f"price must be more than or equal to {min_price}")
    if price > max_price:
        errors.append(f"price must be less than or equal to {max_price}")

    return (len(errors) == 0), errors


ALLOWED_IMAGE_EXTENSIONS = {'jpeg', 'png', 'webp'}
ALLOWED_MIME_TYPES = {'image/jpeg', 'image/png', 'image/webp'}


def image_extension_is_allowed(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in (current_app.config.get('ALLOWED_IMAGE_EXTENSIONS') if current_app.config.get('ALLOWED_IMAGE_EXTENSIONS') else ALLOWED_IMAGE_EXTENSIONS)


def verify_image_file_get_info(file_obj, pixel_limit=None):
    if pixel_limit is None:
        try:
            pixel_limit = current_app.config.get('UPLOAD_IMAGE_PIXEL_LIMIT')
        except Exception:
            pass

    file_obj.stream.seek(0)
    try:
        Image.open(file_obj.stream).verify() # verify -> musíme otevřít znovu
        Image.open(file_obj.stream).load()
        image_file = Image.open(file_obj.stream)
    except Exception:
        file_obj.stream.seek(0)
        return False, {}
    file_obj.stream.seek(0)

    image_format = image_file.format  # např. 'JPEG', 'PNG', 'WEBP', 'GIF', etc.
    if not image_format:
        return False, {}

    mime_from_pillow = Image.MIME.get(image_format.upper())  # např. 'image/jpeg'

    if mime_from_pillow not in (current_app.config.get('ALLOWED_IMAGE_MIME_TYPES') if current_app.config.get('ALLOWED_IMAGE_MIME_TYPES') else ALLOWED_MIME_TYPES):
        return False, {}
    
    if pixel_limit:
        width, height = image_file.size
        if width * height > pixel_limit:
            return False, {}

    return True, {
        'height': image_file.height,
        'width': image_file.width,
        'mime_type': mime_from_pillow
        }


def save_unique_stream(file_obj, dest_dir, secure_name, max_attempts=1000):
    """
    Uloží obsah z file_obj.stream do dest_dir pod jedinečným jménem.

    Snaží se vytvořit soubor s `secure_name`, pak `base_1`, `base_2`, ... až `max_attempts`.
    Pokud to selže, zkusí až 5 variací s UUID. Vytváří soubor atomicky přes O_EXCL.
    Kontroluje MAX_CONTENT_LENGTH z Flask `current_app.config` (pokud dostupné)
    a při přetečení vyhodí `RequestEntityTooLarge`. Při chybě se částečný soubor smaže
    a (pokud je seekovatelný) stream se vrátí na pozici 0.

    Args:
        file_obj: objekt s atributem `.stream` (např. Flask FileStorage).
        dest_dir (str): cílový adresář (musí existovat a být zapisovatelný).
        secure_name (str): navržené bezpečné jméno souboru.
        max_attempts (int): počet číslovaných pokusů (default 1000).

    Returns:
        str: skutečné jméno uloženého souboru.

    Raises:
        PermissionError, OSError,
        RequestEntityTooLarge (při překročení MAX_CONTENT_LENGTH),
        RuntimeError("unable_to_create_unique_filename") (pokud se nepodaří najít volné jméno).
    """
    base, ext = os.path.splitext(secure_name)
    if not ext:
        ext = ''

    MAX_BYTES = None
    try:
        from flask import current_app
        MAX_BYTES = current_app.config.get('MAX_CONTENT_LENGTH', None)
    except Exception:
        MAX_BYTES = None

    chunk_size = 4096

    def _write_and_cleanup(file_descriptor, stream, dest_path):
        bytes_written = 0
        try:
            with os.fdopen(file_descriptor, 'wb') as out_file:
                while True:
                    chunk = stream.read(chunk_size)
                    if not chunk:
                        break
                    if MAX_BYTES is not None and (bytes_written + len(chunk) > MAX_BYTES):
                        raise RuntimeError("__TOO_LARGE__")
                    out_file.write(chunk)
                    bytes_written += len(chunk)
        except Exception as exc:
            try:
                if os.path.exists(dest_path):
                    os.remove(dest_path)
            except Exception:
                pass
            if isinstance(exc, RuntimeError) and str(exc) == "__TOO_LARGE__":
                raise RequestEntityTooLarge()
            raise
        finally:
            try:
                if hasattr(stream, 'seek') and getattr(stream, 'seekable', lambda: True)():
                    stream.seek(0)
            except Exception:
                pass

    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL  # O_EXCL zabrání race overwrite

    # zkus base, base_1, base_2, ...
    for i in range(max_attempts):
        candidate = secure_name if i == 0 else f"{base}_{i}{ext}"
        dest_path = os.path.join(dest_dir, candidate)
        try:
            file_descriptor = os.open(dest_path, flags, 0o644)
        except FileExistsError:
            continue
        except PermissionError:
            raise
        except OSError:
            raise
        else:
            _write_and_cleanup(file_descriptor, file_obj.stream, dest_path)
            return candidate

    # moc pokusů -> použij UUID
    for _ in range(5):
        candidate = f"{base}_{uuid.uuid4().hex}{ext}"
        dest_path = os.path.join(dest_dir, candidate)
        try:
            file_descriptor = os.open(dest_path, flags, 0o644)
        except FileExistsError:
            continue
        except PermissionError:
            raise
        else:
            _write_and_cleanup(file_descriptor, file_obj.stream, dest_path)
            return candidate

    raise RuntimeError("unable_to_create_unique_filename")


def convert_image_paths_from_relative(products):
    for product in products:
        if product['image_path']:
            product['image_path'] = url_for('static', filename=product['image_path'])