"""Testy zálohování a obnovy databáze."""

import os
import pytest
from unittest.mock import patch, MagicMock

from cashier_app.db import (
    backup_db, restore_db, get_latest_backup, _rotate_backups,
    backup_db_command, restore_db_command,
)


@pytest.fixture()
def app_with_cli(app):
    """Zaregistruje backup/restore CLI příkazy (db.init_app je v testech patchnutý)."""
    app.cli.add_command(backup_db_command)
    app.cli.add_command(restore_db_command)
    return app


class TestBackupDb:

    def test_calls_pg_dump_with_correct_args(self, app_context, tmp_path):
        app_context.config['BACKUP_DIR'] = str(tmp_path)
        app_context.config['DATABASE_CONNINFO'] = 'dbname=testdb'

        mock_result = MagicMock(returncode=0)
        with patch('cashier_app.db.subprocess.run', return_value=mock_result) as mock_run:
            filepath = backup_db()

        args = mock_run.call_args[0][0]
        assert args[0] == 'pg_dump'
        assert '--dbname' in args
        assert 'dbname=testdb' in args
        assert '-Fc' in args
        assert filepath.endswith('.dump')

    def test_creates_dump_file_path_with_timestamp(self, app_context, tmp_path):
        app_context.config['BACKUP_DIR'] = str(tmp_path)

        mock_result = MagicMock(returncode=0)
        with patch('cashier_app.db.subprocess.run', return_value=mock_result):
            filepath = backup_db()

        filename = os.path.basename(filepath)
        assert filename.startswith('backup_')
        assert filename.endswith('.dump')

    def test_creates_backup_dir_if_missing(self, app_context, tmp_path):
        backup_dir = str(tmp_path / 'new_dir')
        app_context.config['BACKUP_DIR'] = backup_dir

        mock_result = MagicMock(returncode=0)
        with patch('cashier_app.db.subprocess.run', return_value=mock_result):
            backup_db()

        assert os.path.isdir(backup_dir)

    def test_raises_on_pg_dump_failure(self, app_context, tmp_path):
        app_context.config['BACKUP_DIR'] = str(tmp_path)

        mock_result = MagicMock(returncode=1, stderr='connection refused')
        with patch('cashier_app.db.subprocess.run', return_value=mock_result):
            with pytest.raises(RuntimeError, match='pg_dump selhal'):
                backup_db()

    def test_cleans_up_file_on_pg_dump_failure(self, app_context, tmp_path):
        app_context.config['BACKUP_DIR'] = str(tmp_path)

        # Vytvoř soubor, který by pg_dump zanechal
        mock_result = MagicMock(returncode=1, stderr='error')
        with patch('cashier_app.db.subprocess.run', return_value=mock_result):
            with pytest.raises(RuntimeError):
                backup_db()

        # Žádný .dump soubor by neměl zůstat
        dumps = [f for f in os.listdir(tmp_path) if f.endswith('.dump')]
        assert dumps == []

    def test_calls_rotate_after_backup(self, app_context, tmp_path):
        app_context.config['BACKUP_DIR'] = str(tmp_path)
        app_context.config['BACKUP_MAX_COUNT'] = 5

        mock_result = MagicMock(returncode=0)
        with patch('cashier_app.db.subprocess.run', return_value=mock_result), \
             patch('cashier_app.db._rotate_backups') as mock_rotate:
            backup_db()

        mock_rotate.assert_called_once_with(str(tmp_path), 5)


