from django.test import SimpleTestCase

from database_safety import validate_database_safety


class DatabaseSafetyTests(SimpleTestCase):
    def azure_config(self, name="propiextractor"):
        return {
            "default": {
                "ENGINE": "mssql",
                "HOST": "granextractor-sql-prod.database.windows.net",
                "NAME": name,
            }
        }

    def test_accepts_propiextractor(self):
        validate_database_safety(self.azure_config(), argv=["manage.py", "check"])

    def test_rejects_memory_database(self):
        with self.assertRaises(RuntimeError):
            validate_database_safety(
                self.azure_config(":memory:"), argv=["manage.py", "check"]
            )

    def test_rejects_another_primary_database(self):
        with self.assertRaises(RuntimeError):
            validate_database_safety(
                self.azure_config("otra_base"), argv=["manage.py", "check"]
            )

    def test_rejects_tests_against_azure(self):
        with self.assertRaises(RuntimeError):
            validate_database_safety(
                self.azure_config(), argv=["manage.py", "test"]
            )

    def test_allows_local_sqlite_tests(self):
        validate_database_safety(
            {
                "default": {
                    "ENGINE": "django.db.backends.sqlite3",
                    "NAME": "local-tests.sqlite3",
                }
            },
            argv=["manage.py", "test"],
        )

    def test_allows_test_settings_to_replace_azure_bootstrap(self):
        validate_database_safety(
            self.azure_config(),
            argv=["manage.py", "test"],
            allow_local_test_settings=True,
        )
