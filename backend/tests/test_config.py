import unittest

from cryptography.fernet import Fernet
from pydantic import ValidationError

from app.core.config import Settings


class ProductionTransportTests(unittest.TestCase):
    def settings(self, **overrides):
        values = dict(
            app_env="production",
            app_base_url="http://47.245.56.28",
            allowed_origins="http://47.245.56.28",
            database_url="postgresql+psycopg://emotion_app:strong-password@localhost/emotion",
            session_token_pepper="test-only-" + "x" * 40,
            privacy_ledger_key=Fernet.generate_key().decode(),
            ai_enabled=False,
            ai_provider="disabled",
            cookie_secure=False,
            allow_insecure_http=False,
        )
        values.update(overrides)
        return Settings(_env_file=None, **values)

    def test_http_requires_explicit_opt_in(self):
        with self.assertRaisesRegex(ValidationError, "ALLOW_INSECURE_HTTP"):
            self.settings()

    def test_http_with_opt_in(self):
        settings = self.settings(allow_insecure_http=True)
        self.assertFalse(settings.cookie_secure)
        self.assertEqual(settings.origins, ["http://47.245.56.28"])

    def test_http_cannot_set_secure_cookie(self):
        with self.assertRaises(ValidationError):
            self.settings(allow_insecure_http=True, cookie_secure=True)

    def test_https_still_works(self):
        self.settings(app_base_url="https://example.com", cookie_secure=True)

    def test_http_does_not_allow_fake_provider(self):
        with self.assertRaisesRegex(ValidationError, "fake provider"):
            self.settings(allow_insecure_http=True, ai_provider="fake")

    def test_http_does_not_allow_demo_password(self):
        with self.assertRaisesRegex(ValidationError, "demonstration database password"):
            self.settings(
                allow_insecure_http=True,
                database_url="postgresql+psycopg://emotion:emotion@localhost/emotion",
            )