class TestRotateBackups:

    def test_keeps_max_count(self, tmp_path):
        for i in range(5):
            (tmp_path / f'backup_2026-03-{20+i:02d}_120000.dump').touch()

        _rotate_backups(str(tmp_path), 3)

        remaining = sorted(f for f in os.listdir(tmp_path) if f.endswith('.dump'))
        assert len(remaining) == 3
        # nejstarší 2 smazány, zůstaly 3 nejnovější
        assert remaining[0] == 'backup_2026-03-22_120000.dump'

    def test_no_delete_when_under_limit(self, tmp_path):
        for i in range(2):
            (tmp_path / f'backup_2026-03-{20+i:02d}_120000.dump').touch()

        _rotate_backups(str(tmp_path), 5)

        remaining = [f for f in os.listdir(tmp_path) if f.endswith('.dump')]
        assert len(remaining) == 2

    def test_ignores_non_backup_files(self, tmp_path):
        (tmp_path / 'backup_2026-03-20_120000.dump').touch()
        (tmp_path / 'notes.txt').touch()
        (tmp_path / 'backup_old.sql').touch()

        _rotate_backups(str(tmp_path), 1)

        all_files = os.listdir(tmp_path)
        assert 'notes.txt' in all_files
        assert 'backup_old.sql' in all_files
        assert 'backup_2026-03-20_120000.dump' in all_files


class TestGetLatestBackup:

    def test_returns_newest_backup(self, app_context, tmp_path):
        app_context.config['BACKUP_DIR'] = str(tmp_path)

        (tmp_path / 'backup_2026-03-20_100000.dump').touch()
        (tmp_path / 'backup_2026-03-22_100000.dump').touch()
        (tmp_path / 'backup_2026-03-21_100000.dump').touch()

        result = get_latest_backup()
        assert os.path.basename(result) == 'backup_2026-03-22_100000.dump'

    def test_raises_when_no_backups(self, app_context, tmp_path):
        app_context.config['BACKUP_DIR'] = str(tmp_path)

        with pytest.raises(FileNotFoundError, match='Žádná záloha'):
            get_latest_backup()

    def test_raises_when_dir_missing(self, app_context, tmp_path):
        app_context.config['BACKUP_DIR'] = str(tmp_path / 'nonexistent')

        with pytest.raises(FileNotFoundError, match='neexistuje'):
            get_latest_backup()


class TestRestoreDb:

    def test_calls_pg_restore_with_correct_args(self, app_context, tmp_path):
        dump_file = tmp_path / 'backup_2026-03-20_120000.dump'
        dump_file.touch()
        app_context.config['DATABASE_CONNINFO'] = 'dbname=testdb'

        mock_result = MagicMock(returncode=0)
        with patch('cashier_app.db.subprocess.run', return_value=mock_result) as mock_run:
            restore_db(str(dump_file))

        args = mock_run.call_args[0][0]
        assert args[0] == 'pg_restore'
        assert '--dbname' in args
        assert 'dbname=testdb' in args
        assert '--clean' in args
        assert '--if-exists' in args
        assert '--single-transaction' in args
        assert '--exit-on-error' in args
        assert str(dump_file) in args

    def test_uses_latest_backup_when_no_filepath(self, app_context, tmp_path):
        app_context.config['BACKUP_DIR'] = str(tmp_path)

        dump_file = tmp_path / 'backup_2026-03-20_120000.dump'
        dump_file.touch()

        mock_result = MagicMock(returncode=0)
        with patch('cashier_app.db.subprocess.run', return_value=mock_result) as mock_run:
            restored = restore_db()

        assert restored == str(dump_file)
        # ověř, že se pg_restore zavolal s tímto souborem
        args = mock_run.call_args[0][0]
        assert str(dump_file) in args

    def test_raises_on_missing_file(self, app_context):
        with pytest.raises(FileNotFoundError, match='nenalezen'):
            restore_db('/nonexistent/backup.dump')

    def test_raises_on_pg_restore_failure(self, app_context, tmp_path):
        dump_file = tmp_path / 'backup_2026-03-20_120000.dump'
        dump_file.touch()

        mock_result = MagicMock(returncode=1, stderr='error restoring')
        with patch('cashier_app.db.subprocess.run', return_value=mock_result):
            with pytest.raises(RuntimeError, match='pg_restore selhal'):
                restore_db(str(dump_file))

    def test_returns_filepath(self, app_context, tmp_path):
        dump_file = tmp_path / 'backup_2026-03-20_120000.dump'
        dump_file.touch()

        mock_result = MagicMock(returncode=0)
        with patch('cashier_app.db.subprocess.run', return_value=mock_result):
            result = restore_db(str(dump_file))

        assert result == str(dump_file)


