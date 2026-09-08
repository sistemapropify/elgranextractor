from unittest.mock import patch

from django.test.runner import DiscoverRunner


class OfflineIntegrationRunner(DiscoverRunner):
    def setup_test_environment(self, **kwargs):
        super().setup_test_environment(**kwargs)
        self.http_guard = patch('requests.sessions.Session.request',
            side_effect=AssertionError('External HTTP is disabled in integration tests'))
        self.http_guard.start()

    def teardown_test_environment(self, **kwargs):
        self.http_guard.stop()
        super().teardown_test_environment(**kwargs)
