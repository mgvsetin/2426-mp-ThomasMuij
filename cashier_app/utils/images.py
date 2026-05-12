"""Pomocné funkce pro správu obrázků produktů – mazání nepoužívaných obrázků a osiřelých souborů z disku."""

import os
import time
from pathlib import Path
from flask import current_app
from cashier_app.db import get_pool
import uuid
from werkzeug.utils import secure_filename
from PIL import Image
from werkzeug.exceptions import RequestEntityTooLarge

from cashier_app.utils.query_builder import build_insert_statement


def relative_posix_path(full_path: str, base: str | None = None) -> str:
    """Vrátí relativní POSIX cestu od base k full_path."""
    base_path = Path(base).resolve()
    full_path = Path(full_path).resolve()

    try:
        rel = full_path.relative_to(base_path)
    except ValueError:
        # Není uvnitř base_path; záložní řešení přes relpath, které může obsahovat .. komponenty
        rel = Path(os.path.relpath(str(full_path), start=str(base_path)))

    return rel.as_posix()


ALLOWED_IMAGE_EXTENSIONS = {'jpeg', 'jpg', 'png', 'webp'}
ALLOWED_MIME_TYPES = {'image/jpeg', 'image/png', 'image/webp'}
UPLOAD_IMAGE_PIXEL_LIMIT = 50_000_000


def _get_allowed_exts():
    """Vrátí množinu povolených přípon obrázků z konfigurace aplikace."""
    v = current_app.config.get('ALLOWED_IMAGE_EXTENSIONS')
    if not v:
        return set(ALLOWED_IMAGE_EXTENSIONS)
    return {str(x).lower() for x in (v if isinstance(v, (set, list, tuple)) else [v])}

def _get_allowed_mime_types():
    """Vrátí množinu povolených MIME typů obrázků z konfigurace aplikace."""
    v = current_app.config.get('ALLOWED_IMAGE_MIME_TYPES')
    if not v:
        return set(ALLOWED_MIME_TYPES)
    return {str(x).lower() for x in (v if isinstance(v, (set, list, tuple)) else [v])}


def image_extension_is_allowed(filename):
    """Ověří, zda má soubor povolenou příponu obrázku."""
    if '.' not in filename:
        return False

    ext = filename.rsplit('.', 1)[1].lower()
    return ext in _get_allowed_exts()


def verify_image_file_get_info(file_obj, pixel_limit=None):
    """Ověří platnost obrázku a vrátí informace (rozměry, MIME typ).

    Vrátí (True, info_dict) při úspěchu nebo (False, {}) při neplatném obrázku.
    """
    if pixel_limit is None:
        try:
            pixel_limit = current_app.config.get('UPLOAD_IMAGE_PIXEL_LIMIT', UPLOAD_IMAGE_PIXEL_LIMIT)
        except Exception:
            pixel_limit = UPLOAD_IMAGE_PIXEL_LIMIT

    Image.MAX_IMAGE_PIXELS = pixel_limit

    try:
        file_obj.stream.seek(0)
        with Image.open(file_obj.stream) as img:
            img.verify() # verify -> musíme otevřít znovu

        file_obj.stream.seek(0)
        with Image.open(file_obj.stream) as image_file:
            image_format = image_file.format  # např. 'JPEG', 'PNG', 'WEBP', 'GIF', etc.
            if not image_format:
                return False, {}

            mime_from_pillow = Image.MIME.get(image_format.upper())  # např. 'image/jpeg'

            if mime_from_pillow not in _get_allowed_mime_types():
                return False, {}
            
            width, height = image_file.size
            if width * height > pixel_limit:
                return False, {}
                
            info = {
                'height': image_file.height,
                'width': image_file.width,
                'mime_type': mime_from_pillow
            }

        file_obj.stream.seek(0)
        with Image.open(file_obj.stream) as img:
            img.load()

        file_obj.stream.seek(0)
        return True, info
    except Exception:
        file_obj.stream.seek(0)
        return False, {}


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

    # nemělo by se nikdy stát:
    if os.path.basename(secure_name) != secure_name:
        raise RuntimeError("filename_is_not_secure")
    
    if not dest_dir:
        raise RuntimeError("no dest_dir")
    dest_dir = os.path.abspath(dest_dir)
    if not os.path.isdir(dest_dir):
        raise RuntimeError("dest_dir folder not found")

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