class TestBackupCli:

    def test_backup_db_command_success(self, app_with_cli):
        runner = app_with_cli.test_cli_runner()

        mock_result = MagicMock(returncode=0)
        with patch('cashier_app.db.subprocess.run', return_value=mock_result):
            result = runner.invoke(args=['backup-db'])

        assert result.exit_code == 0
        assert 'Záloha databáze vytvořena' in result.output

    def test_backup_db_command_failure(self, app_with_cli):
        runner = app_with_cli.test_cli_runner()

        mock_result = MagicMock(returncode=1, stderr='connection refused')
        with patch('cashier_app.db.subprocess.run', return_value=mock_result):
            result = runner.invoke(args=['backup-db'])

        assert result.exit_code == 1

    def test_restore_db_command_success(self, app_with_cli, tmp_path):
        runner = app_with_cli.test_cli_runner()

        dump_file = tmp_path / 'backup_2026-03-20_120000.dump'
        dump_file.touch()

        mock_result = MagicMock(returncode=0)
        with patch('cashier_app.db.subprocess.run', return_value=mock_result):
            result = runner.invoke(args=['restore-db', str(dump_file)])

        assert result.exit_code == 0
        assert 'Databáze obnovena ze zálohy' in result.output

    def test_restore_db_command_latest(self, app_with_cli, tmp_path):
        app_with_cli.config['BACKUP_DIR'] = str(tmp_path)
        runner = app_with_cli.test_cli_runner()

        dump_file = tmp_path / 'backup_2026-03-20_120000.dump'
        dump_file.touch()

        mock_result = MagicMock(returncode=0)
        with patch('cashier_app.db.subprocess.run', return_value=mock_result):
            result = runner.invoke(args=['restore-db'])

        assert result.exit_code == 0
        assert 'backup_2026-03-20_120000.dump' in result.output

    def test_restore_db_command_missing_file(self, app_with_cli):
        runner = app_with_cli.test_cli_runner()

        result = runner.invoke(args=['restore-db', '/nonexistent/file.dump'])

        assert result.exit_code == 1

    def test_restore_db_command_failure(self, app_with_cli, tmp_path):
        runner = app_with_cli.test_cli_runner()

        dump_file = tmp_path / 'backup_2026-03-20_120000.dump'
        dump_file.touch()

        mock_result = MagicMock(returncode=1, stderr='error')
        with patch('cashier_app.db.subprocess.run', return_value=mock_result):
            result = runner.invoke(args=['restore-db', str(dump_file)])

        assert result.exit_code == 1


# ---------------------------------------------------------------------------
# Integrační testy – vyžadují běžící PostgreSQL (pytest -m db)
# ---------------------------------------------------------------------------

from tests.conftest import DB_TEST_CONNINFO, FAKE_HASH
from cashier_app import create_app


