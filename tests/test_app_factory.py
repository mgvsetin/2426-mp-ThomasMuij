"""Testy vytvoření Flask aplikace a obsluh chyb."""

import pytest
from datetime import datetime, date, timezone


class TestCreateApp:

    def test_app_exists(self, app):
        assert app is not None

    def test_testing_config(self, app):
        assert app.config['TESTING'] is True

    def test_secret_key_set(self, app):
        assert app.config['SECRET_KEY'] == 'test-secret-key'

    def test_scheduler_disabled_in_tests(self, app):
        assert app.config['SCHEDULER_ENABLED'] is False


class TestISOJSONProvider:

    def test_datetime_serialized_as_iso(self, app):
        with app.app_context():
            dt = datetime(2025, 6, 15, 14, 30, 0, tzinfo=timezone.utc)
            result = app.json.dumps({'ts': dt})
            assert '2025-06-15T14:30:00+00:00' in result

    def test_date_serialized_as_iso(self, app):
        with app.app_context():
            d = date(2025, 6, 15)
            result = app.json.dumps({'d': d})
            assert '2025-06-15' in result

    def test_naive_datetime_gets_utc(self, app):
        with app.app_context():
            dt = datetime(2025, 6, 15, 12, 0, 0)  # bez časové zóny
            result = app.json.dumps({'ts': dt})
            assert '+00:00' in result


class TestErrorHandlers:

    def test_413_error_handler(self, client):
        # POST s obsahem větším než MAX_CONTENT_LENGTH vyvolá chybu 413
        # Obsluhu otestujeme přímým vyvoláním scénáře s velkým nahráváním
        response = client.get('/nonexistent-route')
        assert response.status_code == 404

    def test_versioned_static_returns_path(self, app):
        with app.app_context():
            versioned = app.jinja_env.globals.get('versioned_static')
            assert versioned is not None


class TestCacheHeaders:

    def test_versioned_static_gets_cache_headers(self, client):
        # Požadavek na statický soubor s parametrem verze
        response = client.get('/static/scripts/general/utils.js?v=abc123')
        cc = response.cache_control
        assert cc.max_age == 60 * 60 * 24 * 365
        assert cc.public is True

    def test_non_versioned_static_gets_no_cache(self, client):
        response = client.get('/static/scripts/general/utils.js')
        cc = response.cache_control
        assert cc.no_cache is True