def save_image_get_params(image_file):
    """Ověří, uloží obrázek a vrátí slovník s parametry pro uložení do databáze.

    Při chybě vrátí slovník s klíči 'error' a 'code'.
    """
    safe_filename = secure_filename(image_file.filename)

    max_filename_len = current_app.config.get('MAX_FILENAME_LEN', 255)
    if len(safe_filename) > max_filename_len:
        base, ext = os.path.splitext(safe_filename)
        safe_filename = base[:max_filename_len - len(ext)] + ext

    if not image_extension_is_allowed(safe_filename):
        return {'error': 'disallowed_image_extension', 'code': 400}
    
    image_is_ok, image_info = verify_image_file_get_info(image_file)
    if not image_is_ok:
        return {'error': 'image_file_is_invalid', 'code': 400}

    dest_dir = current_app.config.get('UPLOAD_FOLDER')
    try:
        saved_name = save_unique_stream(image_file, dest_dir, safe_filename)
    except (PermissionError, OSError, RuntimeError):
        return {'error': 'unable_to_save_file', 'code': 500}
    except RequestEntityTooLarge:
        return {'error': 'file_too_large', 'code': 413}
    
    product_images_params = {
    'image_path': saved_name,
    'image_filename': saved_name,
    'image_mime_type': image_info['mime_type'],
    'image_size_bytes': Path(dest_dir, saved_name).stat().st_size,
    'image_width': image_info['width'],
    'image_height': image_info['height']
    }

    return product_images_params



def remove_image_if_exists(path):
    """Smaže obrázek na dané cestě, pokud existuje. Vrátí True při úspěchu."""
    if not path or not os.path.exists(path):
        return True
    
    # Opakované pokusy kvůli zamykání souborů na Windows
    max_attempts = 2
    for attempt in range(max_attempts):
        try:
            os.remove(path)
            return True
        except PermissionError:
            if attempt < max_attempts - 1:
                time.sleep(0.1)
            else:
                current_app.logger.warning('failed to remove image %s after %d attempts', path, max_attempts)
        except OSError:
            current_app.logger.warning('failed to remove image %s', path)
            return False
    return False


def delete_unused_images():
    """Smaže obrázky produktů, které nejsou referencovány žádným aktivním produktem ani historií změn."""
    rows_failed_to_delete_img = []
    with get_pool().connection() as conn:
        with conn.cursor() as cur:
            unused_image_rows = cur.execute(
                '''
                DELETE FROM product_images AS img
                WHERE NOT EXISTS (
                    SELECT 1
                    FROM products AS p
                    WHERE p.image_id = img.id
                    AND p.deleted_at IS NULL
                )
                AND NOT EXISTS (
                    SELECT 1
                    FROM change_history ch,
                    jsonb_array_elements(ch.changes) AS elem
                    WHERE elem->>'table' = 'products'
                    AND (
                        (elem->'old_values'->>'image_id') = img.id::text
                        OR (elem->'new_values'->>'image_id') = img.id::text
                    )
                )
                RETURNING img.image_path, 0 AS attempt''').fetchall()
            unused_image_rows += cur.execute(
                '''
                DELETE FROM product_images_failed_to_delete
                RETURNING image_path, attempt''',
                ).fetchall()
    for image_row_to_delete in unused_image_rows:
        unused_image_path = Path(current_app.config['UPLOAD_FOLDER'], image_row_to_delete['image_path'])

        success = remove_image_if_exists(unused_image_path)

        if not success:
            if image_row_to_delete['attempt'] < 5:
                image_row_to_delete['attempt'] += 1
                rows_failed_to_delete_img.append(image_row_to_delete)
            else:
                current_app.logger.exception('failed to delete image %s after %s requests', image_row_to_delete['image_path'], image_row_to_delete['attempt'])
    
    if rows_failed_to_delete_img:
        sql, query_params = build_insert_statement('product_images_failed_to_delete', rows_failed_to_delete_img)

        # jestli nešel smazat obrázek, tak vytvoř řadu, aby se smazal příště
        with get_pool().connection() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, query_params)


def delete_disk_orphans():
    """Smaže soubory obrázků na disku, které nemají žádný odpovídající záznam v databázi."""
    image_dir = current_app.config.get('UPLOAD_FOLDER')
    if image_dir and os.path.isdir(image_dir):
        filenames_on_disk = {f for f in os.listdir(image_dir)
                            if os.path.isfile(os.path.join(image_dir, f))}

        if filenames_on_disk:
            with get_pool().connection() as conn:
                with conn.cursor() as cur:
                    known_rows = cur.execute(
                        'SELECT image_path FROM product_images'
                    ).fetchall()
                    failed_rows = cur.execute(
                        'SELECT image_path FROM product_images_failed_to_delete'
                    ).fetchall()

            known_filenames = {os.path.basename(row['image_path'])
                               for row in known_rows + failed_rows}

            for filename in filenames_on_disk - known_filenames:
                remove_image_if_exists(Path(image_dir, filename))