@pytest.fixture()
def backup_app(tmp_path, _db_pool):
    """Flask app s test DB konfigurací pro integrační backup testy.

    Po testu reinicializuje schéma testovací databáze do čistého stavu.
    """
    test_config = {
        'TESTING': True,
        'SECRET_KEY': 'test',
        'DATABASE_CONNINFO': DB_TEST_CONNINFO,
        'BACKUP_DIR': str(tmp_path),
        'BACKUP_MAX_COUNT': 10,
        'PASSWORD_HASHER_PARAMETERS': {
            'time_cost': 1, 'memory_cost': 1024, 'parallelism': 1,
            'hash_len': 16, 'salt_len': 8,
        },
        'READER_INFO': {
            'serial_port_options': {
                'baudRate': 9600, 'dataBits': 8, 'stopBits': 1,
                'parity': 'none', 'flowControl': 'none',
            }
        },
        'SCHEDULER_ENABLED': False,
    }

    with patch('cashier_app.db.init_app'), \
         patch('cashier_app.scheduler.init_scheduler'):
        application = create_app(test_config)

    from flask.sessions import SecureCookieSessionInterface
    application.session_interface = SecureCookieSessionInterface()

    yield application

    # Cleanup: reinicializuj schéma, aby další testy měly čistou DB
    schema_path = os.path.join(
        os.path.dirname(__file__), '..', 'cashier_app', 'schema.sql',
    )
    with open(schema_path, 'r', encoding='utf-8') as f:
        schema_sql = f.read()

    with _db_pool.connection() as conn:
        conn.autocommit = True
        with conn.cursor() as cur:
            cur.execute("""
                DO $$ DECLARE r RECORD;
                BEGIN
                    FOR r IN (SELECT tablename FROM pg_tables
                              WHERE schemaname = 'public') LOOP
                        EXECUTE 'DROP TABLE IF EXISTS public.'
                                || quote_ident(r.tablename) || ' CASCADE';
                    END LOOP;
                END $$;
            """)
            cur.execute(schema_sql)


@pytest.mark.db
class TestBackupIntegration:

    def test_backup_and_restore_preserves_data(self, backup_app, _db_pool):
        """Záloha a následná obnova vrátí databázi do původního stavu."""
        # 1. Vlož data a commitni (musí být viditelné pro pg_dump)
        with _db_pool.connection() as conn:
            conn.autocommit = True
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO employees (username, email, password_hash, is_admin)
                    VALUES ('backup_user', 'backup@test.com', %s, TRUE)
                    RETURNING id
                """, (FAKE_HASH,))
                emp_id = cur.fetchone()['id']

        # 2. Vytvoř zálohu
        with backup_app.app_context():
            backup_path = backup_db()

        # 3. Změň data
        with _db_pool.connection() as conn:
            conn.autocommit = True
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE employees SET username = 'changed' WHERE id = %s",
                    (emp_id,),
                )
                cur.execute(
                    "SELECT username FROM employees WHERE id = %s", (emp_id,),
                )
                assert cur.fetchone()['username'] == 'changed'

        # 4. Obnov ze zálohy
        with backup_app.app_context():
            restore_db(backup_path)

        # 5. Ověř, že data jsou zpět v původním stavu
        with _db_pool.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT username FROM employees WHERE id = %s", (emp_id,),
                )
                assert cur.fetchone()['username'] == 'backup_user'

    def test_restore_rollbacks_on_corrupt_dump(self, backup_app, _db_pool):
        """Pokud pg_restore selže, single-transaction zajistí rollback."""
        # 1. Vlož data
        with _db_pool.connection() as conn:
            conn.autocommit = True
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO employees (username, email, password_hash, is_admin)
                    VALUES ('original', 'original@test.com', %s, TRUE)
                    RETURNING id
                """, (FAKE_HASH,))
                emp_id = cur.fetchone()['id']

        # 2. Vytvoř validní zálohu
        with backup_app.app_context():
            valid_path = backup_db()

        # 3. Změň data
        with _db_pool.connection() as conn:
            conn.autocommit = True
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE employees SET username = 'modified' WHERE id = %s",
                    (emp_id,),
                )

        # 4. Vytvoř poškozený dump (oříznutý na polovinu)
        corrupt_path = valid_path + '.corrupt'
        file_size = os.path.getsize(valid_path)
        with open(valid_path, 'rb') as src, open(corrupt_path, 'wb') as dst:
            dst.write(src.read(file_size // 2))

        # 5. Pokus o obnovu z poškozeného dumpu → selže
        with backup_app.app_context():
            with pytest.raises(RuntimeError, match='pg_restore selhal'):
                restore_db(corrupt_path)

        # 6. Data zůstala v modifikovaném stavu (rollback proběhl)
        with _db_pool.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT username FROM employees WHERE id = %s", (emp_id,),
                )
                assert cur.fetchone()['username'] == 'modified'
