import os
import time
from pathlib import Path
from flask import current_app
from cashier_app.db import get_pool

from cashier_app.utils.query_builder import build_insert_statement


def relative_posix_path(full_path: str, base: str | None = None) -> str:
    base_path = Path(base).resolve()
    full_path = Path(full_path).resolve()

    try:
        rel = full_path.relative_to(base_path)
    except ValueError:
        # Not inside base_path; fall back to relpath which can contain .. components
        rel = Path(os.path.relpath(str(full_path), start=str(base_path)))

    return rel.as_posix()


def remove_image_if_exists(path):
    if not path or not os.path.exists(path):
        return True
    
    # Retry logic for Windows file locking
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
    # smaž soubory na disku, které nemají žádný řádek v DB
